"""Accounts behind a narrow session seam.

Signup and login themselves belong to Clerk: the product never handles a
password or runs an identity provider of its own. What the rest of the
application needs from auth is small - given the opaque session token a signed-in
browser carries, who is this? :class:`SessionVerifier` is that seam.

Offline it is deterministic and dependency-free, matching the retrieval and
generation seams: :meth:`sign_in` stands in for a completed Clerk signup/login
and mints a session token, and :meth:`verify` resolves a token back to its
:class:`Account`. Production swaps Clerk's hosted session verification behind
``verify`` (validating a real Clerk JWT) - the surface contract, a token in and
an Account or ``None`` out, does not change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Account:
    """An authenticated user, identified across devices by a stable id."""

    user_id: str


class SessionVerifier:
    """Resolves a session token to the :class:`Account` it authenticates."""

    def __init__(self) -> None:
        # token -> user_id. In production this is Clerk's signed session, not a
        # local table; here it is an in-memory registry so the path runs offline.
        self._sessions: Dict[str, str] = {}

    def sign_in(self, user_id: str) -> str:
        """Stand in for a completed Clerk signup/login and mint a session token.

        Signing in again as the same user re-authenticates the same Account, so a
        returning user's persisted history is theirs again.
        """
        token = f"sess_{user_id}"
        self._sessions[token] = user_id
        return token

    def verify(self, token: str) -> Optional[Account]:
        """Resolve a session token to its Account, or ``None`` if unknown."""
        user_id = self._sessions.get(token)
        return Account(user_id) if user_id is not None else None
