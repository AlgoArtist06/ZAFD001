"""Hybrid retrieval routed by Covered Domain."""
from ingestion.models import ActType
from ingestion.vectorstore import QdrantVectorStore

from tests.doubles import HashEmbedder

from rag.domain.routing import route_domains
from rag.domain.expansion import expand
from rag.domain.retrieval import HybridRetriever


def test_consumer_query_routes_to_consumer_domain_only():
    domains = route_domains("How do I file a consumer complaint about goods?")
    assert ActType.CONSUMER in domains
    assert ActType.CRIMINAL not in domains


def test_routing_filters_criminal_sections_out_of_a_consumer_query(corpus):
    retriever = HybridRetriever(corpus, embedder=HashEmbedder())
    domains = route_domains("How do I file a consumer complaint about goods?")
    hits = retriever.retrieve("How do I file a consumer complaint about goods?", domains)
    assert hits
    assert all(h.chunk.provenance.act_type == ActType.CONSUMER for h in hits)


def test_hybrid_uses_both_keyword_and_vector_signal(corpus):
    retriever = HybridRetriever(corpus, embedder=HashEmbedder())
    hits = retriever.retrieve("theft of movable property", [ActType.CRIMINAL])
    top = hits[0]
    assert top.chunk.section_number == "303"
    assert top.keyword_score > 0
    assert top.vector_score > 0


def test_qdrant_retrieval_keeps_hybrid_scores_and_domain_filtering(corpus):
    from qdrant_client import QdrantClient

    embedder = HashEmbedder()
    store = QdrantVectorStore(
        embedder=embedder,
        collection="retrieval_test",
        client=QdrantClient(":memory:"),
    )
    store.load(corpus)
    retriever = HybridRetriever(corpus, embedder=embedder, vector_store=store)

    hits = retriever.retrieve("consumer complaint goods", [ActType.CONSUMER])

    assert hits
    assert all(hit.chunk.provenance.act_type == ActType.CONSUMER for hit in hits)
    assert hits[0].keyword_score > 0
    assert hits[0].vector_score > 0
    assert expand(hits, corpus)[0].is_expanded
