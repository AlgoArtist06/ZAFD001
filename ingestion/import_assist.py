"""Import assist: turn a fetched statute into a DRAFT bare-act source file.

    python -m ingestion.import_assist \
        --url https://www.indiacode.nic.in/... \
        --act-id it_act --act-name "Information Technology Act" \
        --year 2000 --type cyber

The tool fetches (or reads) a statute as HTML, PDF, or plain text, detects its
sections heuristically, and composes a draft in the bare-act format the parser
consumes. It then round-trips the draft through :func:`ingestion.parser.parse_act`
and writes a review report naming what it found and what looks suspicious.

It is a drafting assistant, not a parser guarantee: statutory text is quoted
verbatim in answers, so a human must compare the draft against the official
source before it becomes part of the Source of Truth. To keep that gate
physical, the tool writes only under ``data/staging/`` and refuses to write
into ``data/sources/`` - promoting a reviewed draft is a deliberate human move
(see ADR 0008).
"""
from __future__ import annotations

import argparse
import html as html_lib
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

from ingestion.parser import parse_act

_ROOT = Path(__file__).resolve().parent.parent
_STAGING = _ROOT / "data" / "staging"
_SOURCES = _ROOT / "data" / "sources"
_ARTIFACTS = _ROOT / "artifacts"

# A section start in extracted statute text: "12. Heading..." or "12A. ...".
_SECTION_START = re.compile(r"^\s*(\d+[A-Z]{0,2})\.\s+(.+)$")
_TAG = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


@dataclass
class DraftSection:
    number: str
    heading: str
    body: str


def extract_text(raw: bytes, hint: str = "") -> str:
    """Plain text from raw HTML, PDF, or text bytes."""
    if raw[:5] == b"%PDF-" or hint.lower().endswith(".pdf"):
        from pypdf import PdfReader  # lazy: only PDF imports need the dependency

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    text = raw.decode("utf-8", errors="replace")
    if "<html" in text[:2000].lower() or hint.lower().endswith((".html", ".htm")):
        text = _SCRIPT_STYLE.sub(" ", text)
        text = re.sub(r"<(br|/p|/div|/li|/tr|/h[1-6])[^>]*>", "\n", text, flags=re.I)
        text = _TAG.sub(" ", text)
        text = html_lib.unescape(text)
    return text


def detect_sections(text: str) -> List[DraftSection]:
    """Heuristically split extracted statute text into numbered sections.

    A line like ``12. Heading text`` starts a section; everything until the
    next such line is its body. The heading is the first sentence of the
    starting line.
    """
    sections: List[DraftSection] = []
    current: Optional[DraftSection] = None
    for line in text.splitlines():
        started = _SECTION_START.match(line)
        if started:
            if current:
                sections.append(current)
            rest = started.group(2).strip()
            heading, _, tail = rest.partition(".")
            current = DraftSection(
                number=started.group(1),
                heading=heading.strip(),
                body=tail.strip(),
            )
        elif current is not None and line.strip():
            current.body = f"{current.body} {line.strip()}".strip()
    if current:
        sections.append(current)
    return sections


def compose_bare_act(
    act_id: str,
    act_name: str,
    year: int,
    act_type: str,
    source_url: str,
    sections: List[DraftSection],
    retrieval_date: Optional[date] = None,
) -> str:
    """The draft source file in the exact header + ``Section N.`` format."""
    header = (
        f"ACT_ID: {act_id}\n"
        f"ACT: {act_name}\n"
        f"YEAR: {year}\n"
        f"TYPE: {act_type}\n"
        f"SOURCE_URL: {source_url}\n"
        f"RETRIEVAL_DATE: {(retrieval_date or date.today()).isoformat()}\n"
        "===\n"
    )
    blocks = [
        f"Section {s.number}. {s.heading}.\n{s.body}\n" for s in sections
    ]
    return header + "\n".join(blocks)


