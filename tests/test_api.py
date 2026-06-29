"""Thin streaming endpoint + minimal chat UI for the demo path."""
import io
import json

from rag.answer import LegalAssistant
from rag.api import build_app, stream_answer


def _call(app, method, path, body=""):
    raw = body.encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    chunks = app(environ, start_response)
    return captured["status"], captured["headers"], b"".join(chunks)


def test_stream_yields_progressive_chunks(corpus):
    assistant = LegalAssistant(corpus)
    parts = list(stream_answer(assistant, "theft of property", "citizen", "en"))
    assert len(parts) > 1
    joined = "".join(parts)
    assert "Legal basis" in joined
    assert "Practical next step" in joined


def test_get_serves_minimal_chat_ui(corpus):
    status, headers, body = _call(build_app(LegalAssistant(corpus)), "GET", "/")
    assert status.startswith("200")
    assert "text/html" in headers["Content-Type"]
    assert b"<textarea" in body


def test_post_streams_a_grounded_answer(corpus):
    status, headers, body = _call(
        build_app(LegalAssistant(corpus)),
        "POST",
        "/api/answer",
        json.dumps({"query": "theft of property", "mode": "citizen", "language": "en"}),
    )
    assert status.startswith("200")
    assert b"Legal basis" in body


def test_post_unsupported_query_streams_a_refusal(corpus):
    status, _, body = _call(
        build_app(LegalAssistant(corpus)),
        "POST",
        "/api/answer",
        json.dumps({"query": "best recipe for biryani"}),
    )
    assert status.startswith("200")
    assert b"I do not have a sourced answer for that" in body
