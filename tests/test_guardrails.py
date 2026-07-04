"""Seam 2 guardrails - keeping the product on Legal Information, never Advice.

These tests exercise the layered guardrail stack through the public
``answer(query, language)`` entry and the ``rag.guardrails`` seam: an input
scope contract that refuses advice-seeking and out-of-scope requests, an
output-side check that softens advice phrasing, High-Stakes Routing that leads
with emergency contacts, and a persistent Disclaimer with a Legal-Aid Pointer.
"""
import json

from tests.doubles import offline_assistant
from rag.services.eval import ENGLISH, load_gold_cases, run_gold_eval
from rag.services.frames import answer_frames
from rag.domain.generation import DraftAnswer
from rag.domain.guardrails import soften_advice


def test_outcome_prediction_request_is_refused_and_redirected(corpus):
    # This query is grounded (theft of movable property), so only the advice
    # guardrail - not the out-of-scope gate - can cause the Refusal.
    result = offline_assistant(corpus).answer(
        "Someone took my movable property by theft - will I win if I sue?",
        "en",
    )
    assert result.refused is True
    assert result.citations == []
    # The Refusal redirects to real help rather than guessing an outcome.
    assert "NALSA" in result.text or "Legal Services Authority" in result.text


def test_personalised_action_request_is_refused_and_redirected(corpus):
    result = offline_assistant(corpus).answer(
        "My goods were defective - what should I do about the seller?",
        "en",
    )
    assert result.refused is True
    assert result.citations == []
    assert "NALSA" in result.text or "Legal Services Authority" in result.text


def test_output_check_softens_advice_phrasing():
    softened = soften_advice(
        "You should sue them immediately and you will win in court."
    ).lower()
    assert "you should sue" not in softened
    assert "you will win" not in softened
    assert "decided by the court" in softened


def test_advice_phrasing_in_a_draft_is_softened_in_the_answer(corpus):
    class _AdviceGenerator:
        def generate(self, query, sections, language):
            from rag.domain.citation import Citation

            return DraftAnswer(
                explanation="You should sue the seller and you will win.",
                legal_basis="Legal basis - the cited section.",
                next_step="I recommend you file at once.",
                citations=[Citation.from_section(sections[0])],
            )

    result = offline_assistant(corpus, generator=_AdviceGenerator()).answer(
        "theft of movable property", "en"
    )
    assert result.refused is False
    text = result.text.lower()
    assert "you should sue" not in text
    assert "you will win" not in text


def test_high_stakes_query_leads_with_emergency_and_legal_aid_contacts(corpus):
    result = offline_assistant(corpus).answer(
        "The police are arresting me - what is the punishment for theft?",
        "en",
    )
    assert result.high_stakes is True
    text = result.text
    # Emergency and legal-aid contacts appear...
    assert "112" in text
    assert "181" in text
    assert "NALSA" in text
    # ...and lead, before the legal explanation.
    assert text.index("112") < text.index(result.explanation)


def test_ordinary_query_is_not_high_stakes(corpus):
    result = offline_assistant(corpus).answer(
        "What is the punishment for theft of movable property?", "en"
    )
    assert result.high_stakes is False
    assert "112" not in result.text


def test_every_answer_path_carries_a_disclaimer_with_a_legal_aid_pointer(corpus):
    assistant = offline_assistant(corpus)
    grounded = assistant.answer("theft of movable property", "en")
    out_of_scope = assistant.answer("best recipe for biryani", "en")
    advice = assistant.answer("should i sue my landlord?", "en")
    for result in (grounded, out_of_scope, advice):
        assert result.disclaimer
        assert "NALSA" in result.disclaimer
        assert "not legal advice" in result.disclaimer.lower()


def test_streamed_high_stakes_answer_leads_with_the_notice(corpus):
    result = offline_assistant(corpus).answer(
        "The police are arresting me - what is the punishment for theft?",
        "en",
    )
    frames = [json.loads(line) for line in answer_frames(result)]
    assert frames[0]["kind"] == "meta" and frames[0]["state"] == "emergency"
    # The first content frame is the High-Stakes notice, before any explanation.
    assert frames[1]["kind"] == "highStakesNotice"
    assert "112" in frames[1]["text"]


def test_gold_set_covers_guardrail_behaviour_and_all_cases_pass(corpus):
    cases = load_gold_cases(language=ENGLISH)
    # The gold set must exercise an advice Refusal and a High-Stakes case.
    assert any(c.expect_refusal and "advice" in c.id for c in cases)
    assert any(c.expect_high_stakes for c in cases)

    report = run_gold_eval(offline_assistant(corpus), cases)
    assert report.failures == []
    assert report.passed == report.total
