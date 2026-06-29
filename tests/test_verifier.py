"""Citation verifier rejects any section not present in the retrieved chunks."""
from ingestion.models import ActType

from rag.citation import Citation
from rag.domain import route_domains
from rag.expansion import expand
from rag.retrieval import HybridRetriever
from rag.verifier import verify_citations


def _sections(corpus, query, domains=None):
    hits = HybridRetriever(corpus).retrieve(query, domains or route_domains(query))
    return expand(hits, corpus)


def test_a_retrieved_citation_survives(corpus):
    sections = _sections(corpus, "theft of property", [ActType.CRIMINAL])
    real = Citation.from_section(sections[0])
    assert verify_citations([real], sections) == [real]


def test_a_fabricated_section_is_stripped(corpus):
    sections = _sections(corpus, "theft of property", [ActType.CRIMINAL])
    fabricated = Citation(
        act_id="bns",
        act_name="Bharatiya Nyaya Sanhita",
        act_year=2023,
        section_number="999",  # never retrieved
        verbatim_text="Whoever invents a section shall be disbelieved.",
        source_url="https://example.test",
    )
    assert verify_citations([fabricated], sections) == []
