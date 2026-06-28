"""The Phase 0 validation gate.

Partitions chunks into loadable (complete Provenance Record) and flagged
(incomplete - never loaded), and checks structural integrity: no orphaned child
chunks, every parent link resolves, section gaps flagged (logged, not fatal).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ingestion.chunker import section_id
from ingestion.models import Chunk


@dataclass
class Flag:
    chunk_id: str
    reasons: List[str]


@dataclass
class ValidationReport:
    loadable: List[Chunk] = field(default_factory=list)
    flagged: List[Flag] = field(default_factory=list)
    orphaned_children: List[str] = field(default_factory=list)
    section_gaps: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def structural_ok(self) -> bool:
        return not self.orphaned_children


def _section_gaps(chunks: List[Chunk]) -> List[Tuple[str, str]]:
    by_act: Dict[str, set] = {}
    for chunk in chunks:
        if chunk.section_number and chunk.section_number.isdigit():
            by_act.setdefault(chunk.act_id, set()).add(int(chunk.section_number))
    gaps: List[Tuple[str, str]] = []
    for act_id, numbers in by_act.items():
        for missing in range(min(numbers), max(numbers) + 1):
            if missing not in numbers:
                gaps.append((act_id, str(missing)))
    return gaps


def validate_chunks(chunks: List[Chunk]) -> ValidationReport:
    report = ValidationReport()

    valid_section_ids = {
        section_id(c.act_id, c.section_number)
        for c in chunks
        if c.section_number is not None
    }

    for chunk in chunks:
        if not chunk.is_loadable():
            report.flagged.append(
                Flag(chunk_id=chunk.chunk_id, reasons=chunk.provenance.missing_fields())
            )
            continue
        if chunk.is_child() and chunk.parent_section_id not in valid_section_ids:
            report.orphaned_children.append(chunk.chunk_id)
            continue
        report.loadable.append(chunk)

    report.section_gaps = _section_gaps(chunks)
    return report
