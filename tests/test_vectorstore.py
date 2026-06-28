"""Seam 1 tests: vector load + retrieval smoke test.

Uses an offline deterministic embedder so the structural suite runs fully
autonomously (no network, no FastEmbed/Qdrant required). The embedder/store is
a seam: a FastEmbed+Qdrant backend can be substituted without changing callers.
"""
from ingestion.chunker import chunk_act
from ingestion.parser import parse_act
from ingestion.vectorstore import DeterministicEmbedder, InMemoryVectorStore

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
    store = InMemoryVectorStore(DeterministicEmbedder(dim=512))
    store.load(chunks)
    return store


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
