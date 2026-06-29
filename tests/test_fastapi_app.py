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
