"""Per-user persistence of Conversations.

A Conversation belongs to the user who started it, carries the Mode chosen at its
start, and accumulates turns. The store keeps these so a user's history follows
them: signing in from another device and listing Conversations returns the same
records. One user never sees another user's Conversations.

The in-memory store here is the deterministic offline stand-in; production swaps
a Postgres-backed store behind the same interface.
"""
import pytest

from rag.store import InMemoryConversationStore, Turn


def test_a_new_conversation_records_its_owner_and_mode():
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha", mode="professional")
    assert convo.user_id == "user-asha"
    assert convo.mode == "professional"
    assert convo.turns == []


def test_conversations_are_listed_for_their_owner_newest_first():
    store = InMemoryConversationStore()
    first = store.create(user_id="user-asha", mode="citizen")
    second = store.create(user_id="user-asha", mode="professional")
    listed = store.list_for("user-asha")
    assert [c.id for c in listed] == [second.id, first.id]


def test_one_user_never_sees_anothers_conversations():
    store = InMemoryConversationStore()
    store.create(user_id="user-asha", mode="citizen")
    store.create(user_id="user-ravi", mode="citizen")
    assert [c.user_id for c in store.list_for("user-asha")] == ["user-asha"]


def test_history_follows_the_user_across_devices():
    # "Another device" is just another reader of the same persisted store.
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha", mode="citizen")
    store.append_turn("user-asha", convo.id, Turn(query="theft?", resolved="theft?", answer="...", refused=False))

    on_other_device = store.get("user-asha", convo.id)
    assert [t.query for t in on_other_device.turns] == ["theft?"]


def test_a_user_cannot_load_another_users_conversation_by_id():
    store = InMemoryConversationStore()
    ashas = store.create(user_id="user-asha", mode="citizen")
    assert store.get("user-ravi", ashas.id) is None


def test_appended_turns_accumulate_in_order():
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha", mode="citizen")
    store.append_turn("user-asha", convo.id, Turn("a", "a", "ans-a", False))
    store.append_turn("user-asha", convo.id, Turn("b", "b", "ans-b", False))
    assert [t.query for t in store.get("user-asha", convo.id).turns] == ["a", "b"]


def test_appending_to_a_missing_conversation_is_an_error():
    store = InMemoryConversationStore()
    with pytest.raises(KeyError):
        store.append_turn("user-asha", "no-such-id", Turn("a", "a", "x", False))
