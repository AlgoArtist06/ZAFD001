"""Seam 1 tests: the consolidated Phase 0 checkpoint artifact."""
from ingestion.checkpoint import build_checkpoint, sample_sections
from ingestion.pipeline import default_config, run_ingestion


def _result():
    return run_ingestion(default_config())


def test_between_30_and_50_sample_sections_are_produced():
    samples = sample_sections(_result())
    assert 30 <= len(samples) <= 50


def test_every_sample_carries_a_citation_and_official_source_link():
    for s in sample_sections(_result()):
        assert s.citation
        assert s.source_url.startswith("http")
        assert s.verbatim


def test_checkpoint_markdown_includes_coverage_mapping_and_approval_gate():
    md = build_checkpoint(_result())
    assert "Coverage" in md
    assert "IPC-to-BNS" in md
    assert "https://www.indiacode.nic.in" in md
    assert "AWAITING HUMAN APPROVAL" in md
    # Side-by-side: verbatim text next to its official source link.
    assert "Equality before law" in md or "equality before the law" in md
