"""The startup corpus consistency check.

The RAG runtime reads Qdrant but only the ingestion pipeline writes it, so the
two can silently diverge - an empty, stale, or differently-chunked collection
degrades answers with no error anywhere. The check fails fast at startup
instead, naming the fix, and only warns in development so offline work
continues.
"""
import dataclasses
import random

import pytest
from qdrant_client import QdrantClient

from ingestion.vectorstore import QdrantVectorStore

from tests.doubles import HashEmbedder
from rag.infrastructure.consistency import CorpusInconsistent, check_corpus_consistency


def _store(chunks):
    store = QdrantVectorStore(
        embedder=HashEmbedder(dim=64),
        collection="consistency-test",
        client=QdrantClient(":memory:"),
    )
    store.load(chunks)
    return store


def test_matching_collection_passes(corpus):
    store = _store(corpus)
    assert check_corpus_consistency(store, corpus) is True


def test_missing_or_partial_collection_fails_fast_with_the_fix(corpus):
    store = _store(corpus[: len(corpus) // 2])
    with pytest.raises(CorpusInconsistent, match="python -m ingestion"):
        check_corpus_consistency(store, corpus)


def test_same_size_but_different_source_text_fails(corpus):
    store = _store(corpus)
    tampered = [
        dataclasses.replace(
            chunk,
            provenance=dataclasses.replace(
                chunk.provenance, source_hash="a-different-source-hash"
            ),
        )
        for chunk in corpus
    ]
    with pytest.raises(CorpusInconsistent, match="different source text"):
        check_corpus_consistency(
            store, tampered, sample_size=len(tampered), rng=random.Random(0)
        )


def test_development_mode_warns_instead_of_refusing_to_start(corpus, caplog):
    store = _store(corpus[: len(corpus) // 2])
    with caplog.at_level("WARNING"):
        ok = check_corpus_consistency(store, corpus, strict=False)
    assert ok is False
    assert any("python -m ingestion" in message for message in caplog.messages)
