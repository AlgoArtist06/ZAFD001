"""Grounded generation.

Generation runs under a hard contract: answer only from retrieved Source of
Truth text, attach a Citation to every claim, and never invent a section. The
default :class:`DeterministicGenerator` is offline and template-based so the
suite needs no LLM; production swaps in a Claude-backed generator (claude-opus)
behind the same :class:`Generator` protocol, exactly as the vector store swaps a
real embedder behind :class:`Embedder`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, Sequence

from ingestion.models import ActType
from rag.citation import Citation
from rag.expansion import RetrievedSection

# Plain-language label for each Covered Domain, used by the Citizen-mode framing.
_DOMAIN_LABEL = {
    ActType.CRIMINAL: "criminal law",
    ActType.CONSUMER: "consumer protection law",
    ActType.IP: "intellectual property law",
    ActType.CONSTITUTIONAL: "your fundamental rights",
    ActType.SCHEME: "government schemes",
}

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
        self, query: str, sections: Sequence[RetrievedSection], mode: str, language: str
    ) -> DraftAnswer: ...


PROFESSIONAL = "professional"


class DeterministicGenerator:
    """Template generator that only ever cites the sections it was handed.

    Both Modes draw on the same retrieved sections; they differ only in framing.
    Citizen Mode answers in plain step-by-step language around a single focused
    Citation; Professional Mode answers tersely and densely cites every grounded
    section in statutory terms.
    """

    def generate(
        self, query: str, sections: Sequence[RetrievedSection], mode: str, language: str
    ) -> DraftAnswer:
        if mode == PROFESSIONAL:
            return self._professional(sections)
        return self._citizen(sections)

    def _citizen(self, sections: Sequence[RetrievedSection]) -> DraftAnswer:
        top = sections[0]
        citation = Citation.from_section(top)
        domain_label = _DOMAIN_LABEL.get(top.provenance.act_type, "the law")

        explanation = (
            f"In plain language, your question is about {domain_label} in India. "
            "Here is what the law itself says, followed by the exact provision it "
            "comes from."
        )
        legal_basis = f"Legal basis - {citation.anchor}"
        next_step = (
            "Practical next step: read the cited provision above, keep any "
            "relevant documents or evidence, and approach the appropriate office "
            "or authority named in it."
        )
        return DraftAnswer(
            explanation=explanation,
            legal_basis=legal_basis,
            next_step=next_step,
            citations=[citation],
        )

    def _professional(self, sections: Sequence[RetrievedSection]) -> DraftAnswer:
        # Dense: cite every grounded section, in retrieval order, statutory terms.
        citations = [Citation.from_section(s) for s in sections]
        legal_basis = "\n".join(c.anchor for c in citations)
        return DraftAnswer(
            explanation="Applicable provisions:",
            legal_basis=legal_basis,
            next_step="",
            citations=citations,
        )
