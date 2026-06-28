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
from typing import List, Optional, Protocol, Sequence

from ingestion.models import ActType
from rag.citation import Citation
from rag.expansion import RetrievedSection
from rag.multilingual import HINDI, BilingualGlossary

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

# The Hindi Disclaimer keeps the Legal-Aid Pointer (NALSA / DLSA) recognisable.
_DISCLAIMER_HI = (
    "यह कानूनी जानकारी है, कानूनी सलाह नहीं। अपनी विशिष्ट स्थिति में सहायता के लिए "
    "किसी वकील या अपने निकटतम विधिक सेवा प्राधिकरण (NALSA / DLSA) से संपर्क करें।"
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

    Generation honours the answer ``language``: for a Supported Language other than
    English it frames the answer in that language, with the Bilingual Legal Glossary
    constraining the critical terms (rendered in the target language with the
    English term inline in brackets). The Citation Anchor stays verbatim English in
    every language, since it must remain court-traceable.
    """

    def __init__(self, glossary: Optional[BilingualGlossary] = None):
        # The same glossary that normalises a query to English also constrains the
        # terminology on the way back out.
        self._glossary = glossary or BilingualGlossary.load()

    def generate(
        self, query: str, sections: Sequence[RetrievedSection], mode: str, language: str
    ) -> DraftAnswer:
        if mode == PROFESSIONAL:
            return self._professional(sections, language)
        return self._citizen(sections, language)

    def _citizen(
        self, sections: Sequence[RetrievedSection], language: str
    ) -> DraftAnswer:
        top = sections[0]
        citation = Citation.from_section(top)
        domain_label = _DOMAIN_LABEL.get(top.provenance.act_type, "the law")

        if language == HINDI:
            domain = self._glossary.render(domain_label, HINDI)
            explanation = (
                f"सरल भाषा में, आपका प्रश्न भारत में {domain} से संबंधित है। नीचे बताया "
                "गया है कि कानून स्वयं क्या कहता है, और उसके बाद वह सटीक प्रावधान दिया "
                "गया है जिससे यह लिया गया है।"
            )
            legal_basis = f"कानूनी आधार (Legal basis) - {citation.anchor}"
            next_step = (
                "व्यावहारिक अगला कदम: ऊपर उद्धृत प्रावधान को पढ़ें, संबंधित दस्तावेज़ या "
                "साक्ष्य संभाल कर रखें, और उसमें नामित उपयुक्त कार्यालय या प्राधिकरण से "
                "संपर्क करें।"
            )
            return DraftAnswer(
                explanation=explanation,
                legal_basis=legal_basis,
                next_step=next_step,
                citations=[citation],
                disclaimer=_DISCLAIMER_HI,
            )

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

    def _professional(
        self, sections: Sequence[RetrievedSection], language: str
    ) -> DraftAnswer:
        # Dense: cite every grounded section, in retrieval order, statutory terms.
        citations = [Citation.from_section(s) for s in sections]
        legal_basis = "\n".join(c.anchor for c in citations)
        explanation = "लागू प्रावधान:" if language == HINDI else "Applicable provisions:"
        return DraftAnswer(
            explanation=explanation,
            legal_basis=legal_basis,
            next_step="",
            citations=citations,
            disclaimer=_DISCLAIMER_HI if language == HINDI else _DISCLAIMER,
        )
