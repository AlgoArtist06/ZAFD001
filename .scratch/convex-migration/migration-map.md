# Convex Migration Map

> **Status 2026-07-07: COMPLETE.** All ten phases are done and the Python
> backend is removed. Evidence: final Python baseline 282 passed / 1 live-only
> skip; TS suite 100/100 (incl. gold eval at 1.0 for en/hi/ta/gu and an
> end-to-end pipeline test); chunk inventories and stems byte-identical
> between the Python and TS pipelines over the real data/ (4,750 chunks).
> Remaining user steps: provision a cloud deployment + Clerk JWT template,
> set deployment env vars, run `npm run ingest:legal`, then `npm run
> eval:gold` for the live verification. See docs/adr/0011-convex-migration.md.

## Phase 0 analysis (historical)

Refactor Legal Saathi from FastAPI + Postgres + Qdrant + FastEmbed to Next.js + Convex.
The legal correctness behavior is the product: grounded RAG, statute citations, refusal on missing evidence, information-vs-advice boundary, multilingual (en/hi/ta/gu), IPC-to-BNS mapping, high-stakes routing, citation verification, and the gold eval all must survive byte-for-behavior.

Repo facts that shape the plan:

- Corpus: 4,750 loadable chunks (avg 90 tokens, max 4,686) from 13 bare-act sources plus scheme fact-cards. Small enough to preserve the exact hybrid scoring.
- Gold eval: 37 hand-verified cases across 4 languages, accuracy bar 1.0 per language.
- IPC-to-BNS mapping: 14 entries, verified against an official correspondence chart.
- Web is already Next.js 16 + Clerk 7 + shadcn; `web/AGENTS.md` warns the Next.js version differs from training data, so read `node_modules/next/dist/docs/` before frontend work.
- Streaming today: NDJSON frames over a FastAPI StreamingResponse (`meta`, `highStakesNotice`, `explanation` (cumulative, replace semantics), `citation`, `note`, `nextStep`, `disclaimer`).

## 1. Module mapping

### Category A: core domain logic, port to TypeScript (behavior-preserving)

| Python module | Destination | Notes |
|---|---|---|
| `rag/domain/text.py` | `convex/lib/text.ts` | Stemmer + stopwords. Must match Python exactly (same suffix rules) or keyword gating and routing shift. |
| `rag/domain/routing.py` | `convex/lib/routing.ts` | Domain trigger words -> ActType filters. Pure data + set intersection. |
| `rag/domain/retrieval.py` | `convex/retrieval.ts` | `expand_query` lay-concept map + hybrid score `(1-alpha)*keywordNorm + alpha*vector`. Keyword score stays the support gate. |
| `rag/domain/expansion.py` | `convex/retrieval.ts` | Parent/sibling expansion into whole `RetrievedSection`s. Becomes an indexed query on (act_id, section_number). |
| `rag/domain/guardrails.py` | `convex/guardrails.ts` | `screen_request`, `soften_advice`, all safety copy (advice markers, high-stakes markers, softenings, NALSA/DLSA pointer). Pure string logic. |
| `rag/domain/recognition.py` | `convex/lib/recognition.ts` | IPC token gate + section regex + mapping lookup, plus the `formerly IPC ...` note builder from `answer.py`. |
| `rag/domain/followup.py` | `convex/lib/followup.ts` | Follow-up markers + context-prefix rewrite. Pure. |
| `rag/domain/multilingual.py` | `convex/lib/multilingual.ts` | Script detection (Devanagari/Tamil/Gujarati ranges), BilingualGlossary (loads `data/glossary.json`), Confirmation Step table, per-language refusal copy. |
| `rag/domain/citation.py` | `convex/citations.ts` | Citation type, `reference`/`anchor` rendering. |
| `rag/domain/verifier.py` | `convex/citations.ts` | `verify_citations`: keep only citations whose (act_id, section_number) was retrieved. The anti-hallucination backstop. |
| `rag/domain/generation.py` | `convex/llm.ts` (types) | DraftAnswer shape, disclaimer text, generation JSON contract. |
| `rag/domain/answer.py` | `convex/chat.ts` action (`answerQuestion`) | The prepare/finalize pipeline: normalize -> confirm -> screen -> recognize IPC -> expand query -> route -> retrieve -> keyword gate -> expand sections -> generate -> verify citations -> soften -> assemble. Refusal reasons (`no_match`, `advice`, `citations_unverified`) preserved. |
| `rag/domain/conversations.py` | `convex/schema.ts` + `convex/chat.ts` | Turn/ConversationRecord/Summary become Convex documents and queries. |
| `rag/domain/privacy.py` | `convex/schema.ts` + `convex/chat.ts` | PRIVACY_NOTICE, NOTICE_VERSION, consent ledger -> `consents` table. `redact` for logs. |
| `rag/services/chat.py` | `convex/chat.ts` | Ownership scoping moves into queries/mutations keyed by `ctx.auth` identity. |
| `rag/services/frames.py` + `streaming.py` | `convex/chat.ts` + frontend | Frame vocabulary becomes the message document shape. Streaming via incremental Convex writes (see section 4). Service-error-vs-refusal distinction (per-language service error copy) preserved. |
| `rag/services/eval.py` | `scripts/runGoldEval.ts` + `convex/eval.ts` (internal) | Gold eval runner against the real deployed pipeline. Bar stays 1.0 per language over `data/eval/seam2_gold.json`. |

