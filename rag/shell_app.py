"""The ChatGPT-style shell as a stdlib WSGI application.

Stdlib-only, matching :mod:`rag.api`: no web framework, no services. It exposes
the application surface the shell page talks to and streams answers back through
the :class:`~rag.shell.ChatShell` - which routes every message through the
existing grounded answer seam, so guardrails and multilingual support are intact.

    GET  /                                  -> the shell page (sidebar + chat)
    GET  /api/conversations                 -> the user's Conversations (sidebar)
    POST /api/conversations                 -> start a new chat in a chosen Mode
    POST /api/conversations/<id>/messages   -> stream a Grounded Answer

Every /api route is authenticated by a Clerk session passed as
``Authorization: Bearer <token>``; an absent or unknown session is a 401.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Iterable, Iterator

from rag.api import _answer_parts
from rag.shell import ChatShell, Unauthenticated

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_MESSAGES_SUFFIX = "/messages"


def _read_shell() -> bytes:
    with open(os.path.join(_STATIC_DIR, "shell.html"), "rb") as handle:
        return handle.read()


def _bearer(environ: dict) -> str:
    """The session token from an ``Authorization: Bearer <token>`` header."""
    header = environ.get("HTTP_AUTHORIZATION", "")
    prefix = "Bearer "
    return header[len(prefix):] if header.startswith(prefix) else ""


def _body(environ: dict) -> dict:
    length = int(environ.get("CONTENT_LENGTH") or 0)
    raw = environ["wsgi.input"].read(length) if length else b"{}"
    return json.loads(raw or b"{}")


def _conversation_row(record) -> dict:
    return {"id": record.id, "mode": record.mode, "title": record.title}


def build_shell_app(shell: ChatShell) -> Callable[[dict, Callable], Iterable[bytes]]:
    """Build a WSGI application serving the shell bound to a :class:`ChatShell`."""

    def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            return _ok(start_response, _read_shell(), "text/html; charset=utf-8")

        try:
            if path == "/api/conversations":
                if method == "GET":
                    rows = [_conversation_row(c) for c in shell.conversations(_bearer(environ))]
                    return _json(start_response, {"conversations": rows})
                if method == "POST":
                    mode = _body(environ).get("mode", "citizen")
                    record = shell.new_chat(_bearer(environ), mode)
                    return _json(start_response, _conversation_row(record))

            if method == "POST" and path.startswith("/api/conversations/") and path.endswith(
                _MESSAGES_SUFFIX
            ):
                conv_id = path[len("/api/conversations/"): -len(_MESSAGES_SUFFIX)]
                payload = _body(environ)
                result = shell.send(
                    _bearer(environ),
                    conv_id,
                    payload.get("query", ""),
                    payload.get("language", "en"),
                )
                start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
                return _encode(_answer_parts(result))
        except Unauthenticated:
            start_response("401 Unauthorized", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Unauthorized"]

        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

    return application


def _encode(parts: Iterator[str]) -> Iterator[bytes]:
    return (part.encode("utf-8") for part in parts)


def _ok(start_response: Callable, body: bytes, content_type: str) -> Iterable[bytes]:
    start_response("200 OK", [("Content-Type", content_type)])
    return [body]


def _json(start_response: Callable, payload: dict) -> Iterable[bytes]:
    body = json.dumps(payload).encode("utf-8")
    return _ok(start_response, body, "application/json; charset=utf-8")
