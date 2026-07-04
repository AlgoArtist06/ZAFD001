# ADR 0006: Startup fails fast when Qdrant diverges from the served corpus

- Status: accepted
- Date: 2026-07-02

## Context

Only the ingestion pipeline writes Qdrant; the RAG runtime reads it and separately parses the same sources in-process for parent expansion.
An empty, stale, or differently-chunked collection therefore degraded answers silently - retrieval missed, expansion found no siblings, and nothing errored.
One real divergence already existed: the pipeline chunked at 80 tokens while the runtime chunked at 512, so the two sides never agreed on chunk ids.

## Decision

Two measures, both in this change:

1. `CHUNK_TOKEN_THRESHOLD` is the single chunking knob: `ingestion.pipeline.default_config` and `rag.composition.load_demo_corpus` both chunk through it, so ingestion-written ids always match runtime-expected ids.
2. `check_corpus_consistency` (in `rag/infrastructure/consistency.py`) runs at startup whenever Qdrant is configured: the collection count must equal the loadable corpus, and a random sample of chunks must round-trip with the same `source_hash`.
On mismatch it raises with the fix in the message ("re-run python -m ingestion") in production, and logs a warning in development (`APP_ENV=development`) so offline work continues.

## Consequences

A misconfigured or stale deployment refuses to start instead of serving degraded answers.
Ingestion and the runtime cannot drift apart on chunking without a test failing (`test_chunk_token_threshold_setting_drives_the_pipeline`).
The check adds one count and one small fetch to startup - negligible.
