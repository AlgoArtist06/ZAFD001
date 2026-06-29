"""Per-user persistence of Conversations.

History should follow a user, not a device: the Conversations they started, the
Mode each was opened in, and the turns within them must be there again when they
sign in elsewhere. :class:`InMemoryConversationStore` is the deterministic,
offline stand-in for that durability; production swaps a Postgres-backed store
behind the same interface so nothing above it changes.

A :class:`ConversationRecord` is owned by exactly one user. Reads are scoped by
``user_id`` so one user can never list or load another's Conversations.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
    """A persisted Conversation: its owner, its locked Mode, and its turns."""

    id: str
    user_id: str
    mode: str
    turns: List[Turn] = field(default_factory=list)

    @property
    def title(self) -> str:
        """A sidebar label: the first thing the user asked, or a placeholder."""
        return self.turns[0].query if self.turns else "New chat"


class InMemoryConversationStore:
    """An offline, per-user store of Conversations behind the persistence seam."""

    def __init__(self) -> None:
        # Insertion-ordered: dicts preserve order, so iterating reversed gives
        # newest-first without depending on the shape of the id string.
        self._by_id: "Dict[str, ConversationRecord]" = {}
        self._ids = itertools.count(1)

    def create(self, user_id: str, mode: str) -> ConversationRecord:
        """Open and persist a new Conversation owned by ``user_id``."""
        record = ConversationRecord(id=f"conv-{next(self._ids)}", user_id=user_id, mode=mode)
        self._by_id[record.id] = record
        return record

    def get(self, user_id: str, conversation_id: str) -> Optional[ConversationRecord]:
        """Load a Conversation, but only for the user who owns it."""
        record = self._by_id.get(conversation_id)
        if record is None or record.user_id != user_id:
            return None
        return record

    def list_for(self, user_id: str) -> List[ConversationRecord]:
        """This user's Conversations, newest first (the sidebar order)."""
        return [r for r in reversed(self._by_id.values()) if r.user_id == user_id]

    def append_turn(self, user_id: str, conversation_id: str, turn: Turn) -> None:
        """Record one more turn on an owned Conversation."""
        record = self.get(user_id, conversation_id)
        if record is None:
            raise KeyError(conversation_id)
        record.turns.append(turn)
