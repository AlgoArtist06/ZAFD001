"""Privacy and data control behind narrow seams.

Privacy is first-class here, aligned with India's DPDP Act 2023. This module
holds the pieces the application layer needs to honour that:

- :data:`PRIVACY_NOTICE` - the clear notice shown at signup. It states what is
  stored and why, and discloses that queries are sent to a third-party LLM along
  with the trade-off that disclosure carries.
- :class:`ConsentLedger` - records the explicit consent a Citizen gives to that
  notice at signup, and erases it on a right-to-erasure request.
- :class:`Cipher` - the encryption-at-rest seam. Offline it is a deterministic,
  dependency-free reversible transform whose stored form is plainly not the
  plaintext; production swaps a managed key (AES-GCM via a KMS) behind the same
  ``encrypt`` / ``decrypt`` contract.
- :func:`redact` - keeps sensitive content out of plaintext logs by replacing it
  with a non-reversible placeholder before anything is logged.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Dict, Optional

# Bumping this when the notice text changes lets a fresh consent be required.
NOTICE_VERSION = "2026-06-29"

PRIVACY_NOTICE = (
    "Privacy notice\n"
    "\n"
    "What we store and why: when you are signed in, we store your "
    "Conversations - the questions you ask and the answers you receive - so "
    "your history follows you across devices. We also store the fact and date "
    "of your consent to this notice. Conversation content is encrypted at rest.\n"
    "\n"
    "Third-party LLM: to understand your question and compose an answer, the "
    "text of your query is sent to a third-party large language model (LLM) "
    "provider. The trade-off: this gives you fluent, multilingual answers "
    "without us running our own model, but it means your query text leaves our "
    "systems, and on a free tier the provider may use inputs to train their "
    "model. Do not include information you would not want shared.\n"
    "\n"
    "Your control: you can delete any single Conversation, or delete your "
    "account and all stored data at any time (your right to erasure)."
)


class ConsentRequired(Exception):
    """Raised when an account is used without recorded consent to the notice."""


@dataclass(frozen=True)
class ConsentRecord:
    """The recorded fact that a user consented to a version of the notice."""

    user_id: str
    notice_version: str


class ConsentLedger:
    """Records and revokes explicit consent to the privacy notice."""

    def __init__(self) -> None:
        self._by_user: Dict[str, ConsentRecord] = {}

    def record(self, user_id: str, notice_version: str = NOTICE_VERSION) -> ConsentRecord:
        """Record a user's explicit consent to a version of the notice."""
        record = ConsentRecord(user_id=user_id, notice_version=notice_version)
        self._by_user[user_id] = record
        return record

    def consent_for(self, user_id: str) -> Optional[ConsentRecord]:
        """The user's recorded consent, or ``None`` if they have not consented."""
        return self._by_user.get(user_id)

    def has_consented(self, user_id: str) -> bool:
        return user_id in self._by_user

    def erase(self, user_id: str) -> None:
        """Forget a user's consent record (part of the right to erasure)."""
        self._by_user.pop(user_id, None)


class Cipher:
    """Reversible encryption-at-rest seam; offline it is deterministic XOR."""

    def __init__(self, key: bytes = b"zafd001-conversation-key") -> None:
        # A real deployment injects a managed key; the offline default is a fixed
        # repo key so the path runs without secrets. The contract, not the
        # algorithm, is what callers depend on.
        self._key = key or b"k"

    def encrypt(self, plaintext: str) -> str:
        raw = plaintext.encode("utf-8")
        masked = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(raw))
        return base64.urlsafe_b64encode(masked).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        masked = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        raw = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(masked))
        return raw.decode("utf-8")


def redact(text: str) -> str:
    """A non-reversible placeholder so sensitive content never reaches a log.

    Logs may record that a message of some length was handled, never its words.
    """
    return f"<redacted {len(text)} chars>"
