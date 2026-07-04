"""The import-assist tool: fetched statute -> reviewable bare-act draft.

The tool is a drafting assistant behind a human gate: it must produce a draft
that round-trips through the real parser, name what looks suspicious in its
report, and physically refuse to write into data/sources/ - promotion is a
human move (ADR 0008).
"""
from pathlib import Path

import pytest

from ingestion.import_assist import (
    build_report,
    compose_bare_act,
    detect_sections,
    extract_text,
    run,
)
from ingestion.parser import parse_act

_HTML = """
<html><head><style>body { color: red }</style></head><body>
<h1>The Testing Act, 2026</h1>
<p>1. Short title. This Act may be called the Testing Act, 2026.</p>
<p>2. Definitions. In this Act, unless the context otherwise requires,
useful terms carry their defined meanings throughout this legislation.</p>
<p>3. Penalty for mischief. Whoever commits mischief under this Act shall be
liable to a fine that the adjudicating officer determines.</p>
</body></html>
"""


def test_html_is_extracted_and_sections_detected():
    sections = detect_sections(extract_text(_HTML.encode(), hint="act.html"))
    assert [s.number for s in sections] == ["1", "2", "3"]
    assert sections[0].heading == "Short title"
    assert "Testing Act, 2026" in sections[0].body
    # Tag soup and the stylesheet never leak into statutory text.
    assert "color: red" not in " ".join(s.body for s in sections)


def test_composed_draft_round_trips_through_the_real_parser():
    sections = detect_sections(extract_text(_HTML.encode(), hint="act.html"))
    draft = compose_bare_act(
        "testing", "Testing Act", 2026, "consumer", "https://example.gov.in", sections
    )
    act = parse_act(draft)
    assert act.act_id == "testing"
    assert [s.section_number for s in act.sections] == ["1", "2", "3"]
    assert "Whoever commits mischief" in act.sections[2].full_text


def test_report_flags_suspicious_sections_and_never_auto_approves():
    sections = detect_sections("1. Stub.\n2. Real section. " + "x" * 80)
    report = build_report(
        "testing",
        "https://example.gov.in",
        Path("data/staging/testing.txt"),
        sections,
        parse_ok=True,
        parse_error="",
        official_total=5,
    )
    assert "Sections detected: 2 (official total: 5)" in report
    assert "1" in report.split("Suspiciously short")[1].splitlines()[0]
    assert "AWAITING HUMAN APPROVAL" in report


def test_run_writes_draft_and_report_but_refuses_the_sources_dir(tmp_path, monkeypatch):
    source = tmp_path / "act.html"
    source.write_bytes(_HTML.encode())
    monkeypatch.setattr("ingestion.import_assist._STAGING", tmp_path / "staging")
    monkeypatch.setattr("ingestion.import_assist._ARTIFACTS", tmp_path / "artifacts")

    draft_path = run(
        act_id="testing",
        act_name="Testing Act",
        year=2026,
        act_type="consumer",
        file=source,
    )

    assert draft_path.exists()
    assert (tmp_path / "artifacts" / "import_report_testing.md").exists()
    parsed = parse_act(draft_path.read_text())
    assert len(parsed.sections) == 3

    with pytest.raises(SystemExit, match="data/sources"):
        run(
            act_id="testing",
            act_name="Testing Act",
            year=2026,
            act_type="consumer",
            file=source,
            out=Path(__file__).resolve().parent.parent / "data" / "sources" / "x.txt",
        )
