"""The FastAPI streaming surface - the demo entry point for the answer seam.

This replaces the ad-hoc stdlib WSGI demo (:mod:`rag.api`'s ``build_app``) with
the framework the PRD's technology stack calls for. It is a wrapper only:

    POST /api/answer  -> streams a Grounded Answer back as text/plain chunks

Every part of retrieval, grounding, citation verification, and guardrails stays
in the existing ``rag`` seam. This module only adapts that seam to HTTP and
streams its structured output one part at a time, so a citizen watches a sourced
answer arrive rather than waiting for a single blob.
"""
from __future__ import annotations

import glob
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ingestion.chunker import chunk_act
from ingestion.models import Chunk
from ingestion.parser import parse_act
from ingestion.schemes import load_scheme_chunks
from rag.accounts import Account, SessionVerifier
from rag.answer import LegalAssistant
from rag.api import stream_answer
from rag.followup import rewrite_followup
from rag.privacy import NOTICE_VERSION, PRIVACY_NOTICE, ConsentLedger

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

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
    mode: str = "citizen"
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

    # The Next.js dev server runs on a different origin, so allow cross-origin
    # calls to the demo endpoint.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
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

    @app.post("/api/answer")
    def answer(
        request: AnswerRequest, account: Account = Depends(current_account)
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
        resolved = rewrite_followup(request.query, request.context[-_CONTEXT_TURNS:])
        parts = stream_answer(
            assistant, resolved, request.mode, request.language
        )
        return StreamingResponse(parts, media_type="text/plain; charset=utf-8")

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
    return create_app(LegalAssistant(load_demo_corpus()))
