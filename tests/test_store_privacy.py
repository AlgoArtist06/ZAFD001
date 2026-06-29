"""Data control and encryption at rest in the Conversation store.

A user controls their own data: they can delete a single Conversation, and on a
right-to-erasure request every Conversation they own is purged. Deletion is
owner-scoped, like every other read, so no user can delete another's data.

Conversation content is encrypted at rest: the store hands the cipher seam the
plaintext to encrypt before persisting it, and decrypts on read, so the words a
Citizen typed never sit in storage in the clear.
"""
from rag.store import InMemoryConversationStore, Turn


def test_a_user_can_delete_one_of_their_conversations():
    store = InMemoryConversationStore()
    keep = store.create(user_id="user-asha", mode="citizen")
    drop = store.create(user_id="user-asha", mode="citizen")

    store.delete("user-asha", drop.id)

    assert store.get("user-asha", drop.id) is None
    assert [c.id for c in store.list_for("user-asha")] == [keep.id]


def test_a_user_cannot_delete_another_users_conversation():
    store = InMemoryConversationStore()
    ashas = store.create(user_id="user-asha", mode="citizen")

    store.delete("user-ravi", ashas.id)

    assert store.get("user-asha", ashas.id) is not None


def test_deleting_all_data_for_a_user_purges_only_their_conversations():
    store = InMemoryConversationStore()
    store.create(user_id="user-asha", mode="citizen")
    store.create(user_id="user-asha", mode="professional")
    ravis = store.create(user_id="user-ravi", mode="citizen")

    store.delete_all_for("user-asha")

    assert store.list_for("user-asha") == []
    assert [c.id for c in store.list_for("user-ravi")] == [ravis.id]


class _SpyCipher:
    """Records what it was asked to encrypt; reversible for round-trips."""

    def __init__(self) -> None:
        self.encrypted: list[str] = []

    def encrypt(self, plaintext: str) -> str:
        self.encrypted.append(plaintext)
        return "enc:" + plaintext[::-1]

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext[len("enc:"):][::-1]


def test_turn_content_is_encrypted_before_it_is_stored_and_decrypted_on_read():
    cipher = _SpyCipher()
    store = InMemoryConversationStore(cipher=cipher)
    convo = store.create(user_id="user-asha", mode="citizen")

    store.append_turn(
        "user-asha",
        convo.id,
        Turn(query="my landlord", resolved="landlord eviction", answer="BNS says...", refused=False),
    )

    # The sensitive fields passed through the cipher before being persisted.
    assert "my landlord" in cipher.encrypted
    assert "BNS says..." in cipher.encrypted

    # ... yet a read hands back the plaintext, unchanged.
    turn = store.get("user-asha", convo.id).turns[0]
    assert turn.query == "my landlord"
    assert turn.answer == "BNS says..."
