"""Per-user persistence of Conversations.

History should follow a user, not a device: the Conversations they started, the
Mode each was opened in, and the turns within them must be there again when they
sign in elsewhere. :class:`InMemoryConversationStore` is the deterministic,
offline stand-in for that durability; production swaps a Postgres-backed store
behind the same interface so nothing above it changes.

A :class:`ConversationRecord` is owned by exactly one user. Reads are scoped by
``user_id`` so one user can never list or load another's Conversations, and so is
deletion: a user can delete a single Conversation or, exercising the right to
erasure, have every Conversation they own purged.

Conversation content is encrypted at rest. The sensitive fields of a turn - the
words a Citizen typed and the answer they received - pass through the
:class:`~rag.privacy.Cipher` seam before being persisted, and are decrypted on
read, so they never sit in storage in the clear.
"""
from __future__ import annotations

import itertools
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from rag.privacy import Cipher


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

    def __init__(self, cipher: Optional[Cipher] = None) -> None:
        # Insertion-ordered: dicts preserve order, so iterating reversed gives
        # newest-first without depending on the shape of the id string. The
        # records held here are the at-rest form: their turn content is
        # ciphertext, decrypted only when handed back through a read.
        self._by_id: "Dict[str, ConversationRecord]" = {}
        self._ids = itertools.count(1)
        self._cipher = cipher or Cipher()

    def create(self, user_id: str, mode: str) -> ConversationRecord:
        """Open and persist a new Conversation owned by ``user_id``."""
        stored = ConversationRecord(id=f"conv-{next(self._ids)}", user_id=user_id, mode=mode)
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
            mode=stored.mode,
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


# Two SQL dialects sit behind the same store: Postgres in production, and SQLite
# as the deterministic, dependency-free offline driver the suite runs against.
# Only the placeholder marker and two column types differ; the queries are one.
_DIALECTS = {
    "postgres": {
        "placeholder": "%s",
        "serial_pk": "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
        "bool": "BOOLEAN",
    },
    "sqlite": {
        "placeholder": "?",
        "serial_pk": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "bool": "INTEGER",
    },
}


