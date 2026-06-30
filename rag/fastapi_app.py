"""The FastAPI streaming surface - the demo entry point for the answer seam.

This replaces the ad-hoc stdlib WSGI demo (:mod:`rag.api`'s ``build_app``) with
the framework the PRD's technology stack calls for. It is a wrapper only:

    POST /api/answer  -> streams a Grounded Answer back as NDJSON frames

Every part of retrieval, grounding, citation verification, and guardrails stays
in the existing ``rag`` seam. This module only adapts that seam to HTTP and
streams its structured signals one part at a time - one JSON frame per line, each
tagging its kind (state, high-stakes notice, explanation, citation, next step,
disclaimer) - so the frontend renders a sourced answer in its safe, distinct
form as it arrives rather than parsing a flat blob.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Iterator, List, Optional

from config import load_config
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ingestion.chunker import chunk_act
from ingestion.models import Chunk
from ingestion.parser import parse_act
from ingestion.schemes import load_scheme_chunks
from rag.accounts import Account, SessionVerifier
from rag.answer import GroundedAnswer, LegalAssistant
from rag.followup import rewrite_followup
from rag.privacy import NOTICE_VERSION, PRIVACY_NOTICE, ConsentLedger
from rag.shell import ChatShell, Unauthenticated
from rag.store import PostgresConversationStore

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# How many recent turns of a Conversation seed follow-up rewriting, mirroring
# Conversation._CONTEXT_TURNS so this stateless path remembers exactly as much
# as the in-process and persisted ones.
_CONTEXT_TURNS = 4


def _answer_frames(result: GroundedAnswer) -> Iterator[str]:
    """Stream a Grounded Answer as NDJSON frames, one structured part per line.

    The frontend renders each signal the answer seam decided - the high-stakes
    notice, the plain-language explanation, each verbatim-English Citation, the
    practical next step, and the disclaimer with its legal-aid pointer - in its
    own safe, distinct presentation. The ``meta`` frame leads with the answer's
    state so a refusal, an emergency answer, and a normal answer are each
    rendered distinguishably. This is presentation only: every decision (what is
    refused, what is high-stakes, what is cited) stays in the seam.
    """

    def frame(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False) + "\n"

    state = (
        "refusal"
        if result.refused
        else "emergency"
        if result.high_stakes
        else "normal"
    )
    yield frame({"kind": "meta", "state": state})
    if result.high_stakes_notice:
        yield frame({"kind": "highStakesNotice", "text": result.high_stakes_notice})
    yield frame({"kind": "explanation", "text": result.explanation})
    for citation in result.citations:
        yield frame(
            {
                "kind": "citation",
                "reference": citation.reference,
                "verbatim": citation.verbatim_text,
                "url": citation.source_url,
            }
        )
    if result.former_ipc_note:
        yield frame({"kind": "note", "text": result.former_ipc_note})
    if result.next_step:
        yield frame({"kind": "nextStep", "text": result.next_step})
    if result.disclaimer:
        yield frame({"kind": "disclaimer", "text": result.disclaimer})


class AnswerRequest(BaseModel):
    """One question in a Conversation, optionally carrying its recent turns.

    The shell keeps a Conversation's history client-side (in-memory for this
    slice) and replays the recent turns as ``context``, oldest first, so a
    dependent follow-up can be resolved against them. A fresh Conversation sends
    no context, so nothing carries across from a previous one.
    """

    query: str
    conversation_id: Optional[str] = None
    mode: str = "citizen"
    language: str = "en"
    context: List[str] = Field(default_factory=list)


class ConversationRequest(BaseModel):
    mode: str = "citizen"


def _bearer_token(authorization: str) -> str:
    """The opaque session token from a ``Authorization: Bearer <token>`` header."""
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" else ""


def create_app(
    assistant: LegalAssistant,
    verifier: Optional[SessionVerifier] = None,
    consent: Optional[ConsentLedger] = None,
    store: Optional[Any] = None,
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

    # The Next.js dev server runs on a different origin, so allow cross-origin
    # calls to the demo endpoint.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

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

    @app.post("/api/conversations")
    def create_conversation(
        request: ConversationRequest,
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> dict:
        record = shell.new_chat(_bearer_token(authorization), request.mode)
        return {"id": record.id, "mode": record.mode, "title": record.title}

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
    def answer(
        request: AnswerRequest,
        account: Account = Depends(current_account),
        authorization: str = Header(default=""),
    ) -> StreamingResponse:
        # The request is attributed to the verified user; an answer is served
        # only once that user has consented to the third-party-LLM processing.
        if not consent.has_consented(account.user_id):
            raise HTTPException(
                status_code=403, detail="Consent to the privacy notice is required."
            )
        # Resolve a dependent follow-up against the Conversation's recent turns
        # before retrieval, routing through the same memory seam the in-process
        # Conversation uses; a self-contained query is returned unchanged.
        if request.conversation_id:
            try:
                result = shell.send(
                    _bearer_token(authorization),
                    request.conversation_id,
                    request.query,
                    request.language,
                )
            except Unauthenticated:
                raise HTTPException(status_code=404, detail="Conversation not found.")
        else:
            resolved = rewrite_followup(request.query, request.context[-_CONTEXT_TURNS:])
            result = assistant.answer(resolved, mode=request.mode, language=request.language)
        return StreamingResponse(
            _answer_frames(result),
            media_type="application/x-ndjson; charset=utf-8",
        )

    return app


def load_demo_corpus() -> List[Chunk]:
    """Load the real Source of Truth slice the demo answers from.

    Reads the ingested statute sources and scheme facts from ``data/``; the
    LegalAssistant then keeps only chunks with complete provenance.
    """
    chunks: List[Chunk] = []
    for path in sorted(glob.glob(os.path.join(_DATA_DIR, "sources", "*.txt"))):
        with open(path, "r", encoding="utf-8") as handle:
            chunks.extend(chunk_act(parse_act(handle.read())))
    chunks.extend(load_scheme_chunks(os.path.join(_DATA_DIR, "schemes.json")))
    return chunks


def build_demo_app() -> FastAPI:
    """The demo entry point: a FastAPI app over the real corpus.

    Run with ``uvicorn rag.fastapi_app:build_demo_app --factory``.
    """
    config = load_config()
    store = (
        PostgresConversationStore.from_dsn(config.database_url)
        if config.database_url
        else None
    )
    return create_app(
        LegalAssistant(load_demo_corpus(), app_config=config), store=store
    )
