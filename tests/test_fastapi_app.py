"""The FastAPI streaming surface - the demo entry point over the answer() seam.

These tests pin the HTTP contract the Next.js frontend depends on: a single
``POST /api/answer`` that streams a Grounded Answer back chunk by chunk. The
FastAPI layer is a wrapper only - all grounding lives in the ``rag`` seam, so
these tests assert the seam's output reaches the wire, not any new logic here.
"""
from fastapi.testclient import TestClient

from rag.answer import LegalAssistant
from rag.fastapi_app import create_app


def _client(corpus):
    return TestClient(create_app(LegalAssistant(corpus)))


def test_post_streams_a_grounded_answer_with_verbatim_basis(corpus):
    response = _client(corpus).post("/api/answer", json={"query": "theft of property"})
    assert response.status_code == 200
    body = response.text
    # The streamed explanation and the verbatim cited legal basis both arrive.
    assert "Legal basis" in body
    assert "commits theft" in body


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
