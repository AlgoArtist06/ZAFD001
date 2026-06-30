"""The FastAPI streaming surface - the demo entry point over the answer() seam.

These tests pin the HTTP contract the Next.js frontend depends on: a single
``POST /api/answer`` that streams a Grounded Answer back chunk by chunk. The
FastAPI layer is a wrapper only - all grounding lives in the ``rag`` seam, so
these tests assert the seam's output reaches the wire, not any new logic here.

Every answer is now served only to a signed-in, consented user: the session a
Clerk-authenticated browser carries is verified through the accounts seam before
anything is answered, and the request is attributed to that user, so one user's
session can never stand in for another's.
"""
import json

from fastapi.testclient import TestClient

from rag.accounts import SessionVerifier
from rag.answer import LegalAssistant
from rag.privacy import ConsentLedger
from rag.fastapi_app import create_app


def _app(corpus):
    """An app plus the seams its tests seed: a verifier and a consent ledger."""
    verifier = SessionVerifier()
    consent = ConsentLedger()
    app = create_app(LegalAssistant(corpus), verifier=verifier, consent=consent)
    return TestClient(app), verifier, consent


def _client(corpus, user_id="user-asha"):
    """A client carrying a verified session whose user has recorded consent."""
    client, verifier, consent = _app(corpus)
    token = verifier.sign_in(user_id)
    consent.record(user_id)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_answer_requires_a_verified_session(corpus):
    """No session, no answer: the seam refuses an unauthenticated request."""
    client, _, _ = _app(corpus)
    response = client.post("/api/answer", json={"query": "theft of property"})
    assert response.status_code == 401


def test_unknown_session_is_rejected(corpus):
    """A token that resolves to nobody is not let through."""
    client, _, _ = _app(corpus)
    response = client.post(
        "/api/answer",
        json={"query": "theft of property"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_post_streams_a_grounded_answer_with_verbatim_basis(corpus):
    response = _client(corpus).post("/api/answer", json={"query": "theft of property"})
    assert response.status_code == 200
    frames = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    kinds = [frame["kind"] for frame in frames]
    # The structured signals reach the wire: a state, the plain-language
    # explanation, a distinct Citation carrying the verbatim English text, and the
    # disclaimer with its legal-aid pointer on every answer.
    assert kinds[0] == "meta" and frames[0]["state"] == "normal"
    assert "explanation" in kinds
    citation = next(frame for frame in frames if frame["kind"] == "citation")
    assert "commits theft" in citation["verbatim"]
    assert "Section" in citation["reference"]
    disclaimer = next(frame for frame in frames if frame["kind"] == "disclaimer")
    assert "NALSA / DLSA" in disclaimer["text"]


def test_post_streams_rather_than_buffering_a_blob(corpus):
    """Chunk streaming, not a single blob: the answer is sent chunk-encoded.

    A buffered blob would carry a fixed ``Content-Length``; a streamed response
    omits it and transfers the parts as the seam yields them.
    """
    response = _client(corpus).post(
        "/api/answer", json={"query": "theft of property"}
    )
    assert "content-length" not in response.headers


def test_post_unsupported_query_streams_the_refusal(corpus):
    response = _client(corpus).post(
        "/api/answer", json={"query": "best recipe for biryani"}
    )
    assert response.status_code == 200
    assert "I do not have a sourced answer for that" in response.text


def test_dependent_followup_is_answered_using_supplied_context(corpus):
    """A follow-up routes through the memory seam when prior turns are supplied.

    The frontend keeps a Conversation's turns client-side and replays the recent
    ones as ``context``; the endpoint resolves the dependent follow-up against
    them via the existing rewrite seam, so "it" reaches the cheating section.
    """
    response = _client(corpus).post(
        "/api/answer",
        json={
            "query": "What is the punishment for it?",
            "context": ["Someone cheated me by fraud and took my property dishonestly"],
        },
    )
    assert response.status_code == 200
    assert "I do not have a sourced answer for that" not in response.text
    assert "318" in response.text


def test_followup_without_context_starts_fresh_and_refuses(corpus):
    """A fresh Conversation carries no memory: the same follow-up, with no
    context, has nothing to resolve against and is refused - so starting a new
    chat cannot inherit a previous one's turns."""
    response = _client(corpus).post(
        "/api/answer", json={"query": "What is the punishment for it?"}
    )
    assert "I do not have a sourced answer for that" in response.text


def test_answer_requires_recorded_consent(corpus):
    """A signed-in user who has not consented to the privacy notice cannot be
    answered: queries are sent to a third-party LLM, so consent gates the path."""
    client, verifier, _ = _app(corpus)
    token = verifier.sign_in("user-ravi")  # signed in, but never consented
    response = client.post(
        "/api/answer",
        json={"query": "theft of property"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_consent_is_recorded_server_side_for_the_signed_in_user(corpus):
    """Consent given at signup is recorded server-side, attributed to that user."""
    client, verifier, consent = _app(corpus)
    token = verifier.sign_in("user-asha")
    response = client.post(
        "/api/consent", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert consent.has_consented("user-asha")
    assert response.json()["user_id"] == "user-asha"


def test_consent_requires_a_session(corpus):
    """Consent cannot be recorded for an anonymous request."""
    client, _, _ = _app(corpus)
    assert client.post("/api/consent").status_code == 401


def test_one_users_consent_does_not_admit_another(corpus):
    """Consent is per-user: Asha consenting does not let an un-consented Ravi
    through, so attribution never leaks across users."""
    client, verifier, consent = _app(corpus)
    consent.record("user-asha")
    ravi = verifier.sign_in("user-ravi")
    response = client.post(
        "/api/answer",
        json={"query": "theft of property"},
        headers={"Authorization": f"Bearer {ravi}"},
    )
    assert response.status_code == 403


def test_privacy_notice_discloses_third_party_llm(corpus):
    """The notice the signup UI shows discloses third-party-LLM processing."""
    client, _, _ = _app(corpus)
    response = client.get("/api/privacy-notice")
    assert response.status_code == 200
    body = response.json()
    assert "third-party" in body["notice"].lower()
    assert "large language model" in body["notice"].lower()
    assert body["version"]
