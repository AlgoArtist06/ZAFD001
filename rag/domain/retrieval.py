"""Hybrid retrieval, routed by Covered Domain.

Combines keyword overlap (for exact section references, act names, and statutory
terms) with vector similarity (for natural-language complaints), over the subset
of chunks whose ``act_type`` is in the routed domains. The keyword score doubles
as the support gate: a hit with zero lexical overlap is not grounded in the
Source of Truth, so the answer seam treats a query with no keyword-grounded hit
as unsupported (a Refusal) rather than a guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

from config import AppConfig
from ingestion.models import ActType, Chunk
from ingestion.vectorstore import Embedder, VectorStore, _cosine
from rag.domain.text import content_stems

# Complaint-to-concept normalization: lay words mapped to the statutory term
# they describe. Injected into the query before retrieval so a colloquial
# complaint still reaches the right section.
_LAY_CONCEPTS = {
    "tricked": "cheating fraud",
    "fooled": "cheating fraud",
    "conned": "cheating fraud",
    "duped": "cheating fraud",
    "swindled": "cheating fraud",
    "ripped": "cheating fraud",
    "scammed": "cheating fraud",
}

_WORD_RE = re.compile(r"[a-z]+")


def expand_query(query: str) -> str:
    """Prepare a query for retrieval.

    Appends the legal concept behind any lay complaint word it recognises, so
    colloquial phrasing reaches the matching statutory section.
    """
    words = set(_WORD_RE.findall(query.lower()))
    additions = [_LAY_CONCEPTS[w] for w in words if w in _LAY_CONCEPTS]
    return query + " " + " ".join(additions) if additions else query


@dataclass
class RetrievalHit:
    chunk: Chunk
    score: float
    keyword_score: int
    vector_score: float


class HybridRetriever:
    """Keyword + vector retrieval filtered to a set of Covered Domains."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        *,
        embedder: Embedder,
        app_config: AppConfig | None = None,
        vector_store: VectorStore | None = None,
    ):
        # The embedder is REQUIRED - there is no offline stand-in (ADR 0010).
        # Production injects FastEmbed via rag.composition; tests inject their
        # own doubles. The domain never reads credentials or the environment.
        self._embedder = embedder
        self._store = vector_store
        self._config = app_config
        self._chunks = list(chunks)
        self._stems = [set(content_stems(c.text)) for c in self._chunks]
        self._vectors = (
            []
            if self._store is not None
            else [self._embedder.embed(c.text) for c in self._chunks]
        )

    def retrieve(
        self,
        query: str,
        domains: Sequence[ActType] | None = None,
        top_k: int | None = None,
    ) -> List[RetrievalHit]:
        allowed = set(domains) if domains is not None else set(ActType)
        q_stems = set(content_stems(query))
        limit = top_k if top_k is not None else (
            self._config.retrieval_top_k if self._config else 8
        )
        # HYBRID_ALPHA weighs the two normalized signals: 0 = pure keyword
        # overlap, 1 = pure vector similarity. Both land in [0, 1], so neither
        # can drown the other the way a raw integer overlap count did.
        alpha = self._config.hybrid_alpha if self._config else 0.5

        def hybrid(keyword_score: int, vector_score: float) -> float:
            keyword_norm = keyword_score / len(q_stems) if q_stems else 0.0
            return (1 - alpha) * keyword_norm + alpha * vector_score

        if self._store is not None:
            # ponytail: preserve the existing exact hybrid score over all filtered
            # points; move keyword ranking into Qdrant if corpus size makes this slow.
            candidates = self._store.search(
                query, top_k=self._store.count(), domains=list(allowed)
            )
            live_hits = []
            for hit in candidates:
                keyword_score = len(q_stems & set(content_stems(hit.chunk.text)))
                live_hits.append(
                    RetrievalHit(
                        chunk=hit.chunk,
                        score=hybrid(keyword_score, hit.score),
                        keyword_score=keyword_score,
                        vector_score=hit.score,
                    )
                )
            live_hits.sort(key=lambda hit: hit.score, reverse=True)
            return live_hits[:limit]

        q_vec = self._embedder.embed(query)

        hits: List[RetrievalHit] = []
        for chunk, stems, vec in zip(self._chunks, self._stems, self._vectors):
            if chunk.provenance.act_type not in allowed:
                continue
            keyword_score = len(q_stems & stems)
            vector_score = _cosine(q_vec, vec)
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=hybrid(keyword_score, vector_score),
                    keyword_score=keyword_score,
                    vector_score=vector_score,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
