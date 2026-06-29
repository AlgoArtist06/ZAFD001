"""Parent-section and sibling expansion.

The embedding/retrieval unit is the small sub-section chunk, so a hit may be a
single child of a larger section. Before generation we expand each hit up to its
whole parent section (all sibling sub-sections), so the model always sees the
complete legal context - provisos and exceptions included - while the Citation
stays at section level. Parent reconstruction is a query-time lookup over the
corpus; sub-section text is never duplicated at rest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from ingestion.models import ProvenanceRecord, Chunk
from rag.retrieval import RetrievalHit


@dataclass
class RetrievedSection:
    """A whole section reassembled from its sibling chunks, with the best
    retrieval score among the chunks that matched."""

    act_id: str
    section_number: str
    chunks: List[Chunk]
    score: float

    @property
    def provenance(self) -> ProvenanceRecord:
        return self.chunks[0].provenance

    @property
    def verbatim_text(self) -> str:
        """The section's Verbatim Text, sub-sections in order."""
        return " ".join(c.text for c in self.chunks).strip()

    @property
    def is_expanded(self) -> bool:
        """True when sibling sub-sections were pulled in around the hit."""
        return len(self.chunks) > 1


def _section_members(corpus: Sequence[Chunk], act_id: str, section_number: str) -> List[Chunk]:
    members = [
        c for c in corpus if c.act_id == act_id and c.section_number == section_number
    ]
    members.sort(key=lambda c: (c.sub_section or ""))
    return members


def expand(hits: Sequence[RetrievalHit], corpus: Sequence[Chunk]) -> List[RetrievedSection]:
    """Group hits into whole sections, pulling in sibling sub-sections."""
    sections: dict[tuple[str, str], RetrievedSection] = {}
    for hit in hits:
        key = (hit.chunk.act_id, hit.chunk.section_number)
        if key in sections:
            sections[key].score = max(sections[key].score, hit.score)
            continue
        members = _section_members(corpus, key[0], key[1])
        sections[key] = RetrievedSection(
            act_id=key[0],
            section_number=key[1],
            chunks=members,
            score=hit.score,
        )
    return sorted(sections.values(), key=lambda s: s.score, reverse=True)
