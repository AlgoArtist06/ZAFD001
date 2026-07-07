# 0011. Migrate the backend to Convex, preserving the answer seam byte for byte

Date: 2026-07-07

## Status

Accepted

## Context

The product ran as Python FastAPI + Postgres (conversations, consent) + Qdrant (vectors) + local FastEmbed embeddings, with a Next.js frontend talking REST/NDJSON.
The legal correctness behavior - grounded RAG, statute citations, refusal on missing evidence, the information-vs-advice boundary, multilingual answering, IPC-to-BNS mapping, high-stakes routing, citation verification, and the gold evaluation - is the product, and had to survive a platform change unchanged.

## Decision

Move all infrastructure to Convex; port the domain logic to TypeScript verbatim rather than re-designing it.

- The domain seams (`rag/domain/*`) became pure TypeScript in `web/convex/lib/` plus `guardrails.ts`/`citations.ts`, with the same constants, markers, copy, scoring formula, and refusal semantics.
- Postgres became Convex tables (`conversations`, `turns`, `consents`); app-layer Fernet encryption was dropped because Convex encrypts at rest platform-side - the privacy notice's promise holds, with the trust boundary moved to the platform.
- Qdrant + boot-time corpus loading became a `documents` table (chunks, provenance, precomputed stems) plus an `embeddings` table carrying the vector index. Splitting the vector out of `documents` keeps keyword scans cheap, which is what preserves the exact hybrid score: candidates are the union of vector-search top 256 and every keyword-overlapping chunk (with true cosine from stored vectors), which provably contains the whole-corpus top-k.
- FastEmbed became an OpenAI-compatible embeddings API (default `gemini-embedding-001`, 768 dims, L2-normalised). Embeddings are an ingestion-time artifact: `scripts/ingestLegalCorpus.ts` skips every chunk whose `contentHash` + `embeddingModel` is unchanged, and the runtime embeds only queries. ADR 0010's live-only rule now also covers embeddings.
- The NDJSON streaming frames became a reactive `streams` document whose fields mirror the frontend's `StructuredAnswer`; the pipeline action updates it as generation progresses (cumulative explanation, replace semantics, late-refusal correction), and turns persist only when complete.
- Clerk JWT verification moved from PyJWT/JWKS in-process to Convex's `auth.config.ts` provider.
- ADR 0010 carries over explicitly: `convex/config.ts#validateLLMConfigured()` gates every generating action; a missing credential surfaces as a service-configuration error, never an ungrounded answer, and only tests may inject deterministic fakes.

## Equivalence evidence (before deleting the Python code)

- The full Python suite ran green one final time (282 passed, 1 live-only skip).
- Chunk inventories over the real `data/` are byte-identical between the Python and TS pipelines (4,750 chunks, same ids, same text hashes), and `content_stems` output matches token for token across the whole corpus.
- The ported suite mirrors the Python test equipment (hash embedder, template generator, glossary intent extractor) and passes, including the gold evaluation at 1.0 accuracy for all four languages and an end-to-end pipeline test through real Convex functions.
- The live gold eval (`npm run eval:gold`) runs the same cases through the deployed pipeline and gates any future model/prompt/chunking change.

## Consequences

- One deployment platform (Convex) replaces four moving parts; no Docker, no boot-time corpus embedding, unlimited restarts with zero embedding calls.
- Retrieval ranking now depends on the embedding API's vectors; the corpus must be re-ingested when the embedding model changes, and the live gold eval is the recalibration gate (HYBRID_ALPHA/top-k remain tunable).
- The `ralph` scripts and `security.md` refer to the retired stack; the security review is marked historical.
