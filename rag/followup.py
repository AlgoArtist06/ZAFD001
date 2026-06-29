"""Rewriting a dependent follow-up into a self-contained query.

Within a Conversation a follow-up turn often leans on what was just asked - a
referential pronoun ("what is the punishment for *it*?") or an elliptical
connector ("and *cheating*?"). On its own such a query carries no statutory
content to ground on, so it would be refused. This module rewrites it into a
standalone query by folding in the bounded recent Conversation context, before
the query enters retrieval. A query that is already self-contained is returned
unchanged, so non-follow-up turns are unaffected.

The rewrite is deliberately deterministic and dependency-free, matching the
offline retrieval and generation seams. Production swaps a Claude-backed
(claude-opus) rewriter behind :func:`rewrite_followup`; the surface contract -
recent context plus a follow-up in, one standalone query out - stays the same.
"""
from __future__ import annotations

import re
from typing import Sequence

# Words that mark a query as leaning on earlier context: back-referential
# pronouns and the elliptical connectors that open a continued question. When a
# query carries one of these it is treated as a follow-up and resolved against
# the recent context rather than answered on its own.
_FOLLOWUP_MARKERS = frozenset(
    {
        "it",
        "its",
        "that",
        "this",
        "them",
        "they",
        "those",
        "these",
        "one",
        "ones",
        "also",
        "else",
    }
)

_WORD_RE = re.compile(r"[a-z]+")


def is_followup(query: str) -> bool:
    """Whether ``query`` reads as a follow-up that depends on prior context."""
    words = _WORD_RE.findall(query.lower())
    return any(word in _FOLLOWUP_MARKERS for word in words)


def rewrite_followup(query: str, recent_context: Sequence[str]) -> str:
    """Rewrite a dependent follow-up into a standalone query using recent context.

    ``recent_context`` is the bounded list of recent standalone queries in the
    Conversation, oldest first. A follow-up is made self-contained by prefixing
    that context so retrieval sees the subject it refers back to; a self-contained
    query (or one with no context yet) is returned unchanged.
    """
    if not recent_context or not is_followup(query):
        return query
    return " ".join([*recent_context, query])
