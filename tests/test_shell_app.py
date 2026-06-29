"""The ChatGPT-style shell over HTTP: auth, sidebar, new chat, streaming.

GET /                                    -> the shell page (sidebar + chat box)
GET /api/conversations                   -> the signed-in user's Conversations
POST /api/conversations                  -> start a new chat in a chosen Mode
POST /api/conversations/<id>/messages    -> stream a Grounded Answer back

Every /api route requires a valid session (Authorization: Bearer <token>); an
absent or unknown session is a 401.
"""
import io
import json

from rag.accounts import SessionVerifier
from rag.answer import LegalAssistant
from rag.shell import ChatShell
from rag.shell_app import build_shell_app


def _call(app, method, path, body="", token=None):
    raw = body.encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    chunks = app(environ, start_response)
    return captured["status"], captured["headers"], b"".join(chunks)


def _app(corpus):
    verifier = SessionVerifier()
    shell = ChatShell(LegalAssistant(corpus), verifier=verifier)
    return build_shell_app(shell), verifier


def test_root_serves_the_shell_with_sidebar_and_chat(corpus):
    app, _ = _app(corpus)
    status, headers, body = _call(app, "GET", "/")
    assert status.startswith("200")
    assert "text/html" in headers["Content-Type"]
    assert b"sidebar" in body
    assert b"new-chat" in body
    assert b"<textarea" in body
    # Clerk owns signup/login; the shell loads it.
    assert b"clerk" in body.lower()


def test_listing_conversations_requires_a_session(corpus):
    app, _ = _app(corpus)
    status, _, _ = _call(app, "GET", "/api/conversations")
    assert status.startswith("401")


def test_new_chat_then_it_appears_in_the_sidebar_list(corpus):
    app, verifier = _app(corpus)
    token = verifier.sign_in("user-asha")
    status, _, body = _call(
        app, "POST", "/api/conversations", json.dumps({"mode": "professional"}), token=token
    )
    assert status.startswith("200")
    created = json.loads(body)
    assert created["mode"] == "professional"

    _, _, listing = _call(app, "GET", "/api/conversations", token=token)
    rows = json.loads(listing)["conversations"]
    assert [(r["id"], r["mode"]) for r in rows] == [(created["id"], "professional")]


def test_posting_a_message_streams_a_grounded_answer(corpus):
    app, verifier = _app(corpus)
    token = verifier.sign_in("user-asha")
    _, _, body = _call(
        app, "POST", "/api/conversations", json.dumps({"mode": "citizen"}), token=token
    )
    conv_id = json.loads(body)["id"]
    status, headers, answer = _call(
        app,
        "POST",
        f"/api/conversations/{conv_id}/messages",
        json.dumps({"query": "punishment for theft of movable property"}),
        token=token,
    )
    assert status.startswith("200")
    assert "text/plain" in headers["Content-Type"]
    assert b"Legal basis" in answer


def test_posting_a_message_requires_a_session(corpus):
    app, _ = _app(corpus)
    status, _, _ = _call(
        app, "POST", "/api/conversations/conv-1/messages", json.dumps({"query": "hi"})
    )
    assert status.startswith("401")
