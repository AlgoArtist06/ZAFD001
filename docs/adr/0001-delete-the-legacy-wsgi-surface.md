# ADR 0001: Delete the legacy WSGI demo surface

- Status: accepted
- Date: 2026-07-02

## Context

Two HTTP surfaces served the same ChatShell: the FastAPI app (`rag/fastapi_app.py`, NDJSON structured frames, used by the Next.js frontend) and a stdlib WSGI demo (`rag/shell_app.py` + `rag/api.py` + `rag/static/shell.html`, plain-text streaming).
Both re-implemented routing, bearer parsing, and answer streaming.
The WSGI surface had no consumer besides its own tests.

## Decision

Delete `rag/shell_app.py`, `rag/api.py`, `rag/static/`, and their tests.
The FastAPI app is the only HTTP surface.
The one behavioral pin worth keeping (a streamed high-stakes answer leads with the emergency notice) moved to a frame-ordering assertion against the FastAPI emitter in `tests/test_guardrails.py`.

## Consequences

One surface to maintain, test, and secure.
Any future demo need is served by the real frontend or `curl -N` against the FastAPI app.
