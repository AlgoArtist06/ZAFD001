"""Vector load + retrieval seam.

The pipeline depends on two small protocols - an embedder and a vector store -
so the production backend (FastEmbed BAAI/bge-base-en-v1.5 + Qdrant) can be
swapped in without touching any caller. The default in-repo implementation is
fully offline and deterministic so the Seam 1 suite needs no services.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import List, Protocol, Sequence

from ingestion.models import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> List[float]: ...


class DeterministicEmbedder:
    """Hashing bag-of-words embedder with L2-normalised vectors.

    Good enough for a keyword-overlap retrieval smoke test; carries no model
    weights and makes no network calls.
    """

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm:
            vec = [v / norm for v in vec]
        return vec


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SearchHit:
    chunk: Chunk
    score: float


class InMemoryVectorStore:
    """Reference vector store. Holds legal documents only, in memory."""

    def __init__(self, embedder: Embedder):
        self._embedder = embedder
        self._items: List[tuple[List[float], Chunk]] = []

    def load(self, chunks: Sequence[Chunk]) -> int:
        for chunk in chunks:
            self._items.append((self._embedder.embed(chunk.text), chunk))
        return len(self._items)

    def count(self) -> int:
        return len(self._items)

    def search(self, query: str, top_k: int = 8) -> List[SearchHit]:
        q = self._embedder.embed(query)
        hits = [SearchHit(chunk=chunk, score=_cosine(q, vec)) for vec, chunk in self._items]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]
