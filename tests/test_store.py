"""Per-user persistence of Conversations.

A Conversation belongs to the user who started it, carries the Mode chosen at its
start, and accumulates turns. The store keeps these so a user's history follows
them: signing in from another device and listing Conversations returns the same
records. One user never sees another user's Conversations.

The in-memory store here is the deterministic offline stand-in; production swaps
a Postgres-backed store behind the same interface.
"""
import pytest

from rag.domain.conversations import InMemoryConversationStore, Turn


def test_a_new_conversation_records_its_owner():
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha")
    assert convo.user_id == "user-asha"
    assert convo.turns == []


def test_conversations_are_listed_for_their_owner_newest_first():
    store = InMemoryConversationStore()
    first = store.create(user_id="user-asha")
    second = store.create(user_id="user-asha")
    listed = store.list_for("user-asha")
    assert [c.id for c in listed] == [second.id, first.id]


def test_citations_round_trip_with_a_turn():
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha")
    cited = [{"reference": "BNS (2023), Section 303", "verbatim": "Whoever...", "url": "https://x"}]
    store.append_turn(
        "user-asha", convo.id, Turn("theft?", "theft?", "ans", False, citations=cited)
    )
    loaded = store.get("user-asha", convo.id)
    assert loaded.turns[0].citations == cited


def test_summaries_carry_the_first_turn_as_title():
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha")
    store.append_turn(
        "user-asha", convo.id, Turn("first question", "first question", "ans", False)
    )
    store.append_turn("user-asha", convo.id, Turn("second", "second", "ans", False))
    empty = store.create(user_id="user-asha")

    summaries = {s.id: s for s in store.list_summaries("user-asha")}

    assert summaries[convo.id].title == "first question"  # the first turn, decrypted
    assert summaries[empty.id].title == "New chat"  # no turns yet


def test_one_user_never_sees_anothers_conversations():
    store = InMemoryConversationStore()
    store.create(user_id="user-asha")
    store.create(user_id="user-ravi")
    assert [c.user_id for c in store.list_for("user-asha")] == ["user-asha"]


def test_history_follows_the_user_across_devices():
    # "Another device" is just another reader of the same persisted store.
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha")
    store.append_turn("user-asha", convo.id, Turn(query="theft?", resolved="theft?", answer="...", refused=False))

    on_other_device = store.get("user-asha", convo.id)
    assert [t.query for t in on_other_device.turns] == ["theft?"]


def test_a_user_cannot_load_another_users_conversation_by_id():
    store = InMemoryConversationStore()
    ashas = store.create(user_id="user-asha")
    assert store.get("user-ravi", ashas.id) is None


def test_appended_turns_accumulate_in_order():
    store = InMemoryConversationStore()
    convo = store.create(user_id="user-asha")
    store.append_turn("user-asha", convo.id, Turn("a", "a", "ans-a", False))
    store.append_turn("user-asha", convo.id, Turn("b", "b", "ans-b", False))
    assert [t.query for t in store.get("user-asha", convo.id).turns] == ["a", "b"]


def test_appending_to_a_missing_conversation_is_an_error():
    store = InMemoryConversationStore()
    with pytest.raises(KeyError):
        store.append_turn("user-asha", "no-such-id", Turn("a", "a", "x", False))
