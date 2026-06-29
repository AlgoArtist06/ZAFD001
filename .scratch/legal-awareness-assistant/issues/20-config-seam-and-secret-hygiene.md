# Configuration seam and secret hygiene (prefactor)

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Introduce the single configuration seam every later production adapter will read from, so the choice between a real service and its offline deterministic stand-in becomes a config decision rather than hard-wired code.
Today no code reads the environment at all: there is no config loader, the `Generator` is always `DeterministicGenerator`, the `Embedder` is always `DeterministicEmbedder`, and the retriever holds vectors in memory.
The `.env.example` already documents the intended settings (LLM, embeddings, Qdrant, Postgres, Clerk, RAG tuning); this slice makes the code actually consume them.

Build a typed configuration loader that reads the documented environment variables with the defaults from `.env.example`, validates them, and is the one place that decides which implementation each seam uses.
The selection rule is keyless-safe: when a service's required keys are absent (for example no `LLM_API_KEY`, no `QDRANT_URL`), the corresponding seam resolves to its existing offline deterministic stand-in, so the test suite continues to run fully offline with no secrets and no network.
When keys are present, the loader exposes them to the adapters that later slices add.

As part of the same change, fix the standing hygiene issues we identified: replace the real-looking Gemini and Clerk values in the committed `.env.example` with obvious non-secret placeholders (the file is tracked and must never carry live secrets), and reconcile the generation module docstring that says "Claude / claude-opus" with the PRD's stated v1 default of Google Gemini 2.5 Flash via its OpenAI-compatible endpoint, so the code's intent matches the PRD.

## Acceptance criteria

- [ ] A single typed configuration loader reads the variables documented in `.env.example` and applies their defaults
- [ ] Each pluggable seam (generator, embedder, vector store) selects its implementation from config, not from a hard-coded constructor
- [ ] With no service keys set, every seam resolves to its offline deterministic stand-in and the full test suite passes with no network and no secrets
- [ ] Invalid or malformed configuration fails fast with a clear error rather than failing silently later
- [ ] `.env.example` contains only placeholder values; the previously committed real-looking Gemini/Clerk keys are removed
- [ ] The generation module docstring matches the PRD's v1 LLM decision (Gemini 2.5 Flash via OpenAI-compatible endpoint)
- [ ] A short note documents how to create a real `.env` from `.env.example` and that `.env` stays git-ignored

## Blocked by

- None - can start immediately
