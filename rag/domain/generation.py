"""Grounded generation.

Generation runs under a hard contract: answer only from retrieved Source of
Truth text, attach a Citation to every claim, and never invent a section. The
only production implementation of the :class:`Generator` protocol is the live
:class:`rag.infrastructure.llm.OpenAICompatibleGenerator` (ADR 0010); the test
suite injects its own doubles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, Sequence

from rag.domain.citation import Citation
from rag.domain.expansion import RetrievedSection

_DISCLAIMER = (
    "This is legal information, not legal advice. For help with your specific "
    "situation, consult a lawyer or your nearest Legal Services Authority "
    "(NALSA / DLSA)."
)


@dataclass
class DraftAnswer:
    """A grounded draft: the three structured parts plus its Citations."""

    explanation: str
    legal_basis: str
    next_step: str
    citations: List[Citation] = field(default_factory=list)
    disclaimer: str = _DISCLAIMER


class Generator(Protocol):
    def generate(
        self, query: str, sections: Sequence[RetrievedSection], language: str
    ) -> DraftAnswer: ...


@dataclass(frozen=True)
class ExplanationSoFar:
    """A streaming generator's cumulative explanation text, mid-generation.

    A generator that supports token streaming exposes an additional
    ``stream(query, sections, language)`` async iterator that yields
    these as the explanation grows - each carries the full text so far, not a
    delta - and finishes with the complete :class:`DraftAnswer`. Generators
    without ``stream`` (test doubles) are served by running ``generate``
    whole; the seam stays optional so the offline suite never touches asyncio.
    """

    text: str
