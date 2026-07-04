"""Parent-section and sibling expansion before generation."""
from ingestion.models import ActType

from rag.domain.routing import route_domains
from rag.domain.expansion import expand
from rag.domain.retrieval import HybridRetriever
from tests.doubles import HashEmbedder


def test_a_matched_child_expands_to_its_parent_and_siblings(corpus):
    retriever = HybridRetriever(corpus, embedder=HashEmbedder())
    # cpa-35 is split into children 35(1) and 35(2); a query that only hits one
    # child must still surface the whole section.
    hits = retriever.retrieve(
        "How is a consumer complaint filed?", route_domains("consumer complaint")
    )
    sections = expand(hits, corpus)
    cpa = next(s for s in sections if s.section_number == "35")
    assert cpa.is_expanded
    labels = {c.sub_section for c in cpa.chunks}
    assert labels == {"1", "2"}
    # The reconstructed section text carries both sub-sections (provisos intact).
    assert "District Commission" in cpa.verbatim_text
    assert "accompanied with" in cpa.verbatim_text


def test_a_whole_section_hit_expands_to_itself(corpus):
    retriever = HybridRetriever(corpus, embedder=HashEmbedder())
    hits = retriever.retrieve("theft of property", [ActType.CRIMINAL])
    sections = expand(hits, corpus)
    bns = next(s for s in sections if s.section_number == "303")
    assert not bns.is_expanded
    assert len(bns.chunks) == 1
