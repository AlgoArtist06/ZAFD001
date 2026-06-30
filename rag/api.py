"""The shared answer-streaming helper for the HTTP demo surfaces.

Turns a Grounded Answer into a sequence of text chunks so an endpoint can stream
it part by part instead of returning a single blob. The FastAPI demo entry point
(:mod:`rag.fastapi_app`) and the ChatGPT-style shell (:mod:`rag.shell_app`) both
stream over this helper; none of them add retrieval or grounding of their own -
that all lives in the :func:`rag.answer` seam.
"""
from __future__ import annotations

from typing import Iterator

from rag.answer import GroundedAnswer, LegalAssistant


def _answer_parts(result: GroundedAnswer) -> Iterator[str]:
    """The structured answer, part by part, for progressive streaming."""
    if result.high_stakes_notice:
        yield result.high_stakes_notice + "\n\n"
    yield result.explanation + "\n\n"
    if result.legal_basis:
        yield result.legal_basis + "\n\n"
    yield result.next_step + "\n\n"
    if result.disclaimer:
        yield result.disclaimer


def stream_answer(
    assistant: LegalAssistant, query: str, mode: str = "citizen", language: str = "en"
) -> Iterator[str]:
    """Yield a Grounded Answer progressively, one structured part at a time."""
    yield from _answer_parts(assistant.answer(query, mode=mode, language=language))
