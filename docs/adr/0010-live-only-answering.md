# ADR 0010: Live-only answering - no deterministic stand-ins in the product

- Status: accepted
- Date: 2026-07-03

## Context

Early phases shipped deterministic stand-ins behind the answering seams: a template generator, a hashing embedder, and a glossary-only intent extractor.
They let the product run keyless, but they also let it serve template answers that looked real while never touching a model or a real embedding.
That is worse than failing: a user cannot tell a canned answer from a grounded one, and a misconfigured deployment silently degrades instead of being noticed.

## Decision

The answering path is live-only.
Generation and intent extraction require `LLM_API_KEY`; the server refuses to start without it.
Embeddings are always real (FastEmbed, local and keyless).
No production seam falls back to a deterministic stand-in - a missing or failing dependency surfaces as an explicit error to the user, never as a template answer.
Deterministic implementations survive only as test doubles in `tests/doubles.py`, outside the product packages.

## Consequences

- A misconfiguration is caught at startup, not discovered in production answers.
- A mid-answer model failure reaches the frontend as an explicit error state (with the failure detail), distinct from a Refusal; an ungrounded query reaches it as a Refusal with a machine-readable reason.
- The suite still runs offline, because doubles are injected explicitly per test; nothing in the product can reach them.
- Local development now needs a real LLM key; that is the accepted cost of never serving a fake answer.
