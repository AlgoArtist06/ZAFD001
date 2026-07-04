"""Seam 1: the end-to-end ingestion pipeline (the Phase 0 gate).

This is the seam the PRD names: the point where the pipeline produces validated
chunk records around the vector load, independent of any RAG layer. The
acceptance criteria of the issue are asserted here.
"""
import dataclasses
import json
from pathlib import Path

import pytest

from config import load_config
from ingestion.models import ActType
from ingestion.pipeline import default_config, run_ingestion
from tests.doubles import HashEmbedder

DATA = Path(__file__).resolve().parent.parent / "data"
MANIFEST = json.loads((DATA / "ground_truth" / "manifest.json").read_text())


@pytest.fixture(scope="module")
def result():
    return run_ingestion(default_config())


def test_coverage_meets_the_gate_and_remainder_is_logged(result):
    assert result.coverage.meets_threshold(minimum=0.80)
    # The full official act is ingested, so no uncovered remainder remains.
    assert result.coverage.per_act["bns"].uncovered_remainder == 0


def test_every_loaded_chunk_has_complete_provenance(result):
    assert result.chunks  # non-empty
    assert all(c.provenance.is_complete() for c in result.chunks)


def test_chunks_lacking_provenance_are_flagged_and_never_loaded(result):
    loaded_ids = {c.chunk_id for c in result.chunks}
    for flag in result.validation.flagged:
        assert flag.chunk_id not in loaded_ids


def test_structural_integrity_no_orphans_parents_resolve(result):
    assert result.validation.structural_ok
    assert result.validation.orphaned_children == []
    valid = {f"{c.act_id}-{c.section_number}" for c in result.chunks if c.section_number}
    for child in (c for c in result.chunks if c.is_child()):
        assert child.parent_section_id in valid


def test_adaptive_chunking_small_whole_large_split():
    # Chunk adaptively at a deliberately low threshold so a multi-sub-section
    # section is forced to split while a short section still stays whole.
    # Structure only, so the hashing double keeps the run off the real model.
    low_threshold = run_ingestion(
        dataclasses.replace(default_config(), token_threshold=80),
        embedder=HashEmbedder(dim=64),
    )
    # BNS 318 (Cheating) has four sub-sections and exceeds the threshold -> split.
    cheating = [
        c for c in low_threshold.chunks if c.act_id == "bns" and c.section_number == "318"
    ]
    assert len(cheating) >= 2
    assert all(c.is_child() and c.parent_section_id == "bns-318" for c in cheating)
    # BNS 20 (Act of a child under seven years of age) is short -> stored whole.
    child_under_seven = [
        c for c in low_threshold.chunks if c.act_id == "bns" and c.section_number == "20"
    ]
    assert len(child_under_seven) == 1
    assert child_under_seven[0].parent_section_id is None


def test_chunk_token_threshold_setting_drives_the_pipeline():
    # The one CHUNK_TOKEN_THRESHOLD setting drives ingestion chunking, so the
    # chunk ids in the vector store match the ids the RAG runtime expects.
    assert default_config(load_config({})).token_threshold == 512
    assert (
        default_config(load_config({"CHUNK_TOKEN_THRESHOLD": "80"})).token_threshold
        == 80
    )


def test_ipc_to_bns_mapping_loaded_and_verified(result):
    assert result.mapping_verified
    assert result.mapping.lookup("420").bns == "318"


def test_amendment_history_captured_on_every_chunk(result):
    assert all(c.amendment_history.is_captured() for c in result.chunks)


def test_landmark_judgments_loaded_with_full_citations(result):
    assert len(result.landmarks) >= 4
    assert all(j.has_full_citation() for j in result.landmarks)


def test_schemes_loaded_as_scheme_provenance_chunks(result):
    schemes = [c for c in result.chunks if c.provenance.act_type == ActType.SCHEME]
    assert len(schemes) >= 2


def test_retrieval_smoke_known_queries_return_correct_top_section(result):
    top = result.store.search(
        "deceiving a person dishonestly to deliver property and cheat"
    )[0]
    assert top.chunk.act_id == "bns"
    assert top.chunk.section_number == "318"

    rights = result.store.search(
        "fundamental right to protection of life and personal liberty"
    )[0]
    assert rights.chunk.act_id == "constitution"
    assert rights.chunk.section_number == "21"


def test_content_accuracy_pinned_to_bare_act_ground_truth(result):
    # A pinned section may be stored whole or split into child chunks; the
    # pinned bare-act text must be found among that section's chunks.
    by_key = {}
    for c in result.chunks:
        by_key.setdefault((c.act_id, c.section_number), []).append(c)
    for pin in MANIFEST["spot_check"]:
        chunks = by_key[(pin["act_id"], pin["section"])]
        if "verbatim" in pin:
            assert any(
                c.provenance.verbatim_text == pin["verbatim"] for c in chunks
            )
        else:
            assert any(
                pin["verbatim_contains"] in c.provenance.verbatim_text
                for c in chunks
            )


def test_section_counts_match_ground_truth(result):
    for act_id, spec in MANIFEST["acts"].items():
        ingested = {
            c.section_number
            for c in result.chunks
            if c.act_id == act_id and c.section_number
        }
        assert len(ingested) == spec["expected_ingested_sections"]