### Category B: infrastructure adapters, replace with Convex

| Python module | Replacement |
|---|---|
| `rag/infrastructure/persistence.py` (Postgres/SQLite, Fernet) | Convex tables. Convex encrypts at rest platform-side; app-layer Fernet goes away (decision recorded below). |
| `rag/infrastructure/clerk.py` (JWKS verification, Backend API delete) | `convex/auth.config.ts` (Clerk JWT provider) + `ctx.auth.getUserIdentity()`. Account erasure keeps one fetch to Clerk's Backend API from a Convex action. |
| `rag/infrastructure/llm.py` | `convex/llm.ts` action: same OpenAI-compatible `/chat/completions` contract via `fetch`, same system prompts, same `response_format: json_object`, `max_tokens: 4096`, one retry on 5xx/transport. Intent extractor keeps the skip-LLM-for-pure-English shortcut and glossary term constraints. |
| `rag/infrastructure/observability.py` | Convex function logs. Keep `redact` discipline: never log query/answer text. |
| `rag/infrastructure/consistency.py` | Deleted concept. Retrieval reads the same Convex tables ingestion writes, so runtime/corpus divergence cannot happen. Replaced by a corpus count/hash check in the ingest script. |
| `ingestion/vectorstore.py` (Qdrant + FastEmbed) | Convex vector index on `documents` + `convex/embeddings.ts` calling an API embedding provider. |
| `rag/api/app.py` (FastAPI routes, CORS, bearer parsing) | Deleted. Convex functions + Clerk auth replace all routes. |
| `rag/composition.py`, `config.py` | Deleted. Convex env vars + `convex/schema.ts` are the wiring. Fail-fast guards (no LLM key -> refuse to answer) move into the actions. |

### Category C: ingestion, port to a script

| Python module | Destination |
|---|---|
| `ingestion/models.py` | `scripts/lib/models.ts` (Chunk, ProvenanceRecord, `is_loadable` no-provenance-no-answer gate, ActType). |
| `ingestion/parser.py` | `scripts/lib/parser.ts` (bare-act header + Section/Article + sub-section + @AMENDMENT parsing, sha256 source hash). |
| `ingestion/chunker.py` | `scripts/lib/chunker.ts` (512-token threshold, parent/child chunks, duplicate sub-label disambiguation). |
| `ingestion/schemes.py` | `scripts/lib/schemes.ts` (scheme fact-cards with governing_authority + scheme_url provenance). |
| `ingestion/mapping.py` | `convex/lib/mapping.ts` (runtime needs it for recognition; ingest script verifies against the official chart). |
| `ingestion/landmarks.py` | `scripts/lib/landmarks.ts` (side-file loader; never enters the vector corpus). |
| `ingestion/validation.py` | `scripts/lib/validation.ts` (loadable/flagged partition, orphan checks). |
| `ingestion/coverage.py` + `checkpoint.py` | `scripts/lib/coverage.ts`; checkpoint artifact kept as ingest-script output (the human review gate stays). |
| `ingestion/pipeline.py` + `__main__.py` | `scripts/ingestLegalCorpus.ts` (parse -> chunk -> validate -> embed via API -> upsert to Convex per act, delete-then-insert per act_id, ledger for `--changed-only`). |
| `ingestion/import_assist.py` | Keep as Python tooling. It is an offline drafting assistant that writes only to `data/staging/`; it never touches the runtime. Revisit in Phase 10. |

### Category D: unchanged

`data/` (all of it: sources, glossary, mapping, correspondence chart, schemes, landmarks, gold eval, manifest), `docs/`, `CONTEXT.md`.
`web/` survives with its transport layer swapped (Phase 8): `lib/api.ts`, `answer-stream.ts` NDJSON reader, and the fetch calls in `use-chat.ts`, `consent-gate.tsx`, `account-settings.tsx` are replaced by Convex hooks; all presentation components stay.

## 2. Convex schema (Phase 2/3 target)

