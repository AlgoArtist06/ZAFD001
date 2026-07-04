"""Accounts behind a session seam.

Real signup and login are owned by Clerk; the product never sees a password.
What the product needs is the narrow seam Clerk leaves behind: an opaque session
token in, the authenticated Account out (or nothing when the token is unknown).
Production swaps Clerk's hosted session verification behind ``verify``; the
surface contract - a token in, an Account or None out - stays the same.
"""
import base64

import pytest

from rag.domain.accounts import Account, SessionVerifier
from rag.infrastructure.clerk import (
    ClerkSessionVerifier,
    _frontend_api_from_publishable_key,
)


def _publishable_key(frontend_api: str) -> str:
    encoded = base64.b64encode(f"{frontend_api}$".encode()).decode()
    return f"pk_test_{encoded}"


def test_signed_in_user_gets_a_verifiable_session():
    verifier = SessionVerifier()
    token = verifier.sign_in("user-asha")
    assert verifier.verify(token) == Account(user_id="user-asha")


def test_unknown_token_verifies_to_nobody():
    verifier = SessionVerifier()
    assert verifier.verify("not-a-real-token") is None


def test_signing_in_again_returns_the_same_account():
    # Logging back in (a returning user, not a new signup) authenticates the
    # same Account, so their persisted history is theirs again.
    verifier = SessionVerifier()
    first = verifier.sign_in("user-asha")
    second = verifier.sign_in("user-asha")
    assert verifier.verify(first) == verifier.verify(second) == Account("user-asha")


def test_two_users_get_distinct_sessions():
    verifier = SessionVerifier()
    asha = verifier.sign_in("user-asha")
    ravi = verifier.sign_in("user-ravi")
    assert verifier.verify(asha) != verifier.verify(ravi)


# The Clerk-backed verifier is the production swap behind the same seam: it
# verifies real Clerk session JWTs instead of in-memory tokens, but a token in
# and an Account-or-None out stays the contract.


def test_frontend_api_is_recovered_from_a_publishable_key():
    key = _publishable_key("clean-firefly-45.clerk.accounts.dev")
    assert _frontend_api_from_publishable_key(key) == "clean-firefly-45.clerk.accounts.dev"


def test_a_malformed_publishable_key_is_rejected():
    with pytest.raises(ValueError):
        ClerkSessionVerifier("not-a-clerk-key", "sk_test_secret")


def test_clerk_verifier_rejects_an_empty_token():
    verifier = ClerkSessionVerifier(
        _publishable_key("clean-firefly-45.clerk.accounts.dev"), "sk_test_secret"
    )
    assert verifier.verify("") is None


def test_clerk_verifier_rejects_a_token_it_cannot_verify():
    # A token that is not a well-formed, instance-signed JWT is not a signed-in
    # user: the gate treats it exactly like no token at all.
    verifier = ClerkSessionVerifier(
        _publishable_key("clean-firefly-45.clerk.accounts.dev"), "sk_test_secret"
    )
    assert verifier.verify("garbage-not-a-jwt") is None


def test_clerk_verifier_does_not_mint_tokens():
    # Clerk owns signup and login; the application never issues session tokens.
    verifier = ClerkSessionVerifier(
        _publishable_key("clean-firefly-45.clerk.accounts.dev"), "sk_test_secret"
    )
    with pytest.raises(NotImplementedError):
        verifier.sign_in("user-asha")