def build_report(
    act_id: str,
    source: str,
    draft_path: Path,
    sections: List[DraftSection],
    parse_ok: bool,
    parse_error: str,
    official_total: Optional[int],
) -> str:
    """The human-review report for one import: findings, samples, and status."""
    suspicious = [
        s.number for s in sections if not s.body or len(s.body) < 40
    ]
    lines = [
        f"# Import report: {act_id}",
        "",
        f"- Source: {source}",
        f"- Draft: {draft_path}",
        f"- Sections detected: {len(sections)}"
        + (
            f" (official total: {official_total})"
            if official_total is not None
            else " (no manifest entry to compare against)"
        ),
        f"- Draft parses as a bare act: {'yes' if parse_ok else f'NO - {parse_error}'}",
        f"- Suspiciously short or empty sections: {', '.join(suspicious) or 'none'}",
        "",
        "## Samples for side-by-side verification",
        "",
        "Compare each sample below against the official source text before",
        "promoting this draft. Statutory text is quoted verbatim in answers,",
        "so any extraction damage here becomes a wrong citation there.",
        "",
    ]
    samples = sections[:3]
    if len(sections) > 4:
        samples.append(sections[-1])
    for section in samples:
        lines.append(f"### Section {section.number}. {section.heading}")
        lines.append("")
        lines.append(section.body[:400] or "(empty)")
        lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("AWAITING HUMAN APPROVAL - review the draft against the official")
    lines.append("source, then move it into data/sources/ and run: python -m ingestion")
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    act_id: str,
    act_name: str,
    year: int,
    act_type: str,
    url: Optional[str] = None,
    file: Optional[Path] = None,
    source_url: Optional[str] = None,
    out: Optional[Path] = None,
) -> Path:
    """Fetch, extract, draft, verify, and report. Returns the draft path."""
    if (url is None) == (file is None):
        raise SystemExit("exactly one of --url or --file is required")
    if url is not None:
        import httpx

        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        raw, origin = response.content, url
    else:
        raw, origin = Path(file).read_bytes(), str(file)

    draft_path = (out or _STAGING / f"{act_id}.txt").resolve()
    if _SOURCES.resolve() in draft_path.parents:
        raise SystemExit(
            "refusing to write into data/sources/ - drafts go to data/staging/ "
            "and a human promotes them after review (ADR 0008)"
        )

    sections = detect_sections(extract_text(raw, hint=origin))
    draft = compose_bare_act(
        act_id, act_name, year, act_type, source_url or url or origin, sections
    )

    parse_ok, parse_error = True, ""
    try:
        parsed = parse_act(draft)
        parse_ok = len(parsed.sections) == len(sections)
        if not parse_ok:
            parse_error = (
                f"parser found {len(parsed.sections)} sections, tool drafted {len(sections)}"
            )
    except Exception as exc:
        parse_ok, parse_error = False, f"{type(exc).__name__}: {exc}"

    official_total: Optional[int] = None
    manifest_path = _ROOT / "data" / "ground_truth" / "manifest.json"
    if manifest_path.exists():
        import json

        acts = json.loads(manifest_path.read_text()).get("acts", {})
        if act_id in acts:
            official_total = acts[act_id].get("official_total_sections")

    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(draft)
    report_path = _ARTIFACTS / f"import_report_{act_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_report(
            act_id, origin, draft_path, sections, parse_ok, parse_error, official_total
        )
    )
    print(f"Draft written:  {draft_path}")
    print(f"Report written: {report_path}")
    print("Status: AWAITING HUMAN APPROVAL")
    return draft_path


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ingestion.import_assist")
    parser.add_argument("--url", help="fetch the statute from this URL")
    parser.add_argument("--file", type=Path, help="read the statute from a local file")
    parser.add_argument("--act-id", required=True)
    parser.add_argument("--act-name", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--type", dest="act_type", required=True)
    parser.add_argument(
        "--source-url",
        help="provenance URL recorded in the header (defaults to --url)",
    )
    parser.add_argument("--out", type=Path, help="draft path (default data/staging/)")
    args = parser.parse_args(argv)
    run(
        act_id=args.act_id,
        act_name=args.act_name,
        year=args.year,
        act_type=args.act_type,
        url=args.url,
        file=args.file,
        source_url=args.source_url,
        out=args.out,
    )


if __name__ == "__main__":
    main()
