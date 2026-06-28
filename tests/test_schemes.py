"""Seam 1 tests: government scheme fact-cards."""
from pathlib import Path

from ingestion.models import ActType
from ingestion.schemes import load_scheme_chunks

DATA = Path(__file__).resolve().parent.parent / "data"


def _chunks():
    return load_scheme_chunks(DATA / "schemes.json")


def test_scheme_cards_become_loadable_chunks():
    chunks = _chunks()
    assert len(chunks) >= 2
    assert all(c.is_loadable() for c in chunks)


def test_scheme_chunk_uses_scheme_provenance():
    pmay = next(c for c in _chunks() if c.act_id == "pmay")
    assert pmay.provenance.act_type == ActType.SCHEME
    assert pmay.provenance.section_number is None
    assert pmay.provenance.governing_authority == "Ministry of Housing and Urban Affairs"
    assert pmay.provenance.scheme_url == "https://pmaymis.gov.in"


def test_scheme_chunk_has_captured_amendment_history():
    assert all(c.amendment_history.is_captured() for c in _chunks())
