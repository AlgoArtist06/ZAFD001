"""Privacy and data control through the application shell.

On top of accounts, the shell makes privacy first-class: signup presents the
privacy notice and requires explicit consent before the account is used, and the
consent is recorded. A user can delete a single Conversation, or delete their
account and have all their stored data purged (the right to erasure). The chat
path keeps sensitive content out of plaintext logs.
"""
import logging

import pytest

from rag.domain.accounts import SessionVerifier
from tests.doubles import offline_assistant
from rag.domain.privacy import ConsentLedger, ConsentRequired
from rag.services.chat import ChatShell, Unauthenticated


def _shell(corpus):
    verifier = SessionVerifier()
    consent = ConsentLedger()
    shell = ChatShell(offline_assistant(corpus), verifier=verifier, consent=consent)
    return shell, verifier, consent


def test_the_shell_presents_the_privacy_notice(corpus):
    shell, _, _ = _shell(corpus)
    notice = shell.privacy_notice.lower()
    assert "third-party" in notice or "third party" in notice
    assert "llm" in notice or "language model" in notice


def test_signup_without_consent_is_refused(corpus):
    shell, _, consent = _shell(corpus)
    with pytest.raises(ConsentRequired):
        shell.sign_up("user-asha", accept_privacy_notice=False)
    assert consent.has_consented("user-asha") is False


def test_signup_with_consent_records_it_and_returns_a_usable_session(corpus):
    shell, _, consent = _shell(corpus)
    token = shell.sign_up("user-asha", accept_privacy_notice=True)
    assert consent.has_consented("user-asha") is True
    # The returned session works: the user can open a Conversation.
    convo = shell.new_chat(token)
    assert convo.id


def test_a_user_can_delete_a_single_conversation(corpus):
    shell, _, _ = _shell(corpus)
    token = shell.sign_up("user-asha", accept_privacy_notice=True)
    keep = shell.new_chat(token)
    drop = shell.new_chat(token)

    shell.delete_conversation(token, drop.id)

    assert [c.id for c in shell.conversations(token)] == [keep.id]


def test_deleting_an_account_purges_all_stored_data_and_consent(corpus):
    shell, _, consent = _shell(corpus)
    token = shell.sign_up("user-asha", accept_privacy_notice=True)
    convo = shell.new_chat(token)
    shell.send(token, convo.id, "punishment for theft of movable property")

    shell.delete_account(token)

    # The data is actually gone: the prior session can no longer reach it.
    with pytest.raises(Unauthenticated):
        shell.history(token, convo.id)
    assert consent.has_consented("user-asha") is False


def test_sensitive_query_content_never_reaches_plaintext_logs(corpus, caplog):
    shell, _, _ = _shell(corpus)
    token = shell.sign_up("user-asha", accept_privacy_notice=True)
    convo = shell.new_chat(token)

    secret = "my landlord illegally evicted me from my home"
    with caplog.at_level(logging.DEBUG):
        shell.send(token, convo.id, secret)

    assert secret not in caplog.text
    assert "landlord" not in caplog.text
