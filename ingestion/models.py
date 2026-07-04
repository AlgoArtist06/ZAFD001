"""Domain models for the Phase 0 ingestion module.

The vocabulary here follows ``CONTEXT.md``: a :class:`ProvenanceRecord` is the
mandatory metadata that makes a Citation traceable to a government Source of
Truth, and the hard rule is *no provenance, no answer* - enforced at the data
layer via :meth:`Chunk.is_loadable`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


class ActType(str, Enum):
    """The kind of Source of Truth a chunk belongs to."""

    CRIMINAL = "criminal"
    CONSUMER = "consumer"
    IP = "ip"
    CONSTITUTIONAL = "constitutional"
    SCHEME = "scheme"
    CYBER = "cyber"
    TRANSPORT = "transport"
    GOVERNANCE = "governance"
    PROTECTION = "protection"


@dataclass(frozen=True)
class AmendmentEntry:
    """A single recorded amendment to a section."""

    year: int
    description: str
    citation: Optional[str] = None


@dataclass
class AmendmentHistory:
    """Amendment History captured alongside a section's Provenance Record.

    "Captured" means the ingestion explicitly recorded the amendment state -
    either a non-empty list of entries, or an explicit ``none_recorded`` flag
    meaning the section has no amendments. An empty, unflagged history means the
    ingestion never looked, which fails the "captured per section" criterion.
    """

    entries: List[AmendmentEntry] = field(default_factory=list)
    none_recorded: bool = False

    def is_captured(self) -> bool:
        return bool(self.entries) or self.none_recorded


@dataclass
class ProvenanceRecord:
    """Mandatory metadata that makes a chunk citable in a court of justice.

    Statutory chunks require a ``section_number``; scheme chunks instead require
    a ``governing_authority`` and ``scheme_url`` in its place.
    """

    act_name: str
    act_year: int
    act_type: ActType
    source_url: str
    source_hash: str
    retrieval_date: date
    verbatim_text: str
    section_number: Optional[str] = None
    sub_section: Optional[str] = None
    governing_authority: Optional[str] = None
    scheme_url: Optional[str] = None

    def is_complete(self) -> bool:
        common = all(
            [
                self.act_name,
                self.act_year,
                self.act_type,
                self.source_url,
                self.source_hash,
                self.retrieval_date,
                self.verbatim_text,
            ]
        )
        if not common:
            return False
        if self.act_type == ActType.SCHEME:
            return bool(self.governing_authority and self.scheme_url)
        return bool(self.section_number)

    def missing_fields(self) -> List[str]:
        missing = [
            name
            for name in (
                "act_name",
                "act_year",
                "act_type",
                "source_url",
                "source_hash",
                "retrieval_date",
                "verbatim_text",
            )
            if not getattr(self, name)
        ]
        if self.act_type == ActType.SCHEME:
            if not self.governing_authority:
                missing.append("governing_authority")
            if not self.scheme_url:
                missing.append("scheme_url")
        elif not self.section_number:
            missing.append("section_number")
        return missing


@dataclass
class Chunk:
    """The unit produced by the pipeline and (if loadable) embedded into the
    vector store. Children of a large section carry a ``parent_section_id``."""

    chunk_id: str
    act_id: str
    text: str
    provenance: ProvenanceRecord
    amendment_history: AmendmentHistory
    section_number: Optional[str] = None
    sub_section: Optional[str] = None
    parent_section_id: Optional[str] = None
    is_definition: bool = False
    token_estimate: int = 0

    def is_child(self) -> bool:
        return self.parent_section_id is not None

    def is_loadable(self) -> bool:
        """No provenance, no answer: only fully-provenanced chunks load."""
        return self.provenance.is_complete()
