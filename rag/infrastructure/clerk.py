"""Clerk-backed session verification behind the accounts seam.

Production signup and login are Clerk's: the browser carries a short-lived
Clerk session JWT, signed by the instance with RS256. Verifying it is exactly
the seam's job - a token in, an :class:`~rag.domain.accounts.Account` (or
``None``) out - so :class:`ClerkSessionVerifier` is a drop-in for the offline
:class:`~rag.domain.accounts.SessionVerifier`.
"""
from __future__ import annotations

import base64
import binascii
import logging
from typing import Optional

import httpx

from rag.domain.accounts import Account

# Never log token content: a session JWT is a credential. Exception class names
# and user ids are enough to tell an invalid token from an unreachable JWKS.
_LOG = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 10


def _frontend_api_from_publishable_key(publishable_key: str) -> str:
    """Recover the Clerk Frontend API host encoded in a publishable key.

    A Clerk key is ``pk_test_<base64>`` / ``pk_live_<base64>`` where the base64
    payload is the Frontend API host with a trailing ``$`` marker, for example
    ``clean-firefly-45.clerk.accounts.dev``. That host is where the instance
    publishes its JWKS and is the issuer its session tokens carry, so both the
    JWKS URL and the expected issuer derive from it.
    """
    _, _, encoded = publishable_key.partition("_")  # drop the ``pk`` segment
    _, _, encoded = encoded.partition("_")  # drop the ``test``/``live`` segment
    if not encoded:
        raise ValueError("malformed Clerk publishable key")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        host = base64.b64decode(padded).decode("ascii")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("malformed Clerk publishable key") from exc
    return host.rstrip("$")


class ClerkSessionVerifier:
    """Verify Clerk session tokens behind the same seam as ``SessionVerifier``.

    The signature is checked against the instance's published JWKS and the
    issuer is pinned to the instance host, so a forged or foreign token
    resolves to ``None``.
    """

    def __init__(
        self,
        publishable_key: str,
        secret_key: str,
        *,
        leeway_seconds: int = 5,
    ) -> None:
        from jwt import PyJWKClient

        self._secret_key = secret_key
        frontend_api = _frontend_api_from_publishable_key(publishable_key)
        self._issuer = f"https://{frontend_api}"
        self._jwks = PyJWKClient(
            f"{self._issuer}/.well-known/jwks.json", timeout=_HTTP_TIMEOUT_SECONDS
        )
        self._leeway = leeway_seconds

    def verify(self, token: str) -> Optional[Account]:
        """Resolve a Clerk session JWT to its Account, or ``None`` if invalid."""
        if not token:
            return None
        import jwt

        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                leeway=self._leeway,
                # Clerk session tokens carry no ``aud``; identity comes from ``sub``.
                options={"verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            # A malformed, expired, or foreign token is simply not a signed-in
            # user - the gate treats it exactly like no token at all.
            _LOG.info("session token rejected (%s)", type(exc).__name__)
            return None
        except Exception as exc:
            # Not a bad token but a broken path to Clerk (JWKS unreachable, DNS,
            # TLS). Still fail closed, but leave the operator a distinguishable
            # trace instead of silently 401ing every user.
            _LOG.warning(
                "session verification unavailable (%s)",
                type(exc).__name__,
                exc_info=exc,
            )
            return None
        user_id = claims.get("sub")
        return Account(user_id) if user_id else None

    def sign_in(self, user_id: str) -> str:  # pragma: no cover - not used with Clerk
        """Unsupported: Clerk owns signup and login, so the app never mints tokens."""
        raise NotImplementedError(
            "Clerk issues session tokens; the application does not mint them."
        )

    def delete_account(self, user_id: str) -> None:
        """Erase the user from Clerk (right to erasure) via the Backend API.

        Uses httpx, not urllib: Clerk's API sits behind Cloudflare, which
        rejects urllib's default ``Python-urllib`` User-Agent with a 403.
        Erasure is a legal obligation, so a transient network failure or 5xx
        gets one retry before the error propagates to the caller.
        """
        url = f"https://api.clerk.com/v1/users/{user_id}"
        headers = {"Authorization": f"Bearer {self._secret_key}"}
        for attempt in (1, 2):
            try:
                response = httpx.delete(
                    url, headers=headers, timeout=_HTTP_TIMEOUT_SECONDS
                )
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise
                _LOG.warning(
                    "clerk delete_account unreachable (%s), retrying once",
                    type(exc).__name__,
                )
                continue
            if response.status_code == 404:  # already gone is success for erasure
                return
            if response.status_code >= 500 and attempt == 1:
                _LOG.warning(
                    "clerk delete_account got %s, retrying once", response.status_code
                )
                continue
            response.raise_for_status()
            return
