"""Dual-mode over a single corpus: the Conversation locks a Mode at start.

A Conversation is opened in either Citizen Mode (the default) or Professional
Mode, and that choice is fixed for the Conversation's lifetime - switching Mode
means opening a new Conversation. Both Modes answer over the one shared corpus,
index, and citation verifier held by the assistant.
"""
import pytest

from rag.answer import LegalAssistant


def test_new_conversation_defaults_to_citizen_mode(corpus):
    convo = LegalAssistant(corpus).start_conversation()
    assert convo.mode == "citizen"


def test_conversation_opened_in_professional_mode_keeps_it(corpus):
    convo = LegalAssistant(corpus).start_conversation(mode="professional")
    assert convo.mode == "professional"


def test_mode_is_locked_for_the_conversation_lifetime(corpus):
    convo = LegalAssistant(corpus).start_conversation(mode="professional")
    with pytest.raises(AttributeError):
        convo.mode = "citizen"


def test_professional_answer_is_terse_and_citation_dense(corpus):
    result = LegalAssistant(corpus).answer(
        "punishment for theft and cheating", mode="professional"
    )
    cited = {c.section_number for c in result.citations}
    # Dense: every grounded section is cited, not just the top one.
    assert {"303", "318"} <= cited
    # Terse: no plain-language Citizen framing.
    assert "In plain language" not in result.explanation


def test_citizen_answer_stays_plain_and_focused(corpus):
    result = LegalAssistant(corpus).answer(
        "punishment for theft and cheating", mode="citizen"
    )
    assert "In plain language" in result.explanation
    # Citizen keeps a single focused Citation and the step-by-step next step.
    assert len(result.citations) == 1
    assert "Practical next step" in result.next_step


def test_citizen_mode_expands_lay_phrasing_to_the_legal_concept(corpus):
    # "tricked" is a lay complaint; Citizen Mode normalizes it to cheating and
    # still reaches the right section, exercising complaint-to-concept expansion.
    result = LegalAssistant(corpus).answer(
        "the shopkeeper tricked me out of my money", mode="citizen"
    )
    assert result.refused is False
    assert any(c.section_number == "318" for c in result.citations)


def test_professional_mode_does_no_query_expansion(corpus):
    # Same lay query, exact keyword matching only: with no expansion the
    # colloquial wording has no statutory overlap, so it is refused, not guessed.
    result = LegalAssistant(corpus).answer(
        "the shopkeeper tricked me out of my money", mode="professional"
    )
    assert result.refused is True


def test_both_modes_resolve_against_one_shared_corpus(corpus):
    assistant = LegalAssistant(corpus)
    citizen = assistant.answer("theft of movable property", mode="citizen")
    professional = assistant.answer("theft of movable property", mode="professional")

    citizen_303 = next(c for c in citizen.citations if c.section_number == "303")
    professional_303 = next(
        c for c in professional.citations if c.section_number == "303"
    )
    # One provenance layer and one index: the same section, with identical
    # verbatim statutory text, backs both Modes - the law never diverges.
    assert citizen_303.act_id == professional_303.act_id == "bns"
    assert citizen_303.verbatim_text == professional_303.verbatim_text


def test_conversation_answers_every_turn_in_its_locked_mode(corpus):
    convo = LegalAssistant(corpus).start_conversation(mode="professional")
    result = convo.ask("punishment for theft and cheating")
    assert result.mode == "professional"
    assert {"303", "318"} <= {c.section_number for c in result.citations}
