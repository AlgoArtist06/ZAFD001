"""The Postgres-backed Conversation store, behind the same persistence seam.

Issue 15. Conversation history must be durable and cross-device, so the store
moves from in-memory to Postgres without changing the interface the shell, the
accounts seam, and the answer seam sit on top of. These tests exercise that
contract - the same one :mod:`tests.test_store` pins for the in-memory stand-in -
plus the two guarantees that only durable storage can make: a Conversation
survives a reload and is visible on another device, and its content is encrypted
at rest.

The suite stays dependency-free by running the store's real SQL against an
offline SQLite driver, the deterministic stand-in for a live Postgres. Each
``connect`` opens a fresh connection to the same file, so "another device" is
just another connection - exactly how a second browser reaches one Postgres.
"""
import logging
import sqlite3

import pytest

from rag.domain.conversations import Turn
from rag.domain.privacy import Cipher
from rag.infrastructure.persistence import PostgresConversationStore


@pytest.fixture
def connect(tmp_path):
    """A connection factory at a shared file - one Postgres, many connections."""
    path = str(tmp_path / "conversations.db")
    return lambda: sqlite3.connect(path)


@pytest.fixture
def store(connect):
    return PostgresConversationStore(connect, dialect="sqlite")


def test_a_new_conversation_records_its_owner(store):
    convo = store.create(user_id="user-asha")
    assert convo.user_id == "user-asha"
    assert convo.turns == []


def test_conversations_are_listed_for_their_owner_newest_first(store):
    first = store.create(user_id="user-asha")
    second = store.create(user_id="user-asha")
    listed = store.list_for("user-asha")
    assert [c.id for c in listed] == [second.id, first.id]


def test_citations_round_trip_with_a_turn(store):
    convo = store.create(user_id="user-asha")
    cited = [{"reference": "BNS (2023), Section 303", "verbatim": "Whoever...", "url": "https://x"}]
    store.append_turn(
        "user-asha", convo.id, Turn("theft?", "theft?", "ans", False, citations=cited)
    )
    loaded = store.get("user-asha", convo.id)
    assert loaded.turns[0].citations == cited


def test_pre_citations_database_is_migrated_and_old_rows_still_read(connect):
    """A database created before the citations column gains it on open, and its
    existing rows read back with no citations rather than failing decryption."""
    cipher = Cipher()
    conn = connect()
    # The dual-mode-era schema: a NOT NULL mode column the code no longer fills.
    conn.execute(
        "CREATE TABLE conversations ("
        " seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,"
        " user_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'citizen')"
    )
    conn.execute(
        "CREATE TABLE turns ("
        " seq INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " query TEXT NOT NULL, resolved TEXT NOT NULL, answer TEXT NOT NULL,"
        " refused INTEGER NOT NULL)"
    )
    conn.execute(
        "INSERT INTO conversations (id, user_id) VALUES ('conv-old', 'user-asha')"
    )
    conn.execute(
        "INSERT INTO turns (conversation_id, query, resolved, answer, refused) "
        "VALUES (?, ?, ?, ?, 0)",
        ("conv-old", cipher.encrypt("theft?"), cipher.encrypt("theft?"), cipher.encrypt("BNS 303")),
    )
    conn.commit()
    conn.close()

    # Opening the store migrates the schema; the old row reads back whole.
    store = PostgresConversationStore(connect, dialect="sqlite")
    loaded = store.get("user-asha", "conv-old")
    assert loaded.turns[0].query == "theft?"
    assert loaded.turns[0].citations == []

    # And new turns with citations persist alongside the migrated row.
    cited = [{"reference": "r", "verbatim": "v", "url": "u"}]
    store.append_turn("user-asha", "conv-old", Turn("q", "q", "a", False, citations=cited))
    assert store.get("user-asha", "conv-old").turns[1].citations == cited

    # The dropped mode column no longer blocks creating a new Conversation.
    fresh = store.create(user_id="user-asha")
    assert fresh.id


def test_summaries_carry_the_first_turn_as_title(store):
    convo = store.create("user-asha")
    store.append_turn(
        "user-asha", convo.id, Turn("first question", "first question", "ans", False)
    )
    store.append_turn("user-asha", convo.id, Turn("second", "second", "ans", False))
    empty = store.create("user-asha")

    summaries = {s.id: s for s in store.list_summaries("user-asha")}

    assert summaries[convo.id].title == "first question"  # first turn, decrypted
    assert summaries[empty.id].title == "New chat"  # no turns yet


def test_one_user_never_sees_anothers_conversations(store):
    store.create(user_id="user-asha")
    store.create(user_id="user-ravi")
    assert [c.user_id for c in store.list_for("user-asha")] == ["user-asha"]


