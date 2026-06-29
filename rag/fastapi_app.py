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
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ingestion.chunker import chunk_act
from ingestion.models import Chunk
from ingestion.parser import parse_act
from ingestion.schemes import load_scheme_chunks
from rag.answer import LegalAssistant
from rag.api import stream_answer

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class AnswerRequest(BaseModel):
    """One Citizen-mode English question for the tracer-bullet slice."""

    query: str
    mode: str = "citizen"
    language: str = "en"


def create_app(assistant: LegalAssistant) -> FastAPI:
    """Build a FastAPI app bound to a :class:`LegalAssistant`.

    The assistant is injected so tests can bind a tiny offline corpus while the
    demo binds the real Source of Truth.
    """
    app = FastAPI(title="Multilingual Legal Awareness Assistant")

    # The Next.js dev server runs on a different origin, so allow cross-origin
    # calls to the demo endpoint.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST"],
        allow_headers=["*"],
    )

    @app.post("/api/answer")
    def answer(request: AnswerRequest) -> StreamingResponse:
        parts = stream_answer(
            assistant, request.query, request.mode, request.language
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
