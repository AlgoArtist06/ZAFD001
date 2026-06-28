"""The consolidated Phase 0 checkpoint artifact.

After the agent-autonomous build, there is exactly one human checkpoint: the
user reviews 30 to 50 sample sections side-by-side with their official source
links, plus the coverage and test report, in a single sitting and approves
before Phase 1 begins. This module renders that artifact; it never auto-approves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ingestion.pipeline import IngestionResult


@dataclass
class SampleSection:
    citation: str
    source_url: str
    verbatim: str


def sample_sections(result: IngestionResult, limit: int = 50) -> List[SampleSection]:
    """One row per ingested statutory section (children folded into their parent)."""
    by_section: Dict[tuple, SampleSection] = {}
    for chunk in result.chunks:
        if chunk.section_number is None:
            continue  # schemes are summarised separately
        key = (chunk.act_id, chunk.section_number)
        prov = chunk.provenance
        citation = f"{prov.act_name} {prov.act_year}, s. {chunk.section_number}"
        if key not in by_section:
            by_section[key] = SampleSection(
                citation=citation, source_url=prov.source_url, verbatim=chunk.text
            )
        else:
            by_section[key].verbatim += " " + chunk.text
    return list(by_section.values())[:limit]


def build_checkpoint(result: IngestionResult) -> str:
    cov = result.coverage
    lines: List[str] = []
    lines.append("# Phase 0 Checkpoint - Ingestion Source of Truth")
    lines.append("")
    lines.append("Status: AWAITING HUMAN APPROVAL")
    lines.append("")
    lines.append(
        "Review the sample sections against their official source links, then the "
        "coverage and test report. No downstream (Phase 1 RAG) work begins until "
        "this artifact is approved."
    )
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append("| Act | Ingested | In-scope target | Coverage | Official total | Uncovered remainder (logged) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for act_id, a in cov.per_act.items():
        lines.append(
            f"| {act_id} | {a.ingested} | {a.in_scope_target} | "
            f"{a.coverage:.0%} | {a.official_total} | {a.uncovered_remainder} |"
        )
    lines.append(f"| **overall** | | | **{cov.overall_coverage:.0%}** | | |")
    lines.append("")

    lines.append("## Test / structural report")
    lines.append("")
    lines.append(f"- Chunks loaded (complete provenance): {len(result.chunks)}")
    lines.append(f"- Chunks flagged and withheld (no provenance, no answer): {len(result.validation.flagged)}")
    lines.append(f"- Orphaned child chunks: {len(result.validation.orphaned_children)}")
    lines.append(f"- Section gaps flagged: {len(result.validation.section_gaps)}")
    lines.append(f"- IPC-to-BNS Mapping verified against official chart: {result.mapping_verified}")
    lines.append(f"- Landmark judgments curated (full citations): {len(result.landmarks)}")
    lines.append(f"- Coverage gate (>= 80%): {cov.meets_threshold(0.80)}")
    lines.append("")

    lines.append("## Sample sections (side-by-side with official source)")
    lines.append("")
    for s in sample_sections(result):
        lines.append(f"### {s.citation}")
        lines.append(f"Source: {s.source_url}")
        lines.append("")
        lines.append(f"> {s.verbatim}")
        lines.append("")

    return "\n".join(lines)
