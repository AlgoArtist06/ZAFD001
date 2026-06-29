"""Privacy and data control over HTTP.

The shell page presents the privacy notice and a consent affordance at signup.
The notice is fetchable before a session exists; recording consent, deleting a
single Conversation, and erasing the whole account run behind the session.
"""
import io
import json

from rag.accounts import SessionVerifier
from rag.answer import LegalAssistant
from rag.privacy import ConsentLedger
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
    shell = ChatShell(LegalAssistant(corpus), verifier=verifier, consent=ConsentLedger())
    return build_shell_app(shell), verifier


def test_the_shell_page_presents_the_privacy_notice_and_consent(corpus):
    app, _ = _app(corpus)
    _, _, body = _call(app, "GET", "/")
    lowered = body.lower()
    assert b"privacy" in lowered
    assert b"consent" in lowered


def test_the_privacy_notice_is_fetchable_before_signin(corpus):
    app, _ = _app(corpus)
    status, headers, body = _call(app, "GET", "/api/privacy-notice")
    assert status.startswith("200")
    payload = json.loads(body)
    assert "third-party" in payload["notice"].lower() or "third party" in payload["notice"].lower()


def test_recording_consent_requires_acceptance(corpus):
    app, verifier = _app(corpus)
    token = verifier.sign_in("user-asha")
    refused, _, _ = _call(
        app, "POST", "/api/account/consent", json.dumps({"accept": False}), token=token
    )
    assert refused.startswith("403")
    ok, _, _ = _call(
        app, "POST", "/api/account/consent", json.dumps({"accept": True}), token=token
    )
    assert ok.startswith("200")


def test_a_single_conversation_can_be_deleted_over_http(corpus):
    app, verifier = _app(corpus)
    token = verifier.sign_in("user-asha")
    _, _, body = _call(
        app, "POST", "/api/conversations", json.dumps({"mode": "citizen"}), token=token
    )
    conv_id = json.loads(body)["id"]

    status, _, _ = _call(app, "DELETE", f"/api/conversations/{conv_id}", token=token)
    assert status.startswith("200")

    _, _, listing = _call(app, "GET", "/api/conversations", token=token)
    assert json.loads(listing)["conversations"] == []


def test_deleting_a_conversation_requires_a_session(corpus):
    app, _ = _app(corpus)
    status, _, _ = _call(app, "DELETE", "/api/conversations/conv-1")
    assert status.startswith("401")


def test_the_whole_account_can_be_erased_over_http(corpus):
    app, verifier = _app(corpus)
    token = verifier.sign_in("user-asha")
    _call(app, "POST", "/api/conversations", json.dumps({"mode": "citizen"}), token=token)

    status, _, _ = _call(app, "DELETE", "/api/account", token=token)
    assert status.startswith("200")

    _, _, listing = _call(app, "GET", "/api/conversations", token=token)
    assert json.loads(listing)["conversations"] == []
