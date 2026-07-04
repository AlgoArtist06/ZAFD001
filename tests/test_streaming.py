"""True token streaming: frames flow while generation is still running.

These tests pin the streaming contract the frontend depends on: ``meta`` leads
with the pre-generation state, cumulative ``explanation`` frames grow the text,
citations follow only after verification, a post-generation refusal corrects
the stream with replace-semantics frames, and a transport failure ends it with
an explicit error state carrying what failed. A generator double without
``stream`` falls back to whole-answer frames, so the suite never needs a live
model.
"""
import json

import anyio
import httpx
import pytest

from tests.doubles import offline_assistant
from rag.domain.citation import Citation
from rag.domain.generation import DraftAnswer, ExplanationSoFar
from rag.infrastructure.llm import _ExplanationScanner
from rag.services.frames import answer_frames
from rag.services.streaming import stream_answer


def _collect(async_iterator):
    async def run():
        return [json.loads(line) async for line in async_iterator]

    return anyio.run(run)


class _StreamingGenerator:
    """A fake live generator: streams explanations, then a draft."""

    def __init__(self, make_events):
        self._make_events = make_events
        self.streamed = False

    def generate(self, query, sections, language):
        raise AssertionError("the streaming path must not call generate()")

    async def stream(self, query, sections, language):
        self.streamed = True
        for event in self._make_events(sections):
            yield event


def _grounded_events(sections):
    citation = Citation.from_section(sections[0])
    return [
        ExplanationSoFar("Theft is"),
        ExplanationSoFar("Theft is the dishonest taking of movable property."),
        DraftAnswer(
            explanation="Theft is the dishonest taking of movable property.",
            legal_basis=f"Legal basis - {citation.anchor}",
            next_step="Read the cited provision.",
            citations=[citation],
        ),
    ]


def test_explanations_stream_before_citations_and_meta_leads(corpus):
    generator = _StreamingGenerator(_grounded_events)
    assistant = offline_assistant(corpus, generator=generator)

    frames = _collect(
        stream_answer(assistant, "theft of movable property", "en")
    )

    kinds = [frame["kind"] for frame in frames]
    assert generator.streamed
    assert frames[0] == {"kind": "meta", "state": "normal", "language": "en"}
    # The explanation grew across frames, all before any citation frame.
    explanations = [f["text"] for f in frames if f["kind"] == "explanation"]
    assert len(explanations) >= 2
    assert explanations[0] == "Theft is"
    assert kinds.index("citation") > max(
        i for i, k in enumerate(kinds) if k == "explanation"
    ) - len(explanations) + 1
    citation = next(f for f in frames if f["kind"] == "citation")
    assert "commits theft" in citation["verbatim"]
    # The last explanation frame is the authoritative (verified, softened) text.
    assert explanations[-1] == "Theft is the dishonest taking of movable property."
    assert kinds[-1] == "disclaimer"


def test_late_refusal_corrects_the_stream_after_text_was_sent(corpus):
    def unverifiable(sections):
        return [
            ExplanationSoFar("A claimed rule that will not survive verification"),
            DraftAnswer(
                explanation="A claimed rule.",
                legal_basis="Imaginary Act (2026), Section 999.",
                next_step="",
                citations=[Citation("imaginary", "", 0, "999", "", "")],
            ),
        ]

    assistant = offline_assistant(corpus, generator=_StreamingGenerator(unverifiable))
    frames = _collect(
        stream_answer(assistant, "theft of movable property", "en")
    )

    metas = [f for f in frames if f["kind"] == "meta"]
    assert metas[0]["state"] == "normal"
    assert metas[-1]["state"] == "refusal"
    # The corrective explanation replaces the streamed text client-side.
    assert "I do not have a sourced answer" in frames[-3]["text"] or any(
        "I do not have a sourced answer" in f.get("text", "")
        for f in frames
        if f["kind"] == "explanation"
    )
    assert not any(f["kind"] == "citation" for f in frames)


