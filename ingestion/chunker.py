"""Adaptive hierarchical chunking.

A section under the token threshold is stored as one whole chunk. A larger
section is split into per-sub-section child chunks that each carry a
``parent_section_id``; sub-section text is stored once (parent expansion is a
query-time concern, out of scope for ingestion).
"""
from __future__ import annotations

from typing import List

from ingestion.models import (
    AmendmentHistory,
    Chunk,
    ProvenanceRecord,
)
from ingestion.parser import ParsedAct, Section


def estimate_tokens(text: str) -> int:
    """Cheap, monotonic token estimate (whitespace words)."""
    return len(text.split())


def section_id(act_id: str, section_number: str) -> str:
    return f"{act_id}-{section_number}"


def _provenance(act: ParsedAct, section: Section, verbatim: str, sub_section=None):
    return ProvenanceRecord(
        act_name=act.act_name,
        act_year=act.act_year,
        act_type=act.act_type,
        source_url=act.source_url,
        source_hash=act.source_hash,
        retrieval_date=act.retrieval_date,
        verbatim_text=verbatim,
        section_number=section.section_number,
        sub_section=sub_section,
    )


def _amendment_history(section: Section) -> AmendmentHistory:
    return AmendmentHistory(
        entries=list(section.amendments),
        none_recorded=not section.amendments,
    )


def chunk_section(act: ParsedAct, section: Section, token_threshold: int) -> List[Chunk]:
    parent_id = section_id(act.act_id, section.section_number)
    whole = section.full_text
    if estimate_tokens(whole) <= token_threshold or not section.sub_sections:
        return [
            Chunk(
                chunk_id=parent_id,
                act_id=act.act_id,
                section_number=section.section_number,
                text=whole,
                provenance=_provenance(act, section, whole),
                amendment_history=_amendment_history(section),
                is_definition=section.is_definition,
                token_estimate=estimate_tokens(whole),
            )
        ]

    children: List[Chunk] = []
    for sub in section.sub_sections:
        children.append(
            Chunk(
                chunk_id=f"{parent_id}-{sub.label}",
                act_id=act.act_id,
                section_number=section.section_number,
                sub_section=sub.label,
                parent_section_id=parent_id,
                text=sub.text,
                provenance=_provenance(act, section, sub.text, sub_section=sub.label),
                amendment_history=_amendment_history(section),
                is_definition=section.is_definition,
                token_estimate=estimate_tokens(sub.text),
            )
        )
    return children


def chunk_act(act: ParsedAct, token_threshold: int = 512) -> List[Chunk]:
    chunks: List[Chunk] = []
    for section in act.sections:
        chunks.extend(chunk_section(act, section, token_threshold))
    return chunks
