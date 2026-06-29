"""The multilingual answering layer: Hindi, Tamil, and Gujarati.

The product serves several Supported Languages over one English Source of Truth.
This module is the seam that lets it: it detects the user's language, extracts the
query's intent into an English string with legal terms preserved (so retrieval and
reasoning always run over the single English corpus), and renders critical terms
back into the user's language for the answer.

The Bilingual Legal Glossary is the deterministic backbone here: the same curated
table both normalises an incoming (or code-mixed) query to English and constrains
the terminology in the output, so a term like bailable versus non-bailable cannot
flip meaning in translation. The layer is data-driven by language code - adding a
language is adding a script row and a glossary column, not new branches - and it
flags terms whose translation lacks an official source, the known soft spot for
lower-resource languages like Tamil and Gujarati. Production swaps a Claude-backed
(claude-opus) intent extractor and generator behind these same functions; the
offline default below keeps the suite deterministic, exactly like the embedder and
generator seams.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from rag.text import content_stems

ENGLISH = "en"
HINDI = "hi"
TAMIL = "ta"
GUJARATI = "gu"

_GLOSSARY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "glossary.json"
)

# Each non-English Supported Language writes in its own Unicode block, and that
# script is what marks a query as that language rather than English. Code-mixing
# (e.g. Hinglish) still trips the right script as long as any word is in it; the
# Latin-script tokens around it are preserved verbatim. Detection walks these in
# order, so adding a language is adding one row here and its glossary column.
_SCRIPTS: Sequence[tuple] = (
    (HINDI, re.compile(r"[ऀ-ॿ]")),  # Devanagari
    (TAMIL, re.compile(r"[஀-௿]")),  # Tamil
    (GUJARATI, re.compile(r"[઀-૿]")),  # Gujarati
)

# Any supported non-Latin script: a token carrying one is a foreign-script word.
# Used to drop function words the glossary does not carry once legal terms have
# been mapped to English, so retrieval always runs over English-only text.
_FOREIGN_RE = re.compile(
    "|".join(pattern.pattern for _, pattern in _SCRIPTS)
)


@dataclass(frozen=True)
class GlossaryEntry:
    """One critical legal term and its equivalents across Supported Languages.

    ``by_language`` maps a Supported Language code to the term in that language.
    ``unverified`` names the languages whose translation lacks an official
    central-act source and is therefore flagged for review.
    """

    en: str
    by_language: Dict[str, str]
    unverified: frozenset = frozenset()


def detect_language(query: str) -> str:
    """Detect the user's language from the raw query.

    Returns the code of the first Supported Language whose script appears in the
    query (including code-mixed queries), otherwise ``"en"``. Detection drives the
    language of the answer.
    """
    for language, pattern in _SCRIPTS:
        if pattern.search(query):
            return language
    return ENGLISH


class BilingualGlossary:
    """The curated table of critical legal terms across Supported Languages.

    It serves two directions over the same rows: ``to_english`` rewrites a Hindi or
    code-mixed query into an English query for retrieval, and ``render`` renders an
    English term back into the user's language with the English kept inline in
    brackets so the critical term cannot be lost in translation.
    """

    def __init__(self, entries: Sequence[GlossaryEntry]):
        self._entries = list(entries)
        # Forward maps, one per Supported Language: English term -> target term.
        self._en_to: Dict[str, Dict[str, str]] = {}
        for entry in self._entries:
            for language, term in entry.by_language.items():
                self._en_to.setdefault(language, {})[entry.en] = term
        # One reverse map for normalisation: every foreign term -> its English
        # equivalent, longest foreign forms first so a phrase ("चल संपत्ति",
        # "அசையும் சொத்து") is matched before any of its component words.
        self._foreign_to_en = sorted(
            (
                (term, entry.en)
                for entry in self._entries
                for term in entry.by_language.values()
            ),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )

    @classmethod
    def load(cls, path: str = _GLOSSARY_PATH) -> "BilingualGlossary":
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        rows = list(raw.get("terms", [])) + list(raw.get("domains", []))
        return cls([cls._entry_from_row(row) for row in rows])

    @staticmethod
    def _entry_from_row(row: Dict) -> GlossaryEntry:
        # Every key other than the English term and the bookkeeping ``unverified``
        # flag is a Supported Language column, so new languages are pure data.
        by_language = {
            key: value
            for key, value in row.items()
            if key not in ("en", "unverified")
        }
        return GlossaryEntry(
            en=row["en"],
            by_language=by_language,
            unverified=frozenset(row.get("unverified", [])),
        )

    def to_english(self, query: str) -> str:
        """Normalise a query to an English query, preserving legal terms.

        Each known foreign term (longest first) is replaced with its English
        equivalent; remaining foreign-script tokens (function words the glossary
        does not carry) are dropped, while Latin-script tokens - English words mixed
        into a code-mixed query - are kept verbatim. An English query passes through
        unchanged.
        """
        text = query
        for foreign, en in self._foreign_to_en:
            text = text.replace(foreign, f" {en} ")
        tokens = [t for t in text.split() if not _FOREIGN_RE.search(t)]
        return " ".join(tokens)

    def term_for(self, english_term: str, language: str) -> Optional[str]:
        """The glossary's equivalent of an English term in ``language``, if any."""
        return self._en_to.get(language, {}).get(english_term)

    def hindi_for(self, english_term: str) -> Optional[str]:
        """The glossary's Hindi equivalent of an English term, if it has one."""
        return self.term_for(english_term, HINDI)

    def render(self, english_term: str, language: str) -> str:
        """Render a critical term in ``language`` with the English inline in brackets.

        For a non-English language this yields ``"<term> (<english>)"`` so the
        critical legal term appears in the user's language while its authoritative
        English stays visible. Falls back to the English term when no equivalent
        exists or the language is English.
        """
        if language == ENGLISH:
            return english_term
        translated = self.term_for(english_term, language)
        return f"{translated} ({english_term})" if translated else english_term

    def unverified_terms(self, language: str) -> List[str]:
        """English terms whose ``language`` translation lacks an official source.

        Tamil and Gujarati lean on this: official central-act translations are
        often unavailable to verify a term, so those rows are flagged here rather
        than presented as authoritative.
        """
        return [e.en for e in self._entries if language in e.unverified]


