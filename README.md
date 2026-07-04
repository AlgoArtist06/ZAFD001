# Legal Saathi - Multilingual Legal Awareness Assistant (ZABR-008)

A ChatGPT-style assistant that answers everyday legal questions about Indian law in English, Hindi, Tamil, and Gujarati.
Every answer is grounded in retrieved bare-act text and cites the exact statute section it comes from; when nothing in the corpus supports the question, it refuses rather than guesses.

The system is legal *information*, never legal *advice*: advice-seeking questions are refused and redirected to real help (a lawyer or the nearest Legal Services Authority, NALSA / DLSA).

## What is in this repo

| Path | What it is |
|---|---|
| `ingestion/` | Phase 0 pipeline that parses the bare-act sources in `data/` into provenance-tracked chunks and loads them into the vector store. |
| `rag/domain/` | The answer seam: routing, hybrid retrieval, grounded generation, citation verification, guardrails, and multilingual normalisation. |
| `rag/services/` | Application services over the domain: the chat shell, streaming, and the gold-eval harness. |
| `rag/infrastructure/` | Live adapters: the LLM client, Clerk auth, Postgres persistence, Qdrant consistency. |
| `rag/api/app.py` | The FastAPI HTTP surface (routes only). |
| `rag/composition.py` | The composition root: the one place adapters are selected and wired. |
| `web/` | The Next.js frontend (see `web/README.md`). |
| `data/` | The Source of Truth: bare-act text, schemes, glossary, IPC-to-BNS mapping, and the gold eval set. |

Design docs live in `CONTEXT.md` (the domain's ubiquitous language) and `docs/adr/`.

## Prerequisites

- Python 3.10+ and a virtualenv.
- Node 20.9+ (for the frontend).
- Docker (for local Qdrant + Postgres via `docker-compose.yml`).
- An OpenAI-compatible LLM API key. The default is Google Gemini 2.5 Flash (free key at https://aistudio.google.com/apikey); any compatible provider works by changing `LLM_BASE_URL` and `LLM_MODEL`.

Answering is **live-only** by design (ADR 0010): the backend refuses to start without `LLM_API_KEY`, and there is no offline template fallback.
Embeddings, by contrast, are local FastEmbed (CPU, keyless).

## Configure

```bash
cp .env.example .env
# then fill in LLM_API_KEY at minimum; see the comments in .env.example for the rest
```

`.env` is git-ignored and must never be committed. The backend, ingestion, and (via `web/.env.local`) the frontend all read from it.

Minimum to answer questions locally: `LLM_API_KEY`.
Add `QDRANT_URL` + `QDRANT_API_KEY` to use a persistent vector store instead of re-embedding on every boot.
Add Clerk keys (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`) and `DATABASE_URL` + `CONVERSATION_ENCRYPTION_KEY` for the full signed-in, persisted web experience.

## Run it

### 1. Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . && pip install -r requirements.txt
```

### 2. (Optional) start the datastores

```bash
docker compose up -d          # Qdrant on :6333, Postgres on :5432
```

### 3. Ingest the corpus into the vector store

Only needed when `QDRANT_URL` is set (with the in-memory store the backend embeds the corpus itself on boot).

```bash
python -m ingestion                 # full run
python -m ingestion --changed-only  # re-load only acts whose source changed
```

### 4. Start the backend

```bash
uvicorn rag.composition:build_demo_app --factory --reload --port 8000
```

Health check: `curl http://localhost:8000/healthz` -> `{"status":"ok"}`.
Answering (`POST /api/answer`) requires a signed-in, consented user, so it returns `401` without a session token - that is expected; use the frontend for the full flow.

### 5. Start the frontend

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000. The frontend targets `http://localhost:8000` by default (override with `NEXT_PUBLIC_API_URL`).
Clerk keys must be in `web/.env.local` and exported to the backend so both verify the same instance's session tokens.

## Test

```bash
# Backend (offline: injects deterministic doubles, no services or keys needed)
python -m pytest -q

# Frontend
cd web && npm run test && npm run lint
```

`tests/test_pipeline.py` uses the real FastEmbed embedder (slower, downloads the model on first run); the rest of the suite runs fully offline.
The live seams (`tests/test_live_*.py`) require real credentials and are skipped without them.

## Answering behavior

- Questions in Hindi, Tamil, or Gujarati are auto-detected from their script and answered in that language; English questions are answered in English.
- Ambiguous questions get a clarifying Confirmation Step before an answer.
- Old IPC section numbers are recognised and mapped to the current BNS section, with the former number kept for recognition only.
- High-stakes situations lead with emergency contacts before any legal content.
