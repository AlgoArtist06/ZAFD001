"""Seam 1 tests: vector load + retrieval smoke test.

Uses an offline deterministic embedder so the structural suite runs fully
autonomously (no network, no FastEmbed/Qdrant required). The embedder/store is
a seam: a FastEmbed+Qdrant backend can be substituted without changing callers.
"""
import sys
from types import SimpleNamespace

from ingestion.chunker import chunk_act
from ingestion.parser import parse_act
from ingestion.vectorstore import (
    FastEmbedEmbedder,
    InMemoryVectorStore,
    QdrantVectorStore,
)

from tests.doubles import HashEmbedder

CORPUS = """\
ACT_ID: bns
ACT: Bharatiya Nyaya Sanhita
YEAR: 2023
TYPE: criminal
SOURCE_URL: https://www.indiacode.nic.in/bns
RETRIEVAL_DATE: 2026-06-28
===
Section 318. Cheating.
Whoever by deceiving any person fraudulently or dishonestly induces the person
so deceived to deliver any property is said to cheat.

Section 319. Cheating by personation.
A person is said to cheat by personation if he cheats by pretending to be some
other person.

Section 303. Theft.
Whoever intending to take dishonestly any movable property out of the
possession of any person commits theft.
"""


def _loaded_store():
    chunks = chunk_act(parse_act(CORPUS))
    store = InMemoryVectorStore(HashEmbedder(dim=512))
    store.load(chunks)
    return store


def test_fastembed_embedder_runs_the_configured_model_on_cpu(monkeypatch):
    calls = {}

    class FakeTextEmbedding:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def embed(self, texts):
            assert texts == ["legal text"]
            return iter([SimpleNamespace(tolist=lambda: [0.25, 0.75])])

    monkeypatch.setitem(
        sys.modules, "fastembed", SimpleNamespace(TextEmbedding=FakeTextEmbedding)
    )

    embedder = FastEmbedEmbedder("BAAI/bge-base-en-v1.5", dim=768)

    assert embedder.embed("legal text") == [0.25, 0.75]
    assert calls == {
        "model_name": "BAAI/bge-base-en-v1.5",
        "providers": ["CPUExecutionProvider"],
    }


def test_qdrant_store_loads_and_retrieves_chunks_with_provenance():
    from qdrant_client import QdrantClient

    chunks = chunk_act(parse_act(CORPUS))
    store = QdrantVectorStore(
        embedder=HashEmbedder(dim=512),
        collection="legal_test",
        client=QdrantClient(":memory:"),
    )

    assert store.load(chunks) == 3
    top = store.search("deceiving a person to deliver property", top_k=1)[0]

    assert top.chunk.section_number == "318"
    assert top.chunk.provenance == chunks[0].provenance


class _RecordingClient:
    """A minimal Qdrant client double that records the size of each upsert."""

    def __init__(self):
        self.batches = []
        self._exists = False

    def collection_exists(self, collection_name):
        return self._exists

    def create_collection(self, **kwargs):
        self._exists = True

    def upsert(self, collection_name, points, wait):
        self.batches.append(len(points))

    def count(self, collection_name, exact=False):
        return SimpleNamespace(count=sum(self.batches))


def test_load_upserts_in_bounded_batches():
    # A whole corpus in one request exceeds Qdrant's 32 MB payload limit; the
    # load must split into several requests, each within the batch bound.
    chunks = chunk_act(parse_act(CORPUS)) * 200  # ~600 points
    client = _RecordingClient()
    store = QdrantVectorStore(embedder=HashEmbedder(dim=64), collection="c", client=client)

    assert store.load(chunks) == len(chunks)
    assert len(client.batches) > 1  # more than one upsert request
    assert max(client.batches) <= QdrantVectorStore._UPSERT_BATCH


def test_only_provided_chunks_are_loaded():
    store = _loaded_store()
    assert store.count() == 3


def test_known_query_returns_correct_section_as_top_hit():
    store = _loaded_store()
    top = store.search("deceiving a person to deliver property", top_k=3)[0]
    assert top.chunk.section_number == "318"


def test_theft_query_returns_theft_section_as_top_hit():
    store = _loaded_store()
    top = store.search("dishonestly taking movable property out of possession", top_k=3)[0]
    assert top.chunk.section_number == "303"


def test_search_respects_top_k():
    store = _loaded_store()
    assert len(store.search("property", top_k=2)) == 2