@dataclass(frozen=True)
class NormalizedQuery:
    """A raw query after detection and intent extraction."""

    language: str
    english_query: str


def normalize_query(query: str, glossary: BilingualGlossary) -> NormalizedQuery:
    """Detect the language and extract the query's intent into English."""
    return NormalizedQuery(
        language=detect_language(query),
        english_query=glossary.to_english(query),
    )


# Ambiguous terms that, on their own, do not pin down a single Covered Domain. In
# Citizen Mode such a query triggers a Confirmation Step rather than a guess. Each
# carries the clarifying question in every Supported Language.
_AMBIGUOUS: Dict[str, Dict[str, str]] = {
    "right": {
        ENGLISH: (
            "Did you mean your fundamental rights, your consumer rights, or your "
            "intellectual property rights? Please clarify so I can answer "
            "accurately."
        ),
        HINDI: (
            "क्या आपका मतलब आपके मौलिक अधिकार (fundamental rights), उपभोक्ता अधिकार "
            "(consumer rights), या बौद्धिक संपदा अधिकार (intellectual property rights) "
            "से है? कृपया स्पष्ट करें ताकि मैं सटीक उत्तर दे सकूँ।"
        ),
        TAMIL: (
            "நீங்கள் உங்கள் அடிப்படை உரிமைகள் (fundamental rights), நுகர்வோர் உரிமைகள் "
            "(consumer rights), அல்லது அறிவுசார் சொத்து உரிமைகள் (intellectual property "
            "rights) குறித்து கேட்கிறீர்களா? துல்லியமாக பதிலளிக்க தயவுசெய்து "
            "தெளிவுபடுத்தவும்."
        ),
        GUJARATI: (
            "શું તમારો અર્થ તમારા મૂળભૂત અધિકારો (fundamental rights), ગ્રાહક અધિકારો "
            "(consumer rights), અથવા બૌદ્ધિક સંપદા અધિકારો (intellectual property "
            "rights) છે? કૃપા કરીને સ્પષ્ટ કરો જેથી હું સચોટ જવાબ આપી શકું."
        ),
    },
}


def confirmation_for(english_query: str, language: str = ENGLISH) -> Optional[str]:
    """The Confirmation Step question for an ambiguous query, or ``None``.

    A query is ambiguous when its only content words are ambiguous terms - it
    carries no other legal content to disambiguate against. The clarifying check is
    returned in the user's language.
    """
    stems = set(content_stems(english_query))
    if not stems or not stems <= set(_AMBIGUOUS):
        return None
    for term in _AMBIGUOUS:
        if term in stems:
            texts = _AMBIGUOUS[term]
            return texts.get(language, texts[ENGLISH])
    return None
