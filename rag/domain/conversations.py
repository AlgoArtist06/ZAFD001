"""Per-user persistence of Conversations.

History should follow a user, not a device: the Conversations they started and
the turns within them must be there again when they sign in elsewhere.
:class:`InMemoryConversationStore` is the deterministic,
offline stand-in for that durability; production swaps a Postgres-backed store
behind the same interface so nothing above it changes.

A :class:`ConversationRecord` is owned by exactly one user. Reads are scoped by
``user_id`` so one user can never list or load another's Conversations, and so is
deletion: a user can delete a single Conversation or, exercising the right to
erasure, have every Conversation they own purged.

Conversation content is encrypted at rest. The sensitive fields of a turn - the
words a Citizen typed and the answer they received - pass through the
:class:`~rag.domain.privacy.Cipher` seam before being persisted, and are decrypted on
read, so they never sit in storage in the clear.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rag.domain.privacy import Cipher


@dataclass
class Turn:
    """One exchange in a Conversation: the user's words, the standalone query
    they resolved to (for in-Conversation follow-up memory), and the answer."""

    query: str
    resolved: str
    answer: str
    refused: bool


@dataclass
class ConversationRecord:
    """A persisted Conversation: its owner and its turns."""

    id: str
    user_id: str
    turns: List[Turn] = field(default_factory=list)

    @property
    def title(self) -> str:
        """A sidebar label: the first thing the user asked, or a placeholder."""
        return self.turns[0].query if self.turns else "New chat"


@dataclass(frozen=True)
class ConversationSummary:
    """The sidebar's view of a Conversation: id and title only.

    Listing the sidebar must not load and decrypt every turn of every
    Conversation just to show titles; a summary carries only the title (the
    first turn's query), so a long history costs one decryption per Conversation,
    not one per turn.
    """

    id: str
    title: str


class InMemoryConversationStore:
    """An offline, per-user store of Conversations behind the persistence seam."""

    def __init__(self, cipher: Optional[Cipher] = None) -> None:
        # Insertion-ordered: dicts preserve order, so iterating reversed gives
        # newest-first without depending on the shape of the id string. The
        # records held here are the at-rest form: their turn content is
        # ciphertext, decrypted only when handed back through a read.
        self._by_id: "Dict[str, ConversationRecord]" = {}
        self._ids = itertools.count(1)
        self._cipher = cipher or Cipher()

    def create(self, user_id: str) -> ConversationRecord:
        """Open and persist a new Conversation owned by ``user_id``."""
        stored = ConversationRecord(id=f"conv-{next(self._ids)}", user_id=user_id)
        self._by_id[stored.id] = stored
        return self._decrypt(stored)

    def get(self, user_id: str, conversation_id: str) -> Optional[ConversationRecord]:
        """Load a Conversation, but only for the user who owns it."""
        stored = self._by_id.get(conversation_id)
        if stored is None or stored.user_id != user_id:
            return None
        return self._decrypt(stored)

    def list_for(self, user_id: str) -> List[ConversationRecord]:
        """This user's Conversations, newest first (the sidebar order)."""
        return [
            self._decrypt(r) for r in reversed(self._by_id.values()) if r.user_id == user_id
        ]

    def list_summaries(self, user_id: str) -> List[ConversationSummary]:
        """This user's Conversations as sidebar summaries, newest first.

        Only the first turn is decrypted (for the title), never the whole
        history, so listing stays cheap as a Conversation grows.
        """
        summaries = []
        for r in reversed(self._by_id.values()):
            if r.user_id != user_id:
                continue
            title = self._cipher.decrypt(r.turns[0].query) if r.turns else "New chat"
            summaries.append(ConversationSummary(id=r.id, title=title))
        return summaries

    def append_turn(self, user_id: str, conversation_id: str, turn: Turn) -> None:
        """Record one more turn on an owned Conversation, encrypting its content."""
        stored = self._by_id.get(conversation_id)
        if stored is None or stored.user_id != user_id:
            raise KeyError(conversation_id)
        stored.turns.append(self._encrypt_turn(turn))

    def delete(self, user_id: str, conversation_id: str) -> None:
        """Delete one of the user's Conversations; a no-op if not theirs."""
        stored = self._by_id.get(conversation_id)
        if stored is not None and stored.user_id == user_id:
            del self._by_id[conversation_id]

    def delete_all_for(self, user_id: str) -> None:
        """Purge every Conversation owned by the user (the right to erasure)."""
        for conversation_id in [i for i, r in self._by_id.items() if r.user_id == user_id]:
            del self._by_id[conversation_id]

    def _encrypt_turn(self, turn: Turn) -> Turn:
        return Turn(
            query=self._cipher.encrypt(turn.query),
            resolved=self._cipher.encrypt(turn.resolved),
            answer=self._cipher.encrypt(turn.answer),
            refused=turn.refused,
        )

    def _decrypt(self, stored: ConversationRecord) -> ConversationRecord:
        """A plaintext copy of an at-rest record, for handing back to a reader."""
        return ConversationRecord(
            id=stored.id,
            user_id=stored.user_id,
            turns=[
                Turn(
                    query=self._cipher.decrypt(t.query),
                    resolved=self._cipher.decrypt(t.resolved),
                    answer=self._cipher.decrypt(t.answer),
                    refused=t.refused,
                )
                for t in stored.turns
            ],
        )
