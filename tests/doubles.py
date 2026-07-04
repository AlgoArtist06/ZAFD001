"""Test doubles for the live-only seams.

The product has no offline mode: generation, intent extraction, and embeddings
are always live adapters, selected in :mod:`rag.composition` (ADR 0010). The
suite still runs with no services because these doubles implement the same
protocols deterministically - they are TEST equipment, deliberately outside the
product packages so nothing in production can ever fall back to them.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ingestion.models import ActType, Chunk
from rag.domain.answer import LegalAssistant
from rag.domain.citation import Citation
from rag.domain.expansion import RetrievedSection
from rag.domain.generation import DraftAnswer
from rag.domain.multilingual import (
    GUJARATI,
    HINDI,
    TAMIL,
    BilingualGlossary,
    NormalizedQuery,
    detect_language,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Hashing bag-of-words embedder with L2-normalised vectors.

    Good enough for keyword-overlap retrieval in tests; carries no model
    weights and makes no network calls.
    """

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm:
            vec = [v / norm for v in vec]
        return vec


class GlossaryIntentExtractor:
    """Script-based detection and glossary lookup behind the intent seam."""

    def __init__(self, glossary: BilingualGlossary):
        self._glossary = glossary

    def normalize(self, query: str) -> NormalizedQuery:
        return NormalizedQuery(
            language=detect_language(query),
            english_query=self._glossary.to_english(query),
        )


# Plain-language label for each Covered Domain, used by the template framing.
_DOMAIN_LABEL = {
    ActType.CRIMINAL: "criminal law",
    ActType.CONSUMER: "consumer protection law",
    ActType.IP: "intellectual property law",
    ActType.CONSTITUTIONAL: "your fundamental rights",
    ActType.SCHEME: "government schemes",
    ActType.CYBER: "cyber law",
    ActType.TRANSPORT: "motor vehicle and traffic law",
    ActType.GOVERNANCE: "the right to information",
    ActType.PROTECTION: "protection from domestic violence and workplace harassment",
}


@dataclass(frozen=True)
class _LanguageCopy:
    """The per-language frame around the citation, kept court-traceable."""

    explanation: str
    legal_basis_label: str
    next_step: str
    disclaimer: str


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
    ),
}


class TemplateGenerator:
    """Template generator that only ever cites the sections it was handed.

    Answers in plain step-by-step language around a single focused Citation.
    Generation honours the answer ``language`` with the Bilingual Legal Glossary
    constraining the critical terms; the Citation Anchor stays verbatim English
    in every language.
    """

    def __init__(self, glossary: Optional[BilingualGlossary] = None):
        self._glossary = glossary or BilingualGlossary.load()

    def generate(
        self, query: str, sections: Sequence[RetrievedSection], language: str
    ) -> DraftAnswer:
        top = sections[0]
        citation = Citation.from_section(top)
        domain_label = _DOMAIN_LABEL.get(top.provenance.act_type, "the law")
        copy = _COPY.get(language)

        if copy is not None:
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


def offline_assistant(chunks: Sequence[Chunk], **overrides) -> LegalAssistant:
    """A LegalAssistant wired entirely with deterministic test doubles.

    Any seam can be overridden per test (``generator=``, ``embedder=``, ...);
    the rest stay deterministic so the suite needs no services.
    """
    glossary = overrides.pop("glossary", None) or BilingualGlossary.load()
    kwargs = dict(
        embedder=HashEmbedder(),
        generator=TemplateGenerator(glossary),
        intent_extractor=GlossaryIntentExtractor(glossary),
        glossary=glossary,
    )
    kwargs.update(overrides)
    return LegalAssistant(chunks, **kwargs)
