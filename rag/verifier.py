"""Citation verification.

A programmatic check that every section the generator cited actually exists in
the retrieved chunks. Anything not retrieved is treated as a hallucination and
stripped; an answer left with no surviving Citation cannot stand and is refused
upstream. This is the backstop that keeps a fluent guess from masquerading as a
Grounded Answer.
"""
from __future__ import annotations

from typing import List, Sequence

from rag.citation import Citation
from rag.expansion import RetrievedSection


def retrieved_sections_index(sections: Sequence[RetrievedSection]) -> set:
    """The ``(act_id, section_number)`` pairs actually retrieved."""
    return {(s.act_id, s.section_number) for s in sections}


def verify_citations(
    citations: Sequence[Citation], sections: Sequence[RetrievedSection]
) -> List[Citation]:
    """Keep only Citations whose section is present in the retrieved chunks."""
    allowed = retrieved_sections_index(sections)
    return [c for c in citations if (c.act_id, c.section_number) in allowed]
