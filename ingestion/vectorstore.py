"""Vector load + retrieval seam.

The pipeline depends on two small protocols - an embedder and a vector store -
so the production backend (FastEmbed BAAI/bge-base-en-v1.5 + Qdrant) can be
swapped in without touching any caller. Embeddings are always real (FastEmbed);
tests inject their own doubles - the product has no offline mode (ADR 0010).
"""
from __future__ import annotations

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

class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> List[float]: ...


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

    def delete_acts(self, act_ids: Sequence[str]) -> None:
        """Remove every chunk of the given acts (before re-loading them)."""
        gone = set(act_ids)
        self._items = [
            (vec, chunk) for vec, chunk in self._items if chunk.act_id not in gone
        ]

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

    # Qdrant rejects a single request larger than 32 MB. Verbatim statutory text
    # makes each point large (tens of KB), so the whole corpus in one upsert
    # exceeds that; batch it. 256 keeps a batch well under the limit.
    _UPSERT_BATCH = 256

    def load(self, chunks: Sequence[Chunk]) -> int:
        from qdrant_client.models import Distance, PointStruct, VectorParams

        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._embedder.dim, distance=Distance.COSINE),
            )
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                vector=self._embedder.embed(chunk.text),
                payload=_chunk_payload(chunk),
            )
            for chunk in chunks
        ]
        for start in range(0, len(points), self._UPSERT_BATCH):
            self._client.upsert(
                collection_name=self._collection,
                points=points[start : start + self._UPSERT_BATCH],
                wait=True,
            )
        return self.count()

    def count(self) -> int:
        if not self._client.collection_exists(self._collection):
            return 0
        return self._client.count(collection_name=self._collection, exact=True).count

    def delete_acts(self, act_ids: Sequence[str]) -> None:
        """Remove every point of the given acts, so a re-load cannot leave a
        renamed or removed section behind as a stale point."""
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchAny

        if not act_ids or not self._client.collection_exists(self._collection):
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="chunk.act_id",
                            match=MatchAny(any=list(act_ids)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def fetch(self, chunk_ids: Sequence[str]) -> List[Chunk]:
        """The stored chunks for the given ``chunk_id``s, skipping any missing.

        Point ids are deterministic (uuid5 of the chunk id), so a chunk can be
        looked up directly; the startup consistency check uses this to verify a
        sample of the collection against the in-process corpus.
        """
        if not chunk_ids or not self._client.collection_exists(self._collection):
            return []
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=[str(uuid.uuid5(uuid.NAMESPACE_URL, cid)) for cid in chunk_ids],
            with_payload=True,
        )
        return [_chunk_from_payload(dict(p.payload or {})) for p in points]

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


def create_embedder(config, dim=None) -> Embedder:
    """The embedding seam: always FastEmbed - local, CPU, keyless, and real.

    There is no offline stand-in (ADR 0010): retrieval quality is part of the
    product's correctness, so a deterministic hashing embedder must never serve
    answers. Tests inject their own doubles explicitly.
    """
    size = dim or config.embedding_dim
    return FastEmbedEmbedder(config.embedding_model, size)


def create_vector_store(config, embedder: Embedder) -> VectorStore:
    """The vector-store seam: Qdrant when configured, in-memory otherwise."""
    if config.vector_store_backend == "qdrant":
        return QdrantVectorStore(
            embedder=embedder,
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
            collection=config.qdrant_collection,
        )
    return InMemoryVectorStore(embedder)
