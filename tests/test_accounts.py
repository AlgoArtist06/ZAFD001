"""Accounts behind a session seam.

Real signup and login are owned by Clerk; the product never sees a password.
What the product needs is the narrow seam Clerk leaves behind: an opaque session
token in, the authenticated Account out (or nothing when the token is unknown).
Production swaps Clerk's hosted session verification behind ``verify``; the
surface contract - a token in, an Account or None out - stays the same.
"""
from rag.accounts import Account, SessionVerifier


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
