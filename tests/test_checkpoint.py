"""Seam 1 tests: the consolidated Phase 0 checkpoint artifact."""
import pytest

from ingestion.checkpoint import build_checkpoint, sample_sections
from ingestion.pipeline import default_config, run_ingestion
from tests.doubles import HashEmbedder


@pytest.fixture(scope="module")
def result():
    # The artifact's content, not embedding quality, is under test, so the
    # hashing double keeps the run off the real model.
    return run_ingestion(default_config(), embedder=HashEmbedder(dim=64))


def test_between_30_and_50_sample_sections_are_produced(result):
    samples = sample_sections(result)
    assert 30 <= len(samples) <= 50


def test_every_sample_carries_a_citation_and_official_source_link(result):
    for s in sample_sections(result):
        assert s.citation
        assert s.source_url.startswith("http")
        assert s.verbatim


def test_checkpoint_markdown_includes_coverage_mapping_and_approval_gate(result):
    md = build_checkpoint(result)
    assert "Coverage" in md
    assert "IPC-to-BNS" in md
    assert "https://www.indiacode.nic.in" in md
    assert "AWAITING HUMAN APPROVAL" in md
    # Side-by-side: verbatim text next to its official source link.
    assert "Equality before law" in md or "equality before the law" in md
