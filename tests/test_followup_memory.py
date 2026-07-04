"""Multi-turn memory within a single Conversation.

A follow-up turn may depend on what was just asked ("what is the punishment for
it?"). Before retrieval the Conversation rewrites such a follow-up into a
self-contained query using the bounded recent context, then runs the full
pipeline (retrieval, parent expansion, grounding, citation verification,
guardrails) over it. Context lives inside one Conversation only and is never
carried across Conversations.
"""
from tests.doubles import offline_assistant
from rag.services.eval import ENGLISH, load_gold_cases, run_gold_eval


def test_dependent_followup_is_answered_using_prior_turn(corpus):
    convo = offline_assistant(corpus).start_conversation()
    convo.ask("Someone cheated me by fraud and took my property dishonestly")
    # "it" refers back to the cheating asked about a moment ago.
    followup = convo.ask("What is the punishment for it?")
    assert followup.refused is False
    assert any(c.section_number == "318" for c in followup.citations)


def test_same_followup_refuses_without_conversation_context(corpus):
    # Run on its own the dependent follow-up has no statutory content to ground
    # on, so it is refused - proving the in-Conversation answer came from memory.
    result = offline_assistant(corpus).answer("What is the punishment for it?")
    assert result.refused is True


def test_context_is_not_shared_across_conversations(corpus):
    assistant = offline_assistant(corpus)
    first = assistant.start_conversation()
    first.ask("Someone cheated me by fraud and took my property dishonestly")

    # A brand-new Conversation starts fresh: it has none of the first's context,
    # so the very same follow-up has nothing to resolve against and is refused.
    second = assistant.start_conversation()
    result = second.ask("What is the punishment for it?")
    assert result.refused is True


def test_a_self_contained_turn_is_unaffected_by_memory(corpus):
    convo = offline_assistant(corpus).start_conversation()
    convo.ask("What protects my life and personal liberty?")
    # A fully self-contained second question is answered on its own merits, not
    # contaminated by the unrelated prior turn.
    result = convo.ask("What is the punishment for theft of movable property?")
    assert any(c.section_number == "303" for c in result.citations)


def test_answer_keeps_the_users_own_words_not_the_rewrite(corpus):
    convo = offline_assistant(corpus).start_conversation()
    convo.ask("Someone cheated me by fraud and took my property dishonestly")
    followup = convo.ask("What is the punishment for it?")
    assert followup.query == "What is the punishment for it?"


def test_multi_turn_gold_case_exists_and_holds(corpus):
    """A gold case made of a question then a dependent follow-up is run through a
    Conversation and must cite the right section on the final turn."""
    multi_turn = [c for c in load_gold_cases(language=ENGLISH) if c.turns]
    assert multi_turn, "expected a multi-turn gold case"
    report = run_gold_eval(offline_assistant(corpus), multi_turn)
    assert report.failures == []