def test_a_user_cannot_load_another_users_conversation_by_id(store):
    ashas = store.create(user_id="user-asha")
    assert store.get("user-ravi", ashas.id) is None


def test_appended_turns_accumulate_in_order(store):
    convo = store.create(user_id="user-asha")
    store.append_turn("user-asha", convo.id, Turn("a", "a", "ans-a", False))
    store.append_turn("user-asha", convo.id, Turn("b", "b", "ans-b", False))
    assert [t.query for t in store.get("user-asha", convo.id).turns] == ["a", "b"]


def test_appending_to_a_missing_conversation_is_an_error(store):
    with pytest.raises(KeyError):
        store.append_turn("user-asha", "no-such-id", Turn("a", "a", "x", False))


def test_a_user_can_delete_one_of_their_conversations(store):
    keep = store.create(user_id="user-asha")
    drop = store.create(user_id="user-asha")

    store.delete("user-asha", drop.id)

    assert store.get("user-asha", drop.id) is None
    assert [c.id for c in store.list_for("user-asha")] == [keep.id]


def test_a_user_cannot_delete_another_users_conversation(store):
    ashas = store.create(user_id="user-asha")

    store.delete("user-ravi", ashas.id)

    assert store.get("user-asha", ashas.id) is not None


def test_deleting_all_data_for_a_user_purges_only_their_conversations(store):
    store.create(user_id="user-asha")
    store.create(user_id="user-asha")
    ravis = store.create(user_id="user-ravi")

    store.delete_all_for("user-asha")

    assert store.list_for("user-asha") == []
    assert [c.id for c in store.list_for("user-ravi")] == [ravis.id]


def test_history_survives_a_reload_and_is_visible_on_another_device(connect):
    # The Conversation is created and a turn recorded on "this device".
    on_this_device = PostgresConversationStore(connect, dialect="sqlite")
    convo = on_this_device.create(user_id="user-asha")
    on_this_device.append_turn(
        "user-asha", convo.id, Turn("theft?", "theft?", "BNS 303 ...", False)
    )

    # A wholly separate store over the same Postgres is "another device" (and,
    # equally, the same device after a reload): it loads the persisted history.
    on_another_device = PostgresConversationStore(connect, dialect="sqlite")
    restored = on_another_device.get("user-asha", convo.id)
    assert restored is not None
    assert [t.query for t in restored.turns] == ["theft?"]
    assert [c.id for c in on_another_device.list_for("user-asha")] == [convo.id]


class _SpyCipher:
    """Records what it was asked to encrypt; reversible for round-trips."""

    def __init__(self) -> None:
        self.encrypted: list = []

    def encrypt(self, plaintext: str) -> str:
        self.encrypted.append(plaintext)
        return "enc:" + plaintext[::-1]

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext[len("enc:"):][::-1]


def test_turn_content_is_encrypted_at_rest_and_decrypted_on_read(connect):
    cipher = _SpyCipher()
    store = PostgresConversationStore(connect, cipher=cipher, dialect="sqlite")
    convo = store.create(user_id="user-asha")
    store.append_turn(
        "user-asha",
        convo.id,
        Turn(query="my landlord", resolved="landlord eviction", answer="BNS says...", refused=False),
    )

    # The sensitive fields passed through the cipher before being persisted.
    assert "my landlord" in cipher.encrypted
    assert "BNS says..." in cipher.encrypted

    # What actually sits in the database is ciphertext, never the plaintext.
    raw = connect()
    try:
        stored = raw.execute("SELECT query, resolved, answer FROM turns").fetchall()
    finally:
        raw.close()
    flat = " ".join(col for row in stored for col in row)
    assert "my landlord" not in flat
    assert "landlord eviction" not in flat
    assert "BNS says..." not in flat

    # ... yet a read hands back the plaintext, unchanged.
    turn = store.get("user-asha", convo.id).turns[0]
    assert turn.query == "my landlord"
    assert turn.answer == "BNS says..."


def test_sensitive_content_never_reaches_the_logs(store, caplog):
    with caplog.at_level(logging.DEBUG):
        convo = store.create(user_id="user-asha")
        store.append_turn(
            "user-asha",
            convo.id,
            Turn(query="my landlord evicted me", resolved="landlord eviction", answer="BNS says...", refused=False),
        )
        store.get("user-asha", convo.id)
        store.list_for("user-asha")

    logged = caplog.text
    assert "my landlord evicted me" not in logged
    assert "landlord eviction" not in logged
    assert "BNS says..." not in logged
