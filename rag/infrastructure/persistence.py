"""Durable persistence behind the conversation-store and consent seams.

The same interfaces as the offline defaults
(:class:`~rag.domain.conversations.InMemoryConversationStore` and
:class:`~rag.domain.privacy.ConsentLedger`), so nothing above them changes;
only the backing moves to SQL, which is what makes history and consent durable
across a restart and visible on another device for the same user.

Two SQL dialects sit behind the same stores: Postgres in production, and SQLite
as the deterministic, dependency-free offline driver the suite runs against.
Only the placeholder marker and two column types differ; the queries are one.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from rag.domain.conversations import ConversationRecord, ConversationSummary, Turn
from rag.domain.privacy import Cipher, ConsentRecord, NOTICE_VERSION


class FernetCipher:
    """Authenticated encryption at rest, behind the :class:`Cipher` seam.

    The offline :class:`~rag.domain.privacy.Cipher` is a deterministic XOR
    stand-in whose stored form is merely not-plaintext; it must never back a
    real deployment, because the privacy notice promises conversation content is
    encrypted at rest. Fernet is AES-128-CBC with an HMAC-SHA256 tag, so stored
    content is both confidential and tamper-evident. The key is a urlsafe base64
    32-byte Fernet key supplied from the environment and never committed;
    generate one with::

        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """

    def __init__(self, key: str) -> None:
        from cryptography.fernet import Fernet  # lazy: offline path needs no crypto

        self._fernet = Fernet(key.encode("ascii") if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


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


class _SqlStore:
    """Shared SQL plumbing: a dialect and a fresh committed cursor per operation."""

    def __init__(self, connect: Callable[[], Any], dialect: str) -> None:
        self._connect = connect
        self._dialect = _DIALECTS[dialect]

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


class DurableConsentLedger(_SqlStore):
    """Consent records that survive a restart, behind the ConsentLedger seam.

    Consent is a legal fact, so losing it on a process restart is not an option:
    a consented user would be refused answers (403) until they consented again,
    and the original consent date would be gone. Rows hold no free text - only
    the user id, the notice version, and the timestamp - so they are stored in
    the clear where ``user_id`` must stay queryable (see ADR 0005).
    """

    def __init__(self, connect: Callable[[], Any], *, dialect: str = "postgres") -> None:
        super().__init__(connect, dialect)
        self._ensure_schema()

    @classmethod
    def from_dsn(cls, dsn: str) -> "DurableConsentLedger":
        """Build a ledger that connects to Postgres at ``dsn`` (e.g. ``DATABASE_URL``)."""
        import psycopg  # imported lazily so the offline path needs no driver

        return cls(lambda: psycopg.connect(dsn), dialect="postgres")

    def record(self, user_id: str, notice_version: str = NOTICE_VERSION) -> ConsentRecord:
        """Record a user's explicit consent to a version of the notice."""
        consented_at = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(self._q("DELETE FROM consents WHERE user_id = ?"), (user_id,))
            cur.execute(
                self._q(
                    "INSERT INTO consents (user_id, notice_version, consented_at) "
                    "VALUES (?, ?, ?)"
                ),
                (user_id, notice_version, consented_at),
            )
        return ConsentRecord(user_id=user_id, notice_version=notice_version)

    def consent_for(self, user_id: str) -> Optional[ConsentRecord]:
        """The user's recorded consent, or ``None`` if they have not consented."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "SELECT user_id, notice_version FROM consents WHERE user_id = ?"
                ),
                (user_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return ConsentRecord(user_id=row[0], notice_version=row[1])

    def has_consented(self, user_id: str) -> bool:
        return self.consent_for(user_id) is not None

    def erase(self, user_id: str) -> None:
        """Forget a user's consent record (part of the right to erasure)."""
        with self._cursor() as cur:
            cur.execute(self._q("DELETE FROM consents WHERE user_id = ?"), (user_id,))

    def _ensure_schema(self) -> None:
        with self._cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS consents ("
                "  user_id TEXT PRIMARY KEY,"
                "  notice_version TEXT NOT NULL,"
                "  consented_at TEXT NOT NULL"
                ")"
            )


class PostgresConversationStore(_SqlStore):
    """A durable, per-user store of Conversations behind the persistence seam.

    Every operation opens a fresh connection from the injected ``connect``
    factory, so the store holds no in-process state: the database is the single
    source of truth, and a second connection (another device, or the same one
    after a reload) sees exactly what the first persisted. Reads and writes are
    scoped by ``user_id`` in the ``WHERE`` clause, so one user can never list,
    load, or delete another's Conversations. Turn content is encrypted through
    the :class:`~rag.domain.privacy.Cipher` seam before it is written and
    decrypted on read, so it is never at rest in the clear; the store logs
    nothing, so no plaintext content reaches a log.
    """

    def __init__(
        self,
        connect: Callable[[], Any],
        *,
        cipher: Optional[Cipher] = None,
        dialect: str = "postgres",
    ) -> None:
        super().__init__(connect, dialect)
        self._cipher = cipher or Cipher()
        self._ensure_schema()

    @classmethod
    def from_dsn(cls, dsn: str, *, cipher: Optional[Cipher] = None) -> "PostgresConversationStore":
        """Build a store that connects to Postgres at ``dsn`` (e.g. ``DATABASE_URL``)."""
        import psycopg  # imported lazily so the offline path needs no driver

        return cls(lambda: psycopg.connect(dsn), cipher=cipher, dialect="postgres")

    def create(self, user_id: str) -> ConversationRecord:
        """Open and persist a new Conversation owned by ``user_id``."""
        conversation_id = f"conv-{uuid.uuid4().hex}"
        with self._cursor() as cur:
            cur.execute(
                self._q("INSERT INTO conversations (id, user_id) VALUES (?, ?)"),
                (conversation_id, user_id),
            )
        return ConversationRecord(id=conversation_id, user_id=user_id)

    def get(self, user_id: str, conversation_id: str) -> Optional[ConversationRecord]:
        """Load a Conversation, but only for the user who owns it."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "SELECT id, user_id FROM conversations "
                    "WHERE id = ? AND user_id = ?"
                ),
                (conversation_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return ConversationRecord(
                id=row[0], user_id=row[1], turns=self._load_turns(cur, row[0])
            )

    def list_for(self, user_id: str) -> List[ConversationRecord]:
        """This user's Conversations, newest first (the sidebar order)."""
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "SELECT id, user_id FROM conversations "
                    "WHERE user_id = ? ORDER BY seq DESC"
                ),
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                ConversationRecord(
                    id=row[0], user_id=row[1], turns=self._load_turns(cur, row[0])
                )
                for row in rows
            ]

    def list_summaries(self, user_id: str) -> List[ConversationSummary]:
        """This user's Conversations as sidebar summaries, newest first.

        The title is the first turn's query, fetched with a correlated subquery so
        only that one row per Conversation is read and decrypted, never the whole
        history. Everything else the sidebar needs (id) is on the row.
        """
        with self._cursor() as cur:
            cur.execute(
                self._q(
                    "SELECT c.id, "
                    "(SELECT t.query FROM turns t WHERE t.conversation_id = c.id "
                    " ORDER BY t.seq LIMIT 1) "
                    "FROM conversations c WHERE c.user_id = ? ORDER BY c.seq DESC"
                ),
                (user_id,),
            )
            rows = cur.fetchall()
        return [
            ConversationSummary(
                id=row[0],
                title=self._cipher.decrypt(row[1]) if row[1] else "New chat",
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
                f"  user_id TEXT NOT NULL"
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
