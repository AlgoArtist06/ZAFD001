"""The application shell behind the ChatGPT-style UI.

This is the single object the web layer talks to. It authenticates a session
through the :mod:`rag.accounts` seam, persists each user's Conversations through
the :mod:`rag.store` seam, and routes every message through the existing
:class:`~rag.answer.LegalAssistant` answer seam - so guardrails, the IPC-to-BNS
recognition, and multilingual support are unchanged on the chat path.

Mode is chosen when a Conversation starts and fixed for its lifetime. Follow-up
memory works across the *persisted* Conversation, not just within one process:
the bounded recent context is rebuilt from the stored turns before each message
is resolved, so a dependent follow-up survives a page reload or a new device.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from rag.accounts import SessionVerifier
from rag.answer import GroundedAnswer, LegalAssistant
from rag.followup import rewrite_followup
from rag.privacy import PRIVACY_NOTICE, ConsentLedger, ConsentRequired, redact
from rag.store import ConversationRecord, InMemoryConversationStore, Turn

# How many recent standalone turns seed follow-up rewriting, mirroring
# Conversation._CONTEXT_TURNS so the persisted path remembers exactly as much as
# the in-process one.
_CONTEXT_TURNS = 4

# The shell's own log. Messages here name conversations and lengths, never the
# words a Citizen typed or the answer they received - those are redacted first.
_LOG = logging.getLogger(__name__)


class Unauthenticated(Exception):
    """Raised when a request carries no valid session - the web layer's 401."""


class ChatShell:
    """Accounts, persisted Conversations, and the grounded answer seam, together."""

    def __init__(
        self,
        assistant: LegalAssistant,
        store: Optional[InMemoryConversationStore] = None,
        verifier: Optional[SessionVerifier] = None,
        consent: Optional[ConsentLedger] = None,
    ) -> None:
        self._assistant = assistant
        self._store = store or InMemoryConversationStore()
        self._verifier = verifier or SessionVerifier()
        self._consent = consent or ConsentLedger()

    @property
    def privacy_notice(self) -> str:
        """The clear privacy notice shown at signup before consent is given."""
        return PRIVACY_NOTICE

    def sign_up(self, user_id: str, *, accept_privacy_notice: bool) -> str:
        """Sign a user up, recording explicit consent to the privacy notice.

        Consent is a precondition, not an afterthought: without it no session is
        issued, so an account cannot be used before its owner has accepted the
        notice. With it, the consent is recorded and a usable session returned.
        """
        if not accept_privacy_notice:
            raise ConsentRequired()
        self._consent.record(user_id)
        return self._verifier.sign_in(user_id)

    def record_consent(self, token: str, accept_privacy_notice: bool) -> None:
        """Record the signed-in user's explicit consent to the privacy notice.

        The HTTP-side counterpart to :meth:`sign_up`: when signup and login are
        Clerk's, the account is already authenticated and the app's job is only
        to record consent to the notice it presented.
        """
        if not accept_privacy_notice:
            raise ConsentRequired()
        self._consent.record(self._account(token))

    def _account(self, token: str) -> str:
        account = self._verifier.verify(token)
        if account is None:
            raise Unauthenticated()
        return account.user_id

    def conversations(self, token: str) -> List[ConversationRecord]:
        """The signed-in user's Conversations, newest first, for the sidebar."""
        return self._store.list_for(self._account(token))

    def delete_conversation(self, token: str, conversation_id: str) -> None:
        """Delete a single Conversation the signed-in user owns."""
        self._require(token, conversation_id)
        self._store.delete(self._account(token), conversation_id)

    def delete_account(self, token: str) -> None:
        """Erase the user's account and all stored data (right to erasure)."""
        user_id = self._account(token)
        self._store.delete_all_for(user_id)
        self._consent.erase(user_id)

    def new_chat(self, token: str, mode: str = "citizen") -> ConversationRecord:
        """Open a new Conversation for the user with its Mode locked at start."""
        return self._store.create(self._account(token), mode)

    def history(self, token: str, conversation_id: str) -> List[Turn]:
        """The turns of one of the user's Conversations, oldest first."""
        record = self._require(token, conversation_id)
        return record.turns

    def send(
        self, token: str, conversation_id: str, query: str, language: str = "en"
    ) -> GroundedAnswer:
        """Answer one message in a persisted Conversation and record the turn.

        A dependent follow-up is first rewritten into a standalone query using the
        bounded recent context rebuilt from the stored turns, then routed through
        the answer seam in the Conversation's locked Mode. The user's own words are
        kept on the returned answer; the standalone query is stored so later
        follow-ups can build on it.
        """
        record = self._require(token, conversation_id)
        # Observability without exposure: the log names the Conversation and the
        # message length, never the words themselves, which are redacted here.
        _LOG.info("message in %s (%s)", conversation_id, redact(query))
        recent = [t.resolved for t in record.turns][-_CONTEXT_TURNS:]
        resolved = rewrite_followup(query, recent)
        result = self._assistant.answer(resolved, mode=record.mode, language=language)
        result.query = query
        self._store.append_turn(
            record.user_id,
            conversation_id,
            Turn(query=query, resolved=resolved, answer=result.text, refused=result.refused),
        )
        return result

    def _require(self, token: str, conversation_id: str) -> ConversationRecord:
        record = self._store.get(self._account(token), conversation_id)
        if record is None:
            raise Unauthenticated()
        return record
