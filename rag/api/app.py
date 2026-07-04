"""The FastAPI HTTP surface - routes only.

Every part of retrieval, grounding, citation verification, and guardrails stays
in the answer seam; frame assembly lives in :mod:`rag.services.frames`. This
module only adapts the seams to HTTP. Adapter selection (which verifier, which
store, which corpus) happens in :mod:`rag.composition`, the composition root.
"""
from __future__ import annotations

from typing import Any, List, Optional

import anyio.to_thread
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.domain.accounts import Account, SessionVerifier
from rag.domain.answer import LegalAssistant
from rag.domain.followup import rewrite_followup
from rag.domain.privacy import NOTICE_VERSION, PRIVACY_NOTICE, ConsentLedger
from rag.services.chat import ChatShell, Unauthenticated
from rag.services.streaming import stream_answer

# How many recent turns of a Conversation seed follow-up rewriting, mirroring
# Conversation._CONTEXT_TURNS so this stateless path remembers exactly as much
# as the in-process and persisted ones.
_CONTEXT_TURNS = 4


class AnswerRequest(BaseModel):
    """One question in a Conversation, optionally carrying its recent turns.

    The shell keeps a Conversation's history client-side (in-memory for this
    slice) and replays the recent turns as ``context``, oldest first, so a
    dependent follow-up can be resolved against them. A fresh Conversation sends
    no context, so nothing carries across from a previous one.
    """

    query: str
    conversation_id: Optional[str] = None
    language: str = "en"
    context: List[str] = Field(default_factory=list)


def _bearer_token(authorization: str) -> str:
    """The opaque session token from a ``Authorization: Bearer <token>`` header."""
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" else ""


def create_app(
    assistant: LegalAssistant,
    verifier: Optional[SessionVerifier] = None,
    consent: Optional[ConsentLedger] = None,
    store: Optional[Any] = None,
    allowed_origins: Optional[List[str]] = None,
) -> FastAPI:
    """Build a FastAPI app bound to a :class:`LegalAssistant`.

    The assistant is injected so tests can bind a tiny offline corpus while the
    demo binds the real Source of Truth. The session ``verifier`` and the
    ``consent`` ledger are injected too: every answer is served only to a
    signed-in user whose session the accounts seam verifies, and only once that
    user has recorded consent to the privacy notice (their queries are sent to a
    third-party LLM). Offline they are in-memory stand-ins; production swaps
    Clerk's hosted verification and a durable ledger behind the same seams.
    """
    app = FastAPI(title="Multilingual Legal Awareness Assistant")
    verifier = verifier or SessionVerifier()
    consent = consent or ConsentLedger()
    shell = ChatShell(assistant, store=store, verifier=verifier, consent=consent)

    # The web app runs on a different origin, so cross-origin calls are allowed.
    # The composition root pins this to the deployed web origin; only when none
    # is configured (local development) does it fall back to a wildcard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict:
        """Liveness probe for deployment: the process is up and serving."""
        return {"status": "ok"}

    def current_account(authorization: str = Header(default="")) -> Account:
        """Resolve the signed-in Account from the session the browser carries.

        This is the backend's gate: an answer is never served to a request whose
        session the accounts seam cannot verify, so an unauthenticated or unknown
        token is rejected before any work is done.
        """
        account = verifier.verify(_bearer_token(authorization))
        if account is None:
            raise HTTPException(status_code=401, detail="Sign in to use the assistant.")
        return account

    @app.get("/api/privacy-notice")
    def privacy_notice() -> dict:
        """The notice shown at signup, including the third-party-LLM disclosure."""
        return {"version": NOTICE_VERSION, "notice": PRIVACY_NOTICE}

    @app.post("/api/consent")
    def give_consent(account: Account = Depends(current_account)) -> dict:
        """Record, server-side, the signed-in user's consent to the notice."""
        record = consent.record(account.user_id)
        return {"user_id": record.user_id, "notice_version": record.notice_version}

    @app.get("/api/consent")
    def consent_status(account: Account = Depends(current_account)) -> dict:
        """Whether the signed-in user has already consented, and to which notice.

        Lets the consent gate skip itself for a returning user instead of
        asking again on every page load.
        """
        record = consent.consent_for(account.user_id)
        return {
            "consented": record is not None,
            "notice_version": record.notice_version if record else None,
            "current_version": NOTICE_VERSION,
        }

    @app.get("/api/conversations")
    def list_conversations(
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> dict:
        """The signed-in user's Conversations, newest first, for the sidebar."""
        records = shell.conversations(_bearer_token(authorization))
        return {
            "conversations": [
                {"id": r.id, "title": r.title} for r in records
            ]
        }

    @app.post("/api/conversations")
    def create_conversation(
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> dict:
        record = shell.new_chat(_bearer_token(authorization))
        return {"id": record.id, "title": record.title}

    @app.get("/api/conversations/{conversation_id}")
    def conversation_history(
        conversation_id: str,
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> dict:
        try:
            turns = shell.history(_bearer_token(authorization), conversation_id)
        except Unauthenticated:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {"turns": [turn.__dict__ for turn in turns]}

    @app.delete("/api/conversations/{conversation_id}")
    def delete_conversation(
        conversation_id: str,
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> dict:
        """Erase one Conversation through the authenticated deletion seam."""
        try:
            shell.delete_conversation(_bearer_token(authorization), conversation_id)
        except Unauthenticated:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {"ok": True}

    @app.delete("/api/account")
    def delete_account(
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> dict:
        """Erase the authenticated user's account data through the deletion seam."""
        shell.delete_account(_bearer_token(authorization))
        return {"ok": True}

    @app.post("/api/answer")
    async def answer(
        request: AnswerRequest,
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> StreamingResponse:
        # The request is attributed to the verified user; an answer is served
        # only once that user has consented to the third-party-LLM processing.
        # The ledger may be database-backed, so the check runs off the loop.
        consented = await anyio.to_thread.run_sync(
            consent.has_consented, account.user_id
        )
        if not consented:
            raise HTTPException(
                status_code=403, detail="Consent to the privacy notice is required."
            )
        # Resolve a dependent follow-up against the Conversation's recent turns
        # before retrieval, routing through the same memory seam the in-process
        # Conversation uses; a self-contained query is returned unchanged.
        # Resolution (authorisation included) happens before the streaming
        # response starts, so an unknown Conversation still 404s cleanly.
        if request.conversation_id:
            try:
                record, resolved = await anyio.to_thread.run_sync(
                    shell.resolve,
                    _bearer_token(authorization),
                    request.conversation_id,
                    request.query,
                )
            except Unauthenticated:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            frames = stream_answer(
                assistant,
                resolved,
                request.language,
                display_query=request.query,
                persist=lambda result: shell.append_result(
                    record, request.query, resolved, result
                ),
            )
        else:
            resolved = rewrite_followup(request.query, request.context[-_CONTEXT_TURNS:])
            frames = stream_answer(
                assistant,
                resolved,
                request.language,
                display_query=request.query,
            )
        return StreamingResponse(
            frames,
            media_type="application/x-ndjson; charset=utf-8",
        )

    return app
