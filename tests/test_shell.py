"""The application shell: accounts + persisted Conversations + the answer seam.

The shell is what the ChatGPT-style UI talks to. It authenticates the session,
keeps the user's Conversations, and routes every message through the existing
grounded answer seam so guardrails and multilingual support stay intact. Mode is
chosen when a Conversation starts and fixed thereafter; follow-up memory works
across the persisted Conversation, not just within one process.
"""
import pytest

from rag.accounts import SessionVerifier
from rag.answer import LegalAssistant
from rag.shell import ChatShell, Unauthenticated


def _shell(corpus):
    assistant = LegalAssistant(corpus)
    verifier = SessionVerifier()
    return ChatShell(assistant, verifier=verifier), verifier


def test_an_unknown_session_cannot_act(corpus):
    shell, _ = _shell(corpus)
    with pytest.raises(Unauthenticated):
        shell.conversations("bogus-token")


def test_new_chat_records_the_chosen_mode_and_shows_in_the_sidebar(corpus):
    shell, verifier = _shell(corpus)
    token = verifier.sign_in("user-asha")
    convo = shell.new_chat(token, mode="professional")
    listed = shell.conversations(token)
    assert convo.mode == "professional"
    assert [(c.id, c.mode) for c in listed] == [(convo.id, "professional")]


def test_a_message_routes_through_the_grounded_answer_seam(corpus):
    shell, verifier = _shell(corpus)
    token = verifier.sign_in("user-asha")
    convo = shell.new_chat(token, mode="citizen")
    result = shell.send(token, convo.id, "punishment for theft of movable property")
    assert any(c.section_number == "303" for c in result.citations)


def test_guardrails_still_refuse_an_advice_request(corpus):
    shell, verifier = _shell(corpus)
    token = verifier.sign_in("user-asha")
    convo = shell.new_chat(token, mode="citizen")
    result = shell.send(token, convo.id, "should I sue my landlord and will I win?")
    assert result.refused is True


def test_multilingual_support_answers_hindi_in_hindi(corpus):
    shell, verifier = _shell(corpus)
    token = verifier.sign_in("user-asha")
    convo = shell.new_chat(token, mode="citizen")
    result = shell.send(token, convo.id, "चोरी की सजा क्या है?")
    assert result.language == "hi"


def test_conversation_is_persisted_and_visible_from_another_device(corpus):
    # A second ChatShell over the same store and verifier is "another device":
    # the user signs in and finds their Conversation and its turns waiting.
    assistant = LegalAssistant(corpus)
    verifier = SessionVerifier()
    from rag.store import InMemoryConversationStore

    store = InMemoryConversationStore()
    laptop = ChatShell(assistant, store=store, verifier=verifier)
    token = verifier.sign_in("user-asha")
    convo = laptop.new_chat(token, mode="citizen")
    laptop.send(token, convo.id, "punishment for theft of movable property")

    phone = ChatShell(assistant, store=store, verifier=verifier)
    seen = phone.conversations(token)
    assert [c.id for c in seen] == [convo.id]
    assert phone.history(token, convo.id)[0].query == "punishment for theft of movable property"


def test_follow_up_memory_works_across_the_persisted_conversation(corpus):
    shell, verifier = _shell(corpus)
    token = verifier.sign_in("user-asha")
    convo = shell.new_chat(token, mode="citizen")
    shell.send(token, convo.id, "Someone cheated me by fraud and took my property dishonestly")
    followup = shell.send(token, convo.id, "What is the punishment for it?")
    assert followup.refused is False
    assert any(c.section_number == "318" for c in followup.citations)


def test_every_turn_answers_in_the_conversations_locked_mode(corpus):
    shell, verifier = _shell(corpus)
    token = verifier.sign_in("user-asha")
    convo = shell.new_chat(token, mode="professional")
    result = shell.send(token, convo.id, "punishment for theft and cheating")
    assert result.mode == "professional"
    assert {"303", "318"} <= {c.section_number for c in result.citations}
