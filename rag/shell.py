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

from typing import List, Optional

from rag.accounts import SessionVerifier
from rag.answer import GroundedAnswer, LegalAssistant
from rag.followup import rewrite_followup
from rag.store import ConversationRecord, InMemoryConversationStore, Turn

# How many recent standalone turns seed follow-up rewriting, mirroring
# Conversation._CONTEXT_TURNS so the persisted path remembers exactly as much as
# the in-process one.
_CONTEXT_TURNS = 4


class Unauthenticated(Exception):
    """Raised when a request carries no valid session - the web layer's 401."""


class ChatShell:
    """Accounts, persisted Conversations, and the grounded answer seam, together."""

    def __init__(
        self,
        assistant: LegalAssistant,
        store: Optional[InMemoryConversationStore] = None,
        verifier: Optional[SessionVerifier] = None,
    ) -> None:
        self._assistant = assistant
        self._store = store or InMemoryConversationStore()
        self._verifier = verifier or SessionVerifier()

    def _account(self, token: str) -> str:
        account = self._verifier.verify(token)
        if account is None:
            raise Unauthenticated()
        return account.user_id

    def conversations(self, token: str) -> List[ConversationRecord]:
        """The signed-in user's Conversations, newest first, for the sidebar."""
        return self._store.list_for(self._account(token))

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
