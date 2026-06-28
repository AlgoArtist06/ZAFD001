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

from ingestion.models import ActType, Chunk
from ingestion.vectorstore import DeterministicEmbedder, Embedder, _cosine
from rag.text import content_stems

PROFESSIONAL = "professional"

# Citizen Mode complaint-to-concept normalization: lay words mapped to the
# statutory term they describe. Injected into the query before retrieval so a
# colloquial complaint still reaches the right section. Professional Mode skips
# this entirely - it takes precise legal terms and matches them exactly.
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


def expand_query(query: str, mode: str) -> str:
    """Prepare a query for retrieval according to its Mode.

    Professional Mode returns the query unchanged (exact keyword, no expansion).
    Citizen Mode appends the legal concept behind any lay complaint word it
    recognises, so colloquial phrasing reaches the matching statutory section.
    """
    if mode == PROFESSIONAL:
        return query
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

    def __init__(self, chunks: Sequence[Chunk], embedder: Embedder | None = None):
        self._embedder = embedder or DeterministicEmbedder()
        self._chunks = list(chunks)
        self._stems = [set(content_stems(c.text)) for c in self._chunks]
        self._vectors = [self._embedder.embed(c.text) for c in self._chunks]

    def retrieve(
        self,
        query: str,
        domains: Sequence[ActType] | None = None,
        top_k: int = 8,
    ) -> List[RetrievalHit]:
        allowed = set(domains) if domains is not None else set(ActType)
        q_stems = set(content_stems(query))
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
                    # Keyword overlap dominates ranking; vector breaks ties and
                    # surfaces semantically-close hits with no exact word match.
                    score=keyword_score + vector_score,
                    keyword_score=keyword_score,
                    vector_score=vector_score,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]