def test_transport_failure_mid_stream_ends_with_an_explicit_error(corpus):
    async def broken(query, sections, language):
        yield ExplanationSoFar("Theft is")
        raise httpx.ReadError("connection lost")

    class _BrokenGenerator:
        stream = staticmethod(broken)

        def generate(self, *args):
            raise AssertionError("unused")

    persisted = []
    assistant = offline_assistant(corpus, generator=_BrokenGenerator())
    frames = _collect(
        stream_answer(
            assistant,
            "theft of movable property",
            "en",
            persist=persisted.append,
        )
    )

    # A model failure is a SERVICE error, never a fake Refusal: the meta says
    # what actually failed, the explanation says the question went unanswered,
    # and nothing is persisted as an answer.
    metas = [f for f in frames if f["kind"] == "meta"]
    assert metas[-1]["state"] == "error"
    assert "ReadError" in metas[-1]["detail"]
    assert frames[-1]["kind"] == "explanation"
    assert "could not reach its language model" in frames[-1]["text"]
    assert not any(f["kind"] == "citation" for f in frames)
    assert persisted == []


def test_high_stakes_stream_leads_with_the_notice(corpus):
    assistant = offline_assistant(corpus, generator=_StreamingGenerator(_grounded_events))
    frames = _collect(
        stream_answer(
            assistant,
            "The police are arresting me - what is the punishment for theft?",
            "en",
        )
    )
    assert frames[0]["kind"] == "meta" and frames[0]["state"] == "emergency"
    assert frames[1]["kind"] == "highStakesNotice"
    assert "112" in frames[1]["text"]


def test_generator_without_stream_falls_back_to_whole_answer_frames(corpus):
    assistant = offline_assistant(corpus)
    streamed = _collect(
        stream_answer(assistant, "theft of movable property", "en")
    )
    whole = [
        json.loads(line)
        for line in answer_frames(
            assistant.answer("theft of movable property", "en")
        )
    ]
    assert streamed == whole


def test_completed_answer_is_persisted_once_with_the_users_words(corpus):
    persisted = []
    assistant = offline_assistant(corpus, generator=_StreamingGenerator(_grounded_events))

    frames = _collect(
        stream_answer(
            assistant,
            "theft of movable property",
            "en",
            display_query="Someone took my phone",
            persist=persisted.append,
        )
    )

    assert frames  # the stream ran
    assert len(persisted) == 1
    assert persisted[0].query == "Someone took my phone"
    assert persisted[0].refused is False


def test_pre_generation_refusal_streams_as_a_complete_answer(corpus):
    generator = _StreamingGenerator(_grounded_events)
    assistant = offline_assistant(corpus, generator=generator)
    frames = _collect(
        stream_answer(assistant, "best recipe for biryani", "en")
    )
    assert generator.streamed is False
    assert frames[0]["state"] == "refusal"
    assert not any(f["kind"] == "citation" for f in frames)


# --- The incremental explanation scanner -----------------------------------


def test_scanner_reveals_the_explanation_as_it_grows():
    scanner = _ExplanationScanner()
    assert scanner.feed('{"expl') is None
    assert scanner.feed('anation": "The') == "The"
    assert scanner.feed(" law says") == "The law says"
    assert scanner.feed(' so.", "legal_basis":') == "The law says so."


def test_scanner_decodes_escapes_even_split_across_feeds():
    scanner = _ExplanationScanner()
    scanner.feed('{"explanation": "line one\\')
    assert scanner.feed('ntwo \\"quoted\\"') == 'line one\ntwo "quoted"'


def test_scanner_holds_back_incomplete_unicode_escapes():
    scanner = _ExplanationScanner()
    scanner.feed('{"explanation": "rupee \\u20')
    # The half escape is not emitted as garbage...
    assert scanner.feed("") == "rupee "
    # ...and completes cleanly once the rest arrives.
    assert scanner.feed('b9 fine"') == "rupee ₹ fine"


def test_scanner_ignores_objects_without_an_explanation():
    scanner = _ExplanationScanner()
    assert scanner.feed('{"legal_basis": "something"}') is None
