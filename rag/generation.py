"""Grounded generation.

Generation runs under a hard contract: answer only from retrieved Source of
Truth text, attach a Citation to every claim, and never invent a section. The
default :class:`DeterministicGenerator` is offline and template-based so the
suite needs no LLM; production swaps in Google Gemini 2.5 Flash via its
OpenAI-compatible endpoint behind the same :class:`Generator` protocol, exactly
as the vector store swaps a real embedder behind :class:`Embedder`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence

from ingestion.models import ActType
from rag.citation import Citation
from rag.expansion import RetrievedSection
from rag.multilingual import GUJARATI, HINDI, TAMIL, BilingualGlossary

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


@dataclass(frozen=True)
class _LanguageCopy:
    """The per-language frame around the citation, kept court-traceable.

    Each Supported Language fills the same slots: the Citizen-mode explanation
    (with a ``{domain}`` placeholder for the rendered domain term), the labels that
    front the Citation Anchor in each Mode, the practical next step, the Disclaimer,
    and the Professional-mode heading. The Citation Anchor itself is never
    translated. Adding a language is adding one entry here plus its glossary column.
    """

    explanation: str
    legal_basis_label: str
    next_step: str
    disclaimer: str
    professional_heading: str


# The Legal-Aid Pointer (NALSA / DLSA) stays recognisable in every Disclaimer.
_COPY: Dict[str, _LanguageCopy] = {
    HINDI: _LanguageCopy(
        explanation=(
            "सरल भाषा में, आपका प्रश्न भारत में {domain} से संबंधित है। नीचे बताया "
            "गया है कि कानून स्वयं क्या कहता है, और उसके बाद वह सटीक प्रावधान दिया "
            "गया है जिससे यह लिया गया है।"
        ),
        legal_basis_label="कानूनी आधार (Legal basis)",
        next_step=(
            "व्यावहारिक अगला कदम: ऊपर उद्धृत प्रावधान को पढ़ें, संबंधित दस्तावेज़ या "
            "साक्ष्य संभाल कर रखें, और उसमें नामित उपयुक्त कार्यालय या प्राधिकरण से "
            "संपर्क करें।"
        ),
        disclaimer=(
            "यह कानूनी जानकारी है, कानूनी सलाह नहीं। अपनी विशिष्ट स्थिति में सहायता के "
            "लिए किसी वकील या अपने निकटतम विधिक सेवा प्राधिकरण (NALSA / DLSA) से "
            "संपर्क करें।"
        ),
        professional_heading="लागू प्रावधान:",
    ),
    TAMIL: _LanguageCopy(
        explanation=(
            "எளிய மொழியில், உங்கள் கேள்வி இந்தியாவில் {domain} தொடர்பானது. சட்டம் "
            "என்ன கூறுகிறது என்பது கீழே உள்ளது, அதைத் தொடர்ந்து அது எடுக்கப்பட்ட "
            "சரியான விதி கொடுக்கப்பட்டுள்ளது."
        ),
        legal_basis_label="சட்ட அடிப்படை (Legal basis)",
        next_step=(
            "நடைமுறை அடுத்த படி: மேலே மேற்கோள் காட்டப்பட்ட விதியைப் படியுங்கள், "
            "தொடர்புடைய ஆவணங்கள் அல்லது சான்றுகளைப் பாதுகாப்பாக வைத்திருங்கள், அதில் "
            "குறிப்பிடப்பட்ட பொருத்தமான அலுவலகம் அல்லது அதிகாரத்தை அணுகவும்."
        ),
        disclaimer=(
            "இது சட்டத் தகவல், சட்ட ஆலோசனை அல்ல. உங்கள் குறிப்பிட்ட சூழ்நிலையில் "
            "உதவிக்கு, ஒரு வழக்கறிஞரை அல்லது உங்கள் அருகிலுள்ள சட்ட சேவை ஆணையத்தை "
            "(NALSA / DLSA) அணுகவும்."
        ),
        professional_heading="பொருந்தும் விதிகள்:",
    ),
    GUJARATI: _LanguageCopy(
        explanation=(
            "સરળ ભાષામાં, તમારો પ્રશ્ન ભારતમાં {domain} સંબંધિત છે. કાયદો પોતે શું "
            "કહે છે તે નીચે આપેલ છે, ત્યારબાદ તે જે ચોક્કસ જોગવાઈમાંથી આવે છે તે "
            "આપેલ છે."
        ),
        legal_basis_label="કાનૂની આધાર (Legal basis)",
        next_step=(
            "વ્યવહારુ આગળનું પગલું: ઉપર ટાંકેલ જોગવાઈ વાંચો, સંબંધિત દસ્તાવેજો અથવા "
            "પુરાવા સાચવી રાખો, અને તેમાં દર્શાવેલ યોગ્ય કચેરી અથવા સત્તાધિકારીનો "
            "સંપર્ક કરો."
        ),
        disclaimer=(
            "આ કાનૂની માહિતી છે, કાનૂની સલાહ નથી. તમારી ચોક્કસ પરિસ્થિતિમાં મદદ માટે, "
            "વકીલનો અથવા તમારી નજીકના કાનૂની સેવા સત્તામંડળ (NALSA / DLSA) નો સંપર્ક "
            "કરો."
        ),
        professional_heading="લાગુ જોગવાઈઓ:",
    ),
}


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
        copy = _COPY.get(language)

        if copy is not None:
            # A Supported Language other than English: frame in that language, with
            # the domain term rendered as "<term> (<english>)" by the glossary.
            domain = self._glossary.render(domain_label, language)
            return DraftAnswer(
                explanation=copy.explanation.format(domain=domain),
                legal_basis=f"{copy.legal_basis_label} - {citation.anchor}",
                next_step=copy.next_step,
                citations=[citation],
                disclaimer=copy.disclaimer,
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
        copy = _COPY.get(language)
        return DraftAnswer(
            explanation=copy.professional_heading if copy else "Applicable provisions:",
            legal_basis=legal_basis,
            next_step="",
            citations=citations,
            disclaimer=copy.disclaimer if copy else _DISCLAIMER,
        )
