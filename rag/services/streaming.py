"""True token streaming over the answer seam.

The pre-generation pipeline (normalize, screen, retrieve, gate, expand) runs
whole in a worker thread; generation then streams, and each cumulative
explanation goes to the wire as its own frame while citations are still being
produced. Every decision stays in the seam:

- A pre-generation decision (Confirmation, advice Refusal, ungrounded Refusal)
  streams as the complete answer it already is.
- The post-generation citation-verification gate still runs: when it strips
  every citation after text has streamed, a corrective ``meta`` frame flips the
  state to ``refusal`` and a fresh ``explanation`` frame replaces the streamed
  text - both replace client-side, so the contract never breaks.
- A generator without ``stream`` is served by running ``generate`` whole in a
  thread (test doubles use this path; the live generator streams).
- A model-call failure is a SERVICE error, not a legal decision: after one
  retry the stream ends with ``meta{state: "error"}`` plus a plain
  "try again" explanation in the user's language - never a fake Refusal.

A turn is persisted only once its answer is complete: a client disconnect
mid-generation raises ``GeneratorExit`` (a ``BaseException``) out of the
``yield``, so no partial answer is ever recorded - and a service error is
never persisted at all.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator, Callable, Optional

import anyio.to_thread

from rag.domain.answer import GroundedAnswer, LegalAssistant
from rag.domain.generation import DraftAnswer, ExplanationSoFar
from rag.services.frames import answer_frames, citation_payload, frame

_LOG = logging.getLogger(__name__)

Persist = Callable[[GroundedAnswer], None]

# A failed model call is a SERVICE problem, not a legal Refusal: the frames say
# so in the user's language, and the turn is never persisted as an answer.
_SERVICE_ERROR = {
    "en": (
        "The assistant could not reach its language model just now, so this "
        "question was not answered. Please try again in a moment."
    ),
    "hi": (
        "सहायक अभी अपने भाषा मॉडल से संपर्क नहीं कर सका, इसलिए इस प्रश्न का उत्तर "
        "नहीं दिया गया। कृपया थोड़ी देर में फिर से प्रयास करें।"
    ),
    "ta": (
        "உதவியாளரால் இப்போது அதன் மொழி மாதிரியை அணுக முடியவில்லை, எனவே இந்தக் "
        "கேள்விக்கு பதில் அளிக்கப்படவில்லை. சிறிது நேரத்தில் மீண்டும் முயற்சிக்கவும்."
    ),
    "gu": (
        "સહાયક હમણાં તેના ભાષા મોડેલ સુધી પહોંચી શક્યો નથી, તેથી આ પ્રશ્નનો જવાબ "
        "આપવામાં આવ્યો નથી. કૃપા કરીને થોડી વારમાં ફરી પ્રયાસ કરો."
    ),
}


def _error_frames(language: str, exc: Exception):
    """The corrective error frames: replace-semantics meta + explanation.

    The meta carries what actually failed (exception type and message) so the
    frontend can show the user exactly what went wrong, not a vague apology.
    """
    detail = f"{type(exc).__name__}: {exc}".strip().rstrip(":")
    yield frame(
        {"kind": "meta", "state": "error", "language": language, "detail": detail}
    )
    yield frame(
        {
            "kind": "explanation",
            "text": _SERVICE_ERROR.get(language, _SERVICE_ERROR["en"]),
        }
    )


async def stream_answer(
    assistant: LegalAssistant,
    query: str,
    language: str,
    *,
    display_query: Optional[str] = None,
    persist: Optional[Persist] = None,
) -> AsyncIterator[str]:
    """The NDJSON frames of one answer, streamed as generation progresses.

    ``query`` is the resolved (follow-up-rewritten) query the pipeline runs on;
    ``display_query`` is the user's own words, kept on the persisted answer.
    ``persist`` is called once with the completed answer (blocking store I/O,
    run in a thread); it is skipped when the client disconnects mid-answer.
    """
    display = display_query if display_query is not None else query

    async def complete(result: GroundedAnswer) -> GroundedAnswer:
        result.query = display
        if persist is not None:
            await anyio.to_thread.run_sync(persist, result)
        return result

    try:
        prepared = await anyio.to_thread.run_sync(
            assistant.prepare, query, language
        )
    except Exception as exc:
        # Intent extraction is a live LLM call too; its failure is the same
        # service problem, surfaced the same way.
        _LOG.warning("prepare failed (%s); reporting a service error", type(exc).__name__)
        for line in _error_frames(language, exc):
            yield line
        return
    if isinstance(prepared, GroundedAnswer):
        for line in answer_frames(await complete(prepared)):
            yield line
        return

    generator_stream = getattr(assistant.generator, "stream", None)
    if generator_stream is None:
        def generate_whole() -> GroundedAnswer:
            draft = assistant.generator.generate(
                prepared.english_query, prepared.sections, prepared.language
            )
            return assistant.finalize(prepared, draft)

        try:
            result = await anyio.to_thread.run_sync(generate_whole)
        except Exception as exc:
            _LOG.warning(
                "generation failed (%s); reporting a service error", type(exc).__name__
            )
            for line in _error_frames(prepared.language, exc):
                yield line
            return
        for line in answer_frames(await complete(result)):
            yield line
        return

    # True streaming: the state is known before generation (refusal-by-advice
    # and High-Stakes were decided in prepare), so meta leads immediately and
    # the explanation grows frame by frame.
    yield frame(
        {
            "kind": "meta",
            "state": "emergency" if prepared.high_stakes else "normal",
            "language": prepared.language,
        }
    )
    if prepared.notice:
        yield frame({"kind": "highStakesNotice", "text": prepared.notice})

    # Cumulative explanation frames REPLACE client-side, so a whole retry is
    # invisible to the user: the second attempt's text simply overwrites the
    # first's. One retry absorbs the flaky-gateway case (slow first token,
    # transient 5xx) that otherwise turns every question into an error.
    draft: Optional[DraftAnswer] = None
    for attempt in (1, 2):
        try:
            async for event in generator_stream(
                prepared.english_query, prepared.sections, prepared.language
            ):
                if isinstance(event, DraftAnswer):
                    draft = event
                elif isinstance(event, ExplanationSoFar) and event.text:
                    yield frame({"kind": "explanation", "text": event.text})
            if draft is None:
                raise RuntimeError("generation stream ended without a draft")
            break
        except Exception as exc:
            if attempt == 1:
                _LOG.warning(
                    "generation stream failed (%s); retrying once", type(exc).__name__
                )
                continue
            # A failed model call is a service problem, not a legal decision:
            # the corrective error frames replace whatever partial text
            # rendered, and nothing is persisted as an answer.
            _LOG.warning(
                "generation stream failed twice (%s); reporting a service error",
                type(exc).__name__,
            )
            for line in _error_frames(prepared.language, exc):
                yield line
            return

    result = assistant.finalize(prepared, draft)
    result = await complete(result)
    if result.refused:
        # Late refusal: citation verification stripped everything after text
        # streamed. The corrective frames replace the streamed text client-side.
        for line in answer_frames(result):
            yield line
        return

    # The authoritative explanation (post-softening) replaces the streamed text,
    # then the verified citations and the rest of the structured parts follow.
    yield frame({"kind": "explanation", "text": result.explanation})
    for citation in result.citations:
        yield frame(citation_payload(citation))
    if result.former_ipc_note:
        yield frame({"kind": "note", "text": result.former_ipc_note})
    if result.next_step:
        yield frame({"kind": "nextStep", "text": result.next_step})
    if result.disclaimer:
        yield frame({"kind": "disclaimer", "text": result.disclaimer})
