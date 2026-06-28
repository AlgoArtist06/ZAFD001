"""Parser tuned to the v1 in-scope acts.

The input is a lightly-structured bare-act text file (the "structure-detect"
stage's output of the download/extract steps). A header block carries act-level
provenance; the body is a sequence of ``Section N. Heading.`` (or ``Article N.``)
blocks, each optionally split into ``(n)`` sub-sections and annotated with
``@AMENDMENT year: ...`` lines.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List

from ingestion.models import ActType, AmendmentEntry

_SECTION_RE = re.compile(r"^(?:Section|Article)\s+([0-9A-Za-z]+)\.\s*(.*)$")
_SUBSECTION_RE = re.compile(r"^\((\w+)\)\s*(.*)$")
_AMENDMENT_RE = re.compile(r"^@AMENDMENT\s+(\d{4}):\s*(.*)$")


@dataclass
class SubSection:
    label: str
    text: str


@dataclass
class Section:
    section_number: str
    heading: str
    full_text: str
    sub_sections: List[SubSection] = field(default_factory=list)
    amendments: List[AmendmentEntry] = field(default_factory=list)
    is_definition: bool = False


@dataclass
class ParsedAct:
    act_id: str
    act_name: str
    act_year: int
    act_type: ActType
    source_url: str
    retrieval_date: date
    source_hash: str
    sections: List[Section] = field(default_factory=list)


def _split_header(text: str):
    header_raw, _, body = text.partition("===")
    header = {}
    for line in header_raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            header[key.strip().upper()] = value.strip()
    return header, body


def _flush_subsections(buffer_lines: List[str]) -> List[SubSection]:
    """Turn a block of body lines into sub-sections, if any ``(n)`` markers."""
    subs: List[SubSection] = []
    current: SubSection | None = None
    for line in buffer_lines:
        match = _SUBSECTION_RE.match(line.strip())
        if match:
            current = SubSection(label=match.group(1), text=match.group(2).strip())
            subs.append(current)
        elif current is not None:
            current.text = (current.text + " " + line.strip()).strip()
    return subs


def parse_act(text: str) -> ParsedAct:
    header, body = _split_header(text)
    act = ParsedAct(
        act_id=header["ACT_ID"],
        act_name=header["ACT"],
        act_year=int(header["YEAR"]),
        act_type=ActType(header["TYPE"].lower()),
        source_url=header["SOURCE_URL"],
        retrieval_date=date.fromisoformat(header["RETRIEVAL_DATE"]),
        source_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )

    section: Section | None = None
    body_lines: List[str] = []

    def close_section() -> None:
        if section is None:
            return
        # Reflow soft source line-wraps into clean single-spaced verbatim text.
        section.full_text = re.sub(r"\s+", " ", " ".join(body_lines)).strip()
        section.sub_sections = _flush_subsections(body_lines)
        act.sections.append(section)

    for raw in body.splitlines():
        line = raw.rstrip()
        header_match = _SECTION_RE.match(line.strip())
        amendment_match = _AMENDMENT_RE.match(line.strip())
        if header_match:
            close_section()
            number, heading = header_match.group(1), header_match.group(2).strip()
            section = Section(
                section_number=number,
                heading=heading,
                full_text="",
                is_definition="definition" in heading.lower(),
            )
            body_lines = []
        elif amendment_match and section is not None:
            section.amendments.append(
                AmendmentEntry(
                    year=int(amendment_match.group(1)),
                    description=amendment_match.group(2).strip(),
                )
            )
        elif section is not None:
            body_lines.append(line)

    close_section()
    return act