class PostgresConversationStore:
    """A durable, per-user store of Conversations behind the persistence seam.

    The same interface as :class:`InMemoryConversationStore`, so nothing above it
    changes; only the backing moves to Postgres, which is what makes history
    durable across a reload and visible on another device for the same user.

    Every operation opens a fresh connection from the injected ``connect``
    factory, so the store holds no in-process state: the database is the single
    source of truth, and a second connection (another device, or the same one
    after a reload) sees exactly what the first persisted. Reads and writes are
    scoped by ``user_id`` in the ``WHERE`` clause, so one user can never list,
    load, or delete another's Conversations. Turn content is encrypted through the
    :class:`~rag.privacy.Cipher` seam before it is written and decrypted on read,
    so it is never at rest in the clear; the store logs nothing, so no plaintext
    content reaches a log.
    """

    def __init__(
        self,
        connect: Callable[[], Any],
        *,
        cipher: Optional[Cipher] = None,
        dialect: str = "postgres",
    ) -> None:
        self._connect = connect
        self._cipher = cipher or Cipher()
        self._dialect = _DIALECTS[dialect]
        self._ensure_schema()

    @classmethod
    def from_dsn(cls, dsn: str, *, cipher: Optional[Cipher] = None) -> "PostgresConversationStore":
        """Build a store that connects to Postgres at ``dsn`` (e.g. ``DATABASE_URL``)."""
        import psycopg  # imported lazily so the offline path needs no driver

        return cls(lambda: psycopg.connect(dsn), cipher=cipher, dialect="postgres")

    def create(self, user_id: str, mode: str) -> ConversationRecord:
        """Open and persist a new Conversation owned by ``user_id``."""
        conversation_id = f"conv-{uuid.uuid4().hex}"
        with self._cursor() as cur:
            cur.execute(
                self._q("INSERT INTO conversations (id, user_id, mode) VALUES (?, ?, ?)"),
                (conversation_id, user_id, mode),
            )
        return ConversationRecord(id=conversation_id, user_id=user_id, mode=mode)

    def get(self, user_id: str, conversation_id: str) -> Optional[ConversationRecord]:
        """Load a Conversation, but only for the user who owns it."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "SELECT id, user_id, mode FROM conversations "
                    "WHERE id = ? AND user_id = ?"
                ),
                (conversation_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return ConversationRecord(
                id=row[0], user_id=row[1], mode=row[2], turns=self._load_turns(cur, row[0])
            )

    def list_for(self, user_id: str) -> List[ConversationRecord]:
        """This user's Conversations, newest first (the sidebar order)."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "SELECT id, user_id, mode FROM conversations "
                    "WHERE user_id = ? ORDER BY seq DESC"
                ),
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                ConversationRecord(
                    id=row[0], user_id=row[1], mode=row[2], turns=self._load_turns(cur, row[0])
                )
                for row in rows
            ]

    def append_turn(self, user_id: str, conversation_id: str, turn: Turn) -> None:
        """Record one more turn on an owned Conversation, encrypting its content."""
        with self._cursor() as cur:
            cur.execute(
                self._q("SELECT 1 FROM conversations WHERE id = ? AND user_id = ?"),
                (conversation_id, user_id),
            )
            if cur.fetchone() is None:
                raise KeyError(conversation_id)
            cur.execute(
                self._q(
                    "INSERT INTO turns (conversation_id, query, resolved, answer, refused) "
                    "VALUES (?, ?, ?, ?, ?)"
                ),
                (
                    conversation_id,
                    self._cipher.encrypt(turn.query),
                    self._cipher.encrypt(turn.resolved),
                    self._cipher.encrypt(turn.answer),
                    turn.refused,
                ),
            )

    def delete(self, user_id: str, conversation_id: str) -> None:
        """Delete one of the user's Conversations; a no-op if not theirs."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "DELETE FROM turns WHERE conversation_id IN "
                    "(SELECT id FROM conversations WHERE id = ? AND user_id = ?)"
                ),
                (conversation_id, user_id),
            )
            cur.execute(
                self._q("DELETE FROM conversations WHERE id = ? AND user_id = ?"),
                (conversation_id, user_id),
            )

    def delete_all_for(self, user_id: str) -> None:
        """Purge every Conversation owned by the user (the right to erasure)."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "DELETE FROM turns WHERE conversation_id IN "
                    "(SELECT id FROM conversations WHERE user_id = ?)"
                ),
                (user_id,),
            )
            cur.execute(
                self._q("DELETE FROM conversations WHERE user_id = ?"), (user_id,)
            )

    def _load_turns(self, cur: Any, conversation_id: str) -> List[Turn]:
        cur.execute(
            self._q(
                "SELECT query, resolved, answer, refused FROM turns "
                "WHERE conversation_id = ? ORDER BY seq"
            ),
            (conversation_id,),
        )
        return [
            Turn(
                query=self._cipher.decrypt(query),
                resolved=self._cipher.decrypt(resolved),
                answer=self._cipher.decrypt(answer),
                refused=bool(refused),
            )
            for query, resolved, answer, refused in cur.fetchall()
        ]

    def _ensure_schema(self) -> None:
        serial_pk = self._dialect["serial_pk"]
        bool_type = self._dialect["bool"]
        with self._cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS conversations ("
                f"  seq {serial_pk},"
                f"  id TEXT NOT NULL UNIQUE,"
                f"  user_id TEXT NOT NULL,"
                f"  mode TEXT NOT NULL"
                f")"
            )
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS turns ("
                f"  seq {serial_pk},"
                f"  conversation_id TEXT NOT NULL,"
                f"  query TEXT NOT NULL,"
                f"  resolved TEXT NOT NULL,"
                f"  answer TEXT NOT NULL,"
                f"  refused {bool_type} NOT NULL"
                f")"
            )

    def _q(self, sql: str) -> str:
        """Render a ``?``-marked query in the active dialect's placeholder style."""
        return sql.replace("?", self._dialect["placeholder"])

    @contextmanager
    def _cursor(self):
        """A committed cursor on a fresh connection - no state lives in-process."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        finally:
            conn.close()
