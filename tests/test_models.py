"""Seam 1 structural tests: domain model invariants (self-verifying)."""
from datetime import date

from ingestion.models import (
    ActType,
    AmendmentEntry,
    AmendmentHistory,
    Chunk,
    ProvenanceRecord,
)


def _complete_provenance(**overrides):
    base = dict(
        act_name="Bharatiya Nyaya Sanhita",
        act_year=2023,
        section_number="318",
        act_type=ActType.CRIMINAL,
        source_url="https://www.indiacode.nic.in/bns",
        source_hash="a" * 64,
        retrieval_date=date(2026, 6, 28),
        verbatim_text="Whoever cheats shall be punished...",
    )
    base.update(overrides)
    return ProvenanceRecord(**base)


def test_complete_statutory_provenance_is_complete():
    assert _complete_provenance().is_complete()


def test_provenance_missing_verbatim_text_is_incomplete():
    assert not _complete_provenance(verbatim_text="").is_complete()


def test_provenance_missing_source_url_is_incomplete():
    assert not _complete_provenance(source_url="").is_complete()


def test_scheme_provenance_uses_authority_and_scheme_url_in_place_of_section():
    prov = ProvenanceRecord(
        act_name="PM Awas Yojana",
        act_year=2015,
        section_number=None,
        act_type=ActType.SCHEME,
        source_url="https://pmaymis.gov.in",
        source_hash="b" * 64,
        retrieval_date=date(2026, 6, 28),
        verbatim_text="Eligibility: ...",
        governing_authority="Ministry of Housing and Urban Affairs",
        scheme_url="https://pmaymis.gov.in",
    )
    assert prov.is_complete()


def test_scheme_provenance_without_governing_authority_is_incomplete():
    prov = ProvenanceRecord(
        act_name="PM Awas Yojana",
        act_year=2015,
        section_number=None,
        act_type=ActType.SCHEME,
        source_url="https://pmaymis.gov.in",
        source_hash="b" * 64,
        retrieval_date=date(2026, 6, 28),
        verbatim_text="Eligibility: ...",
        governing_authority="",
        scheme_url="https://pmaymis.gov.in",
    )
    assert not prov.is_complete()


def test_statutory_provenance_without_section_number_is_incomplete():
    assert not _complete_provenance(section_number=None).is_complete()


def test_amendment_history_is_captured_even_when_none_recorded():
    hist = AmendmentHistory(none_recorded=True)
    assert hist.is_captured()
    assert hist.entries == []


def test_amendment_history_with_entries_is_captured():
    hist = AmendmentHistory(
        entries=[AmendmentEntry(year=2024, description="Substituted by Act 8 of 2024")]
    )
    assert hist.is_captured()


def test_amendment_history_uncaptured_when_neither_flagged_nor_listed():
    assert not AmendmentHistory().is_captured()


def test_chunk_without_complete_provenance_is_not_loadable():
    chunk = Chunk(
        chunk_id="bns-318",
        act_id="bns",
        section_number="318",
        text="Whoever cheats...",
        provenance=_complete_provenance(verbatim_text=""),
        amendment_history=AmendmentHistory(none_recorded=True),
    )
    assert not chunk.is_loadable()


def test_child_chunk_carries_parent_section_id():
    chunk = Chunk(
        chunk_id="bns-318-1",
        act_id="bns",
        section_number="318",
        sub_section="1",
        parent_section_id="bns-318",
        text="(1) ...",
        provenance=_complete_provenance(),
        amendment_history=AmendmentHistory(none_recorded=True),
    )
    assert chunk.is_child()
    assert chunk.parent_section_id == "bns-318"
