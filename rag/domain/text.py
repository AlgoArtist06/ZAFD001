"""Tiny lexical helpers shared by the domain router and the keyword retriever.

Deliberately dependency-free: a light stemmer and stopword filter are enough to
ground retrieval on this small statutory corpus without pulling in an NLP stack.
"""
from __future__ import annotations

import re
from typing import List, Set

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common function words that carry no legal signal; dropped before matching so a
# query's content words are what drive routing and keyword retrieval.
_STOPWORDS: Set[str] = {
    "a", "an", "the", "of", "for", "to", "is", "are", "am", "was", "were", "be",
    "been", "being", "what", "which", "who", "whom", "how", "do", "does", "did",
    "i", "me", "my", "mine", "we", "us", "our", "you", "your", "it", "its",
    "in", "on", "at", "by", "with", "from", "about", "into", "over", "under",
    "that", "this", "these", "those", "and", "or", "not", "no", "can", "could",
    "should", "would", "will", "shall", "may", "might", "if", "then", "so",
    "any", "some", "all", "such", "as", "out", "up", "down", "there", "here",
    "have", "has", "had", "get", "got", "want", "need", "know",
}


def _stem(token: str) -> str:
    """Crude suffix-stripping stemmer (ing/ed/ies/es/s) for lexical overlap."""
    for suffix in ("ing", "ied", "ed", "ies", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            return base + "y" if suffix == "ies" else base
    return token


def content_stems(text: str) -> List[str]:
    """Lowercased, stopword-filtered, stemmed content tokens of ``text``."""
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]