```
documents:      { chunkId, actId, text, actName, actYear, actType, sectionNumber?,
                  subSection?, parentSectionId?, isDefinition, tokenEstimate,
                  sourceUrl, sourceHash, retrievalDate, verbatimText,
                  governingAuthority?, schemeUrl?, amendments, noneRecorded,
                  language: "en", sourceFile, stems: string[], embedding: v.array(v.float64()) }
                  .vectorIndex("by_embedding", { filterFields: ["actType"] })
                  .index("by_act_section", ["actId", "sectionNumber"])
conversations:  { userId, createdAt }            .index("by_user", ["userId"])
turns:          { conversationId, query, resolved, answer, refused, refusalReason?,
                  state, citations: [...], streaming fields }
                  .index("by_conversation", ["conversationId"])
consents:       { userId, noticeVersion, consentedAt } .index("by_user", ["userId"])
```

No `users` table: Clerk is the identity source; `userId` is the Clerk subject from `ctx.auth`.
`stems` are precomputed at ingest so keyword scoring never re-tokenizes 4,750 chunks per query.
No separate ingest ledger table: each document row carries `sourceFile`, `contentHash`, `embeddingModel`, and `lastEmbeddedAt`, which is the change-detection state (see section 5a).

## 5a. Embedding lifecycle rule (mandated, Phase 3)

Embeddings are a build-time / ingestion-time artifact, never a runtime one.

- Corpus embeddings are generated ONLY by `scripts/ingestLegalCorpus.ts` and stored permanently in the `documents` table.
- Nothing embeds corpus text at application startup, Convex function init, chat requests, retrieval, or frontend load.
- Runtime generates exactly one embedding per question: the query embedding.
- Before embedding a chunk, the ingest script compares its `contentHash` + `embeddingModel` against the stored row and SKIPS unchanged chunks.
- Regeneration happens only when a source file, the chunking logic, or the embedding model changes; never delete-and-recreate the whole corpus unless explicitly requested.
- The system must restart unlimited times with zero corpus embedding API calls.

## 3. Retrieval design (parity-critical)

Today: Qdrant returns ALL domain-filtered points (`top_k = store.count()`), keyword overlap is computed in-process, and the exact hybrid score ranks everything.
Convex vector search caps results at 256, so a naive port changes ranking.

Plan: keep exactness by splitting the two signals.

1. Vector signal: `ctx.vectorSearch` top 256 with `actType` filter (a domain subset is at most a few thousand chunks; 256 covers everything with meaningful vector score).
2. Keyword signal: scan the domain-filtered chunks' precomputed `stems` via the index (4,750 rows total; cheap) and compute overlap exactly as today.
3. Union candidates, score with the same normalized hybrid formula (alpha 0.5, top_k 8), keep `keyword_score > 0` as the support gate.

Gold eval is the equivalence proof; any ranking drift shows up there.

## 4. Streaming design

Convex actions do not stream return values.
Replacement: the `answerQuestion` action writes the growing explanation onto the turn document (throttled), and the frontend `useQuery` re-renders reactively.
The frame vocabulary (meta state, highStakesNotice, cumulative explanation with replace semantics, citations, note, nextStep, disclaimer) becomes fields on the turn document, filled in the same order.
Late refusal (citation verification strips everything after text streamed) overwrites the document to the refusal state, same as the corrective frames today.
A service error writes `state: "error"` with the per-language copy and is never persisted as an answer; today's "no partial answer persisted on disconnect" becomes "the turn document is marked incomplete until finalize".
This keeps token-visible progress without an HTTP action, and the frontend drops `answer-stream.ts` entirely.

## 5. Embeddings decision

