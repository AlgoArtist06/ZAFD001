"""The multilingual answering layer, proven out with Hindi.

The product serves several Supported Languages over one English Source of Truth.
This module is the seam that lets it: it detects the user's language, extracts the
query's intent into an English string with legal terms preserved (so retrieval and
reasoning always run over the single English corpus), and renders critical terms
back into the user's language for the answer.

The Bilingual Legal Glossary is the deterministic backbone here: the same curated
table both normalises an incoming Hindi (or code-mixed Hinglish) query to English
and constrains the Hindi terminology in the output, so a term like bailable versus
non-bailable cannot flip meaning in translation. Production swaps a Claude-backed
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

_GLOSSARY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "glossary.json"
)

# The Devanagari block: its presence is what marks a query as Hindi rather than
# English. Code-mixed Hinglish still trips this as long as any Hindi word is in
# Devanagari script; the Latin-script tokens around it are preserved verbatim.
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


@dataclass(frozen=True)
class GlossaryEntry:
    """One critical legal term and its equivalents across Supported Languages."""

    en: str
    hi: str


def detect_language(query: str) -> str:
    """Detect the user's language from the raw query.

    Returns ``"hi"`` when any Devanagari character is present (including code-mixed
    Hinglish), otherwise ``"en"``. Detection drives the language of the answer.
    """
    return HINDI if _DEVANAGARI_RE.search(query) else ENGLISH


class BilingualGlossary:
    """The curated table of critical legal terms across Supported Languages.

    It serves two directions over the same rows: ``to_english`` rewrites a Hindi or
    code-mixed query into an English query for retrieval, and ``render`` renders an
    English term back into the user's language with the English kept inline in
    brackets so the critical term cannot be lost in translation.
    """

    def __init__(self, entries: Sequence[GlossaryEntry]):
        self._entries = list(entries)
        self._en_to_hi: Dict[str, str] = {e.en: e.hi for e in self._entries}
        # Longest Hindi forms first so a phrase ("चल संपत्ति") is matched before
        # any of its component words ("संपत्ति").
        self._hi_to_en = sorted(
            ((e.hi, e.en) for e in self._entries),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )

    @classmethod
    def load(cls, path: str = _GLOSSARY_PATH) -> "BilingualGlossary":
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        rows = list(raw.get("terms", [])) + list(raw.get("domains", []))
        return cls([GlossaryEntry(en=row["en"], hi=row["hi"]) for row in rows])

    def to_english(self, query: str) -> str:
        """Normalise a query to an English query, preserving legal terms.

        Each known Hindi term (longest first) is replaced with its English
        equivalent; remaining Devanagari tokens (function words the glossary does
        not carry) are dropped, while Latin-script tokens - English words mixed into
        Hinglish - are kept verbatim. An English query passes through unchanged.
        """
        text = query
        for hi, en in self._hi_to_en:
            text = text.replace(hi, f" {en} ")
        tokens = [t for t in text.split() if not _DEVANAGARI_RE.search(t)]
        return " ".join(tokens)

    def hindi_for(self, english_term: str) -> Optional[str]:
        """The glossary's Hindi equivalent of an English term, if it has one."""
        return self._en_to_hi.get(english_term)

    def render(self, english_term: str, language: str) -> str:
        """Render a critical term in ``language`` with the English inline in brackets.

        For Hindi this yields ``"<hindi> (<english>)"`` so the critical legal term
        appears in the user's language while its authoritative English stays visible.
        Falls back to the English term when no equivalent exists or the language is
        English.
        """
        if language == ENGLISH:
            return english_term
        translated = self._en_to_hi.get(english_term)
        return f"{translated} ({english_term})" if translated else english_term


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
