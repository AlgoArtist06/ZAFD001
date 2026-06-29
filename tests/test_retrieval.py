"""Hybrid retrieval routed by Covered Domain."""
from ingestion.models import ActType

from rag.domain import route_domains
from rag.retrieval import HybridRetriever


def test_consumer_query_routes_to_consumer_domain_only():
    domains = route_domains("How do I file a consumer complaint about goods?")
    assert ActType.CONSUMER in domains
    assert ActType.CRIMINAL not in domains


def test_routing_filters_criminal_sections_out_of_a_consumer_query(corpus):
    retriever = HybridRetriever(corpus)
    domains = route_domains("How do I file a consumer complaint about goods?")
    hits = retriever.retrieve("How do I file a consumer complaint about goods?", domains)
    assert hits
    assert all(h.chunk.provenance.act_type == ActType.CONSUMER for h in hits)


def test_hybrid_uses_both_keyword_and_vector_signal(corpus):
    retriever = HybridRetriever(corpus)
    hits = retriever.retrieve("theft of movable property", [ActType.CRIMINAL])
    top = hits[0]
    assert top.chunk.section_number == "303"
    assert top.keyword_score > 0
    assert top.vector_score > 0
