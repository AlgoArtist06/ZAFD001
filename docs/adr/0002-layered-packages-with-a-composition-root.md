# ADR 0002: Layered packages with a composition root

- Status: accepted
- Date: 2026-07-02

## Context

The `rag` package was flat: nineteen modules where pure domain logic, live network adapters, HTTP routing, and adapter selection sat side by side.
Three modules read `load_config()` from the process environment as a hidden fallback, so which adapter ran could be decided in several places.

## Decision

`rag` is layered into four packages plus one composition root:

- `rag/domain/` - pure logic: the answer pipeline, retrieval, generation templates, guardrails, multilingual glossary, privacy pieces, and the deterministic offline default of every seam. No network calls, no credential reads, no `load_config()`.
- `rag/services/` - application services over the domain: `chat.py` (ChatShell), `frames.py` (NDJSON frame assembly), `eval.py`.
- `rag/infrastructure/` - the real adapters: `llm.py` (OpenAI-compatible generator + intent extractor), `clerk.py` (session verification), `persistence.py` (Postgres/SQLite conversation store).
- `rag/api/` - FastAPI routes only.
- `rag/composition.py` - the one place adapters are selected and wired, from credential presence in `AppConfig`.

Dependency rule: `api -> services -> domain`; `infrastructure -> domain protocols`; `composition -> everything`.
The embedding and vector-store seams stay in `ingestion/vectorstore.py` (with their `create_embedder` / `create_vector_store` selection functions) because the ingestion bounded context owns them and must not depend on `rag`.
`config.py` keeps settings and validation only; the `create_*` factory methods moved out of `AppConfig`.
The demo entry point is `uvicorn rag.composition:build_demo_app --factory`.

## Consequences

Which adapter runs is answerable by reading one file.
Domain modules are importable and testable with no services and no environment.
Constructing `LegalAssistant(chunks)` directly still works offline (each seam defaults to its deterministic half), so the test suite keeps constructing it without the composition root.
The trade-off: code that previously relied on `app_config` alone to activate live adapters must now go through `rag.composition.build_assistant`.
