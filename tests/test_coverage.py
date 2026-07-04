"""Seam 1 tests: coverage report and the 80-90% gate."""
from ingestion.coverage import build_coverage_report

MANIFEST = {
    "bns": {"in_scope_sections": ["1", "2", "3", "4", "5"], "official_total_sections": 358},
    "cpa": {"in_scope_sections": ["2", "4"], "official_total_sections": 107},
}


def test_full_in_scope_coverage_reports_100_percent_and_no_missing():
    report = build_coverage_report(
        {"bns": {"1", "2", "3", "4", "5", "99"}, "cpa": {"2", "4"}}, MANIFEST
    )
    assert report.per_act["bns"].coverage == 1.0
    assert report.per_act["bns"].missing_sections == []
    assert report.overall_coverage == 1.0


def test_partial_coverage_logs_the_missing_in_scope_sections():
    report = build_coverage_report({"bns": {"1", "2", "3", "4"}, "cpa": {"2", "4"}}, MANIFEST)
    assert report.per_act["bns"].coverage == 0.8
    assert report.per_act["bns"].missing_sections == ["5"]


def test_uncovered_remainder_against_official_total_is_logged():
    report = build_coverage_report({"bns": {"1", "2", "3", "4", "5"}, "cpa": {"2", "4"}}, MANIFEST)
    # 358 official sections, 5 ingested -> 353 known-uncovered remainder.
    assert report.per_act["bns"].uncovered_remainder == 353


def test_gate_passes_when_every_act_meets_the_minimum():
    report = build_coverage_report({"bns": {"1", "2", "3", "4", "5"}, "cpa": {"2", "4"}}, MANIFEST)
    assert report.meets_threshold(minimum=0.80)


def test_gate_fails_when_an_act_falls_below_the_minimum():
    report = build_coverage_report({"bns": {"1", "2", "3"}, "cpa": {"2", "4"}}, MANIFEST)
    assert report.per_act["bns"].coverage == 0.6
    assert not report.meets_threshold(minimum=0.80)
