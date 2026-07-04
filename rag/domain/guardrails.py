"""The layered guardrail stack that keeps the product on Legal Information.

The product produces Legal Information only - general, source-backed explanation
of what the law says - and never Legal Advice - a personalised recommendation
about a specific person's situation. This module is the seam that enforces that
line:

* :func:`screen_request` is the input-side scope contract. It classifies a
  request before any retrieval runs: advice-seeking inputs (outcome prediction
  or personalised "what should I do") are routed to a Refusal, and High-Stakes
  queries (safety, arrest-in-progress, active deadlines) are flagged so the
  answer can lead with emergency and legal-aid contacts.
* :func:`soften_advice` is the output-side check: it catches any answer text that
  slipped into "you should sue / you will win / do X" phrasing and rewrites it
  back to neutral, informational language.

The High-Stakes notice, advice Refusal text, and Legal-Aid Pointer live here as
the single source of the product's safety copy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# The Legal-Aid Pointer: a concrete reference to real help, reused everywhere a
# Disclaimer or High-Stakes response needs one.
LEGAL_AID_POINTER = (
    "a lawyer or your nearest Legal Services Authority (NALSA / DLSA)"
)

# The scope contract, stated plainly. The layered checks below enforce it.
SCOPE_CONTRACT = (
    "This assistant provides Legal Information only: general, source-backed "
    "explanation of what the law says and what the standard procedure is. It "
    "does not provide Legal Advice - it will not predict the outcome of a case "
    "or tell anyone what they personally should do."
)

# High-Stakes Routing: leads with emergency and legal-aid contacts before the
# legal explanation when a query touches safety, arrest, or an active deadline.
HIGH_STAKES_NOTICE = (
    "If you are in immediate danger or this is urgent, get help first:\n"
    "- Emergency (police / fire / ambulance): 112\n"
    "- Women's helpline: 181\n"
    "- Free legal aid: contact " + LEGAL_AID_POINTER + ".\n"
    "The legal information below is general and is not a substitute for urgent "
    "help or a lawyer."
)

ADVICE_REFUSAL_TEXT = (
    "I can explain what the law says and the general procedure, but I cannot "
    "predict the outcome of a case or tell you what you personally should do."
)

ADVICE_REFUSAL_NEXT_STEP = (
    "For guidance on your specific situation, please consult " + LEGAL_AID_POINTER + "."
)


class RequestKind(Enum):
    """How the scope contract classifies an incoming request."""

    ANSWERABLE = "answerable"
    ADVICE = "advice"


@dataclass(frozen=True)
class ScreenResult:
    """The input-side decision: what kind of request, and is it High-Stakes."""

    kind: RequestKind
    high_stakes: bool


# Advice-seeking markers: outcome prediction and personalised action requests.
# These are deliberately curated - a guardrail errs toward refusing the
# personalised question, not toward guessing.
_ADVICE_MARKERS = (
    "will i win",
    "will i lose",
    "will i get bail",
    "will i be convicted",
    "will the court",
    "will the judge",
    "my chances",
    "chances of winning",
    "predict the outcome",
    "outcome of my case",
    "what should i do",
    "what do i do",
    "should i sue",
    "should i file",
    "should i sign",
    "should i accept",
    "should i plead",
    "should i",
    "what would you do",
    "what do you recommend",
    "do you recommend",
    "advise me",
    "give me advice",
    "tell me what to do",
)

# High-Stakes markers: safety, arrest-in-progress, active deadlines.
_HIGH_STAKES_MARKERS = (
    "being arrested",
    "police are arresting",
    "police are here",
    "they are arresting",
    "being detained",
    "in danger",
    "being attacked",
    "being beaten",
    "domestic violence",
    "threatening to kill",
    "going to kill",
    "about to be evicted",
    "deadline is today",
    "deadline is tomorrow",
    "due today",
    "due tomorrow",
    "last date is today",
    "last date is tomorrow",
    "hearing is tomorrow",
    "expires today",
    "expires tomorrow",
)

# Output-side advice phrasing to soften, mapped to neutral informational copy.
_SOFTENINGS = (
    ("you should sue", "one option the law provides is to approach the appropriate court or authority"),
    ("you should file", "one option the law provides is to file the appropriate complaint"),
    ("you will win", "the outcome of any case depends on its specific facts and is decided by the court"),
    ("you will lose", "the outcome of any case depends on its specific facts and is decided by the court"),
    ("you should", "you may wish to consider whether to"),
    ("i recommend", "the law provides that"),
)


def _normalise(query: str) -> str:
    return re.sub(r"\s+", " ", query.lower()).strip()


def _matches_any(text: str, markers) -> bool:
    return any(marker in text for marker in markers)


def screen_request(query: str) -> ScreenResult:
    """Apply the input-side scope contract to a raw query.

    High-Stakes takes precedence over the advice refusal: an urgent query is
    answered with emergency contacts leading, never silently refused.
    """
    text = _normalise(query)
    high_stakes = _matches_any(text, _HIGH_STAKES_MARKERS)
    if not high_stakes and _matches_any(text, _ADVICE_MARKERS):
        return ScreenResult(kind=RequestKind.ADVICE, high_stakes=False)
    return ScreenResult(kind=RequestKind.ANSWERABLE, high_stakes=high_stakes)


def soften_advice(text: str) -> str:
    """Rewrite any advice-style phrasing in answer text back to neutral language."""
    softened = text
    for phrase, replacement in _SOFTENINGS:
        softened = re.sub(re.escape(phrase), replacement, softened, flags=re.IGNORECASE)
    return softened
