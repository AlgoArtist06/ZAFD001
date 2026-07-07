# Legal Saathi - Multilingual Legal Awareness Assistant (ZABR-008)

A ChatGPT-style assistant that answers everyday legal questions about Indian law in English, Hindi, Tamil, and Gujarati.
Every answer is grounded in retrieved bare-act text and cites the exact statute section it comes from; when nothing in the corpus supports the question, it refuses rather than guesses.

The system is legal *information*, never legal *advice*: advice-seeking questions are refused and redirected to real help (a lawyer or the nearest Legal Services Authority, NALSA / DLSA).

## Architecture

```
Next.js (web/)
   |
Convex functions (web/convex/)
   |
Convex DB + Convex vector search  +  OpenAI-compatible LLM & embedding APIs
```

## What is in this repo

| Path | What it is |
|---|---|
| `web/` | The Next.js frontend (see `web/README.md`). |
| `web/convex/` | The Convex backend: schema, chat/consent persistence, the grounded answer pipeline (`llm.ts`), hybrid retrieval (`retrieval.ts`), guardrails, citation verification, and the corpus storage seam. |
| `web/convex/lib/` | The ported legal domain logic: routing, hybrid scoring, expansion, multilingual glossary, IPC-to-BNS recognition, follow-up memory, the answer seam. |
| `web/scripts/` | Operator scripts: `ingestLegalCorpus.ts` (parse -> chunk -> validate -> embed changed chunks -> store) and `runGoldEval.ts` (the live gold evaluation). |
| `web/tests/` | The test suite: domain behavior, gold eval (all four languages), Convex function tests, and the end-to-end pipeline under convex-test. |
| `data/` | The Source of Truth: bare-act text, schemes, glossary, IPC-to-BNS mapping, ground truth, and the gold eval set. |

Design docs live in `CONTEXT.md` (the domain's ubiquitous language) and `docs/adr/`.

## Prerequisites

- Node 20.9+.
- A Convex project (free at https://convex.dev; `npx convex dev` provisions one).
- A Clerk instance (https://dashboard.clerk.com) with a **Convex** JWT template.
- An OpenAI-compatible LLM API key. The default is Google Gemini (free key at https://aistudio.google.com/apikey); any compatible provider works by changing `LLM_BASE_URL` / `LLM_MODEL`. The same provider serves embeddings (`gemini-embedding-001`, 768 dimensions).

Answering is **live-only** by design (ADR 0010): without `LLM_API_KEY` on the Convex deployment every question returns a clear service-configuration error - there is no offline template fallback, ever.

## Run it

### 1. Install and provision

```bash
cd web
npm install
npx convex dev          # logs in, provisions a dev deployment, writes .env.local
```

### 2. Configure the deployment

```bash
npx convex env set CLERK_JWT_ISSUER_DOMAIN https://<instance>.clerk.accounts.dev
npx convex env set CLERK_SECRET_KEY sk_...
npx convex env set LLM_API_KEY ...
npx convex env set LLM_MODEL gemini-2.5-flash
npx convex env set INGEST_KEY  "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
npx convex env set EVAL_KEY    "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Put the Clerk publishable/secret keys and the same `INGEST_KEY`/`EVAL_KEY`/`LLM_API_KEY` in `web/.env.local` (see `.env.example`).

### 3. Ingest the corpus

```bash
npm run ingest:legal              # parse, validate, embed CHANGED chunks, store
npm run ingest:legal -- --dry-run # report what would change, write nothing
```

Embeddings are an ingestion-time artifact: re-running against an unchanged corpus makes zero embedding API calls, and the app can restart forever without ever re-embedding the corpus.
Only a changed source file, changed chunking, or a changed embedding model re-embeds - and only the affected chunks.

### 4. Start the frontend

```bash
npm run dev
```

Open http://localhost:3000. The frontend needs only `NEXT_PUBLIC_CONVEX_URL` and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.

## Test

```bash
cd web
npm run test    # domain suite, gold eval (offline doubles), pipeline e2e
npm run lint
```

The offline suite injects deterministic doubles for the live seams (embedder, generator, intent extractor), mirroring the original Python test equipment - no services or keys needed.

The **live** gold evaluation runs the same 37 hand-verified cases through the real deployed pipeline (live LLM, live embeddings, the stored corpus) and requires the bar of total correctness per language:

```bash
npm run eval:gold                    # all four languages
npm run eval:gold -- --language en
```

Run it after any change to models, prompts, chunking, or retrieval.

## Answering behavior

- Questions in Hindi, Tamil, or Gujarati are auto-detected from their script and answered in that language; English questions are answered in English.
- Ambiguous questions get a clarifying Confirmation Step before an answer.
- Old IPC section numbers are recognised and mapped to the current BNS section, with the former number kept for recognition only.
- High-stakes situations lead with emergency contacts before any legal content.
- Every citation is verified against the retrieved statutory text; an answer whose citations cannot be verified becomes a refusal, never a repaired guess.
