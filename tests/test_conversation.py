"""Answering over the single shared corpus.

Every answer is drawn from the one shared corpus, index, and citation verifier
held by the assistant.
"""
from tests.doubles import offline_assistant


def test_answer_stays_plain_and_focused(corpus):
    result = offline_assistant(corpus).answer("punishment for theft and cheating")
    assert "In plain language" in result.explanation
    # A single focused Citation and the step-by-step next step.
    assert len(result.citations) == 1
    assert "Practical next step" in result.next_step


def test_lay_phrasing_expands_to_the_legal_concept(corpus):
    # "tricked" is a lay complaint; it normalizes to cheating and still reaches
    # the right section, exercising complaint-to-concept expansion.
    result = offline_assistant(corpus).answer(
        "the shopkeeper tricked me out of my money"
    )
    assert result.refused is False
    assert any(c.section_number == "318" for c in result.citations)
