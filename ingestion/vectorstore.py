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
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from typing import List, Protocol, Sequence

from ingestion.models import (
    ActType,
    AmendmentEntry,
    AmendmentHistory,
    Chunk,
    ProvenanceRecord,
)

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


class FastEmbedEmbedder:
    """Local CPU BGE embeddings; model weights never require an API key."""

    def __init__(self, model_name: str, dim: int):
        from fastembed import TextEmbedding

        self.dim = dim
        self._model = TextEmbedding(
            model_name=model_name, providers=["CPUExecutionProvider"]
        )

    def embed(self, text: str) -> List[float]:
        return list(self._model.embed([text]))[0].tolist()


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SearchHit:
    chunk: Chunk
    score: float


class VectorStore(Protocol):
    def load(self, chunks: Sequence[Chunk]) -> int: ...

    def count(self) -> int: ...

    def search(
        self,
        query: str,
        top_k: int = 8,
        domains: Sequence[ActType] | None = None,
    ) -> List[SearchHit]: ...


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

    def search(
        self,
        query: str,
        top_k: int = 8,
        domains: Sequence[ActType] | None = None,
    ) -> List[SearchHit]:
        q = self._embedder.embed(query)
        allowed = set(domains) if domains is not None else set(ActType)
        hits = [
            SearchHit(chunk=chunk, score=_cosine(q, vec))
            for vec, chunk in self._items
            if chunk.provenance.act_type in allowed
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


def _chunk_payload(chunk: Chunk) -> dict:
    payload = asdict(chunk)
    payload["provenance"]["act_type"] = chunk.provenance.act_type.value
    payload["provenance"]["retrieval_date"] = chunk.provenance.retrieval_date.isoformat()
    return {"chunk": payload}


def _chunk_from_payload(payload: dict) -> Chunk:
    raw = payload["chunk"]
    provenance = raw.pop("provenance")
    amendments = raw.pop("amendment_history")
    provenance["act_type"] = ActType(provenance["act_type"])
    provenance["retrieval_date"] = date.fromisoformat(provenance["retrieval_date"])
    amendments["entries"] = [AmendmentEntry(**entry) for entry in amendments["entries"]]
    return Chunk(
        **raw,
        provenance=ProvenanceRecord(**provenance),
        amendment_history=AmendmentHistory(**amendments),
    )


class QdrantVectorStore:
    """Qdrant adapter storing vectors and complete legal provenance payloads."""

    def __init__(
        self,
        embedder: Embedder,
        collection: str,
        url: str | None = None,
        api_key: str | None = None,
        client=None,
    ):
        from qdrant_client import QdrantClient

        self._embedder = embedder
        self._collection = collection
        self._client = client or QdrantClient(url=url, api_key=api_key)

    def load(self, chunks: Sequence[Chunk]) -> int:
        from qdrant_client.models import Distance, PointStruct, VectorParams

        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._embedder.dim, distance=Distance.COSINE),
            )
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                    vector=self._embedder.embed(chunk.text),
                    payload=_chunk_payload(chunk),
                )
                for chunk in chunks
            ],
            wait=True,
        )
        return self.count()

    def count(self) -> int:
        if not self._client.collection_exists(self._collection):
            return 0
        return self._client.count(collection_name=self._collection, exact=True).count

    def search(
        self,
        query: str,
        top_k: int = 8,
        domains: Sequence[ActType] | None = None,
    ) -> List[SearchHit]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        if top_k <= 0 or not self._client.collection_exists(self._collection):
            return []
        query_filter = None
        if domains is not None:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="chunk.provenance.act_type",
                        match=MatchAny(any=[domain.value for domain in domains]),
                    )
                ]
            )
        points = self._client.query_points(
            collection_name=self._collection,
            query=self._embedder.embed(query),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        ).points
        return [
            SearchHit(chunk=_chunk_from_payload(dict(point.payload or {})), score=point.score)
            for point in points
        ]
