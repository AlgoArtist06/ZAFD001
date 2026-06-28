"""Seam 1 structural tests: the validation gate."""
from datetime import date

from ingestion.chunker import chunk_act
from ingestion.models import (
    ActType,
    AmendmentHistory,
    Chunk,
    ProvenanceRecord,
)
from ingestion.parser import parse_act
from ingestion.validation import validate_chunks

ACT = """\
ACT_ID: cpa
ACT: Consumer Protection Act
YEAR: 2019
TYPE: consumer
SOURCE_URL: https://www.indiacode.nic.in/cpa
RETRIEVAL_DATE: 2026-06-28
===
Section 2. Definitions.
"consumer" means any person who buys any goods.

Section 4. Establishment.
The Central Government shall establish an Authority.
"""


def _good_chunks():
    return chunk_act(parse_act(ACT))


def test_fully_provenanced_chunks_are_all_loadable():
    report = validate_chunks(_good_chunks())
    assert len(report.loadable) == 2
    assert report.flagged == []
    assert report.structural_ok


def test_chunk_missing_provenance_is_flagged_and_never_loaded():
    chunks = _good_chunks()
    bad = Chunk(
        chunk_id="cpa-99",
        act_id="cpa",
        section_number="99",
        text="orphan text",
        provenance=ProvenanceRecord(
            act_name="Consumer Protection Act",
            act_year=2019,
            act_type=ActType.CONSUMER,
            source_url="",  # missing -> incomplete
            source_hash="c" * 64,
            retrieval_date=date(2026, 6, 28),
            verbatim_text="orphan text",
            section_number="99",
        ),
        amendment_history=AmendmentHistory(none_recorded=True),
    )
    report = validate_chunks(chunks + [bad])
    assert "cpa-99" not in {c.chunk_id for c in report.loadable}
    assert any(f.chunk_id == "cpa-99" for f in report.flagged)
    assert "source_url" in next(f for f in report.flagged if f.chunk_id == "cpa-99").reasons


def test_orphaned_child_is_detected():
    chunks = _good_chunks()
    orphan = Chunk(
        chunk_id="cpa-4-9",
        act_id="cpa",
        section_number="4",
        sub_section="9",
        parent_section_id="cpa-does-not-exist",
        text="(9) ...",
        provenance=chunks[0].provenance,
        amendment_history=AmendmentHistory(none_recorded=True),
    )
    report = validate_chunks(chunks + [orphan])
    assert "cpa-4-9" in report.orphaned_children
    assert not report.structural_ok


def test_section_gaps_are_flagged_but_not_fatal():
    # Sections 2 and 4 exist; 3 is missing.
    report = validate_chunks(_good_chunks())
    assert ("cpa", "3") in report.section_gaps
    assert report.structural_ok  # gaps are logged, not orphan failures