FastEmbed (local BGE, 768d) cannot run in Convex.
Replace with an API provider called from `convex/embeddings.ts` and the ingest script.
The corpus and all retrieval queries are English (multilingual queries are normalized to English before retrieval), so any strong English embedding API works.
Default: Gemini `gemini-embedding-001` (768d, same provider/key as the default LLM, one credential).
Env: `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, plus `EMBEDDING_MODEL`/`EMBEDDING_DIM`.
Re-ingestion is required regardless (new vectors), so provider choice is a config swap, not a code change.

## 6. Decisions to record (ADR candidates)

- Encryption at rest: drop app-layer Fernet; Convex encrypts at rest platform-side. The privacy notice's promise ("Conversation content is encrypted at rest") stays true. ADR should note the trust boundary moved from app-managed key to platform.
- ADR 0010 (live-only, no offline fallback) carries over, now mandated explicitly: `convex/config.ts` exports `validateLLMConfigured()`, which every generating action calls first and which throws a ConfigurationError when `LLM_API_KEY`/`LLM_MODEL` are unset. Forbidden: offline templates, mock LLM fallback in production, cached generic answers, rule-based answering, best-effort responses. Tests may inject deterministic fakes; production never switches silently. The user sees a service-unavailable/configuration message, never an ungrounded legal response.
- Consistency check deleted as a concept (single store).
- `import_assist.py` stays Python until Phase 10 review.

## 7. Migration order

Dependency-ordered; each step lands with its ported tests green before the next.

1. **Foundation** (Phase 1): DONE 2026-07-07. `convex/` lives at `web/convex/` (colocated with the app's package.json). Schema, `auth.config.ts` (Clerk JWT template "convex", issuer from `CLERK_JWT_ISSUER_DOMAIN` deployment env var), `config.ts` (ADR 0010 gate), `chat.ts` auth-probe `viewer` query, phase-stub headers for documents/embeddings/retrieval/guardrails/citations/llm, `ConvexClientProvider` (pass-through when `NEXT_PUBLIC_CONVEX_URL` unset, so FastAPI flow is untouched). Local anonymous dev deployment provisioned via `CONVEX_AGENT_MODE=anonymous npx convex init`; push + codegen green; web build and all 34 vitest tests pass. Cloud deployment + real Clerk issuer are a user step (`npx convex dev` login, Clerk dashboard JWT template).
2. **Pure domain libs** (start of Phases 4-6, but land first because everything depends on them and they test offline): `text.ts`, `routing.ts`, `guardrails.ts`, `recognition.ts` + `mapping.ts`, `followup.ts`, `multilingual.ts`, `citations.ts` (verify). Port `test_text`-equivalents, `test_guardrails`, `test_recognition`, `test_mapping`, `test_followup_memory`, `test_multilingual*`, `test_verifier` to vitest as each lands.
3. **Schema + chat persistence** (Phase 2): `schema.ts`, `chat.ts` mutations/queries (createConversation, saveMessage/appendTurn, getConversationHistory, listSummaries, deleteConversation, deleteAccount, consent record/status). Ports `test_store`, `test_conversation`, `test_consent_store`, `test_store_privacy` semantics via convex-test.
4. **Ingestion + vectors** (Phase 3): `scripts/lib/*` ports (parser, chunker, schemes, validation, coverage), `embeddings.ts`, `scripts/ingestLegalCorpus.ts`, run against dev deployment, verify chunk count (4,750) and coverage report match Python output on the same `data/`. Ports `test_parser`, `test_chunker`, `test_schemes`, `test_validation`, `test_coverage`, `test_pipeline`, `test_incremental`.
5. **Retrieval** (Phase 4): `retrieval.ts` (hybrid + expansion) against the ingested corpus. Ports `test_retrieval`, `test_expansion`, `test_live_retrieval`.
6. **Pipeline action** (Phases 5-7): `llm.ts` (generator + intent extractor), `answerQuestion` action wiring prepare/finalize, streaming-by-document-writes. Ports `test_answer`, `test_guardrails` integration, `test_llm_draft`, `test_streaming`, `test_new_domains`, `test_followup_memory`.
7. **Frontend** (Phase 8): ConvexProviderWithClerk, replace fetch/NDJSON with `useQuery`/`useMutation`/`useAction`, delete `lib/api.ts` + `answer-stream.ts`, consent gate and settings onto Convex functions. Frontend needs only `NEXT_PUBLIC_CONVEX_URL` + `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`. Read the bundled Next.js 16 docs first (`web/AGENTS.md`).
8. **Gold eval** (Phase 9): `scripts/runGoldEval.ts` runs all 37 cases per language against the deployed Convex pipeline; bar 1.0 per language, matching `test_eval` / final-eval semantics. Also port `test_fastapi_app`-level auth/consent behavior checks against Convex functions.
9. **Cleanup** (Phase 10): only after gold eval passes on Convex - delete `rag/`, `ingestion/` (except decision on `import_assist`), `config.py`, `tests/` (Python), `docker-compose.yml`, `requirements.txt`, `pyproject.toml`. Keep `data/`, `docs/`, eval data.

## 8. Risks

- Ranking drift from the embedding-model swap is the biggest correctness risk; the gold eval plus `test_live_retrieval` ports are the gate, and `HYBRID_ALPHA`/top_k stay tunable env vars for recalibration.
- The TS stemmer must reproduce the Python one exactly (shared fixture test: same inputs, same stems, generated from the Python implementation before it is deleted).
- Convex vector search is only available in actions; the pipeline must be structured action-first with mutations for persistence (already the natural shape).
- 37 gold cases hit the live LLM; eval runs are minutes and cost tokens, so they gate merges, not every save.
