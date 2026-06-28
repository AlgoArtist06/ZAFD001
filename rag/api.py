"""A thin streaming endpoint and a minimal, no-auth chat UI.

Stdlib-only (WSGI) so the demo path runs with no web framework and no services:

    GET  /            -> the minimal chat UI (rag/static/index.html)
    POST /api/answer  -> streams a Grounded Answer back as text/plain chunks

The endpoint is deliberately unauthenticated - it exists to demo the English
Citizen-mode path on its own, not as the production surface.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Iterable, Iterator

from rag.answer import GroundedAnswer, LegalAssistant

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _answer_parts(result: GroundedAnswer) -> Iterator[str]:
    """The structured answer, part by part, for progressive streaming."""
    yield result.explanation + "\n\n"
    if result.legal_basis:
        yield result.legal_basis + "\n\n"
    yield result.next_step + "\n\n"
    if result.disclaimer:
        yield result.disclaimer


def stream_answer(
    assistant: LegalAssistant, query: str, mode: str = "citizen", language: str = "en"
) -> Iterator[str]:
    """Yield a Grounded Answer progressively, one structured part at a time."""
    yield from _answer_parts(assistant.answer(query, mode=mode, language=language))


def _read_index() -> bytes:
    with open(os.path.join(_STATIC_DIR, "index.html"), "rb") as handle:
        return handle.read()


def build_app(assistant: LegalAssistant) -> Callable[[dict, Callable], Iterable[bytes]]:
    """Build a WSGI application bound to a :class:`LegalAssistant`."""

    def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            body = _read_index()
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
            return [body]

        if method == "POST" and path == "/api/answer":
            length = int(environ.get("CONTENT_LENGTH") or 0)
            raw = environ["wsgi.input"].read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
            query = payload.get("query", "")
            mode = payload.get("mode", "citizen")
            language = payload.get("language", "en")
            start_response(
                "200 OK", [("Content-Type", "text/plain; charset=utf-8")]
            )
            return (part.encode("utf-8") for part in stream_answer(
                assistant, query, mode, language
            ))

        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

    return application
