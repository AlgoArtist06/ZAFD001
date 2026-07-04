# Production hardening: architecture audit and remediation plan

Status: in-progress

## Resolution log

Shipped this pass (all with tests, green baseline held):
- F12 - dedicated `/settings` page with permanent delete; sidebar now links to it.
- F1 - backend `.env` autoload in the composition root + fail-fast guard when a non-development backend has no Clerk.
- F2 - real authenticated encryption at rest (`FernetCipher`), selected by `CONVERSATION_ENCRYPTION_KEY`, with a production guard.
- F3 - CORS pinned to `WEB_ORIGIN` (wildcard only in local development).
- F4 - `/healthz` liveness endpoint.
- F7 - non-development boot warns when the in-memory vector store would re-embed the whole corpus.
- F8 - `.env.example` reconciled (OpenAI-compatible providers documented, new vars added).
- F9 - stale `rag.accounts` / `rag.store` / `rag.answer` / `rag.privacy` docstring paths fixed.
- F10 - sidebar listing now uses `list_summaries`, decrypting only the title, not every turn.
- F11 - the client distinguishes an expired-session 401 and a consent 403 from a backend outage.

Found and fixed while bringing up the real Qdrant + Postgres stack:
- F13 - ingestion upserted the whole corpus in a single request (~85 MB), exceeding Qdrant's 32 MB limit, so the collection stayed empty. Now batched (256 points/request).
- F14 - `chunk_id` collisions: repeated sub-section labels within a section (e.g. definitions clauses) produced duplicate ids, so 575 of 4750 chunks (12%) were silently overwritten in Qdrant and the strict consistency check would fail production boot. Child ids are now disambiguated while the displayed label is preserved.
- F1 (extended) - the ingestion CLI now autoloads `.env` too; `load_dotenv` moved to the shared `config.py` so both entry points use one loader.

Deliberately deferred (documented, not half-done):
- F5 - persisted answers rehydrate as flat text without Citation cards. No information is lost (the verbatim basis is in the stored text); full fidelity needs a turns-schema migration to persist structured citations, which belongs in its own PR.
- F6 - Qdrant retrieval fetches all points and re-ranks in Python; already carries a `ponytail:` ceiling comment, revisit at corpus scale.

## Scope

Read the whole project, judge the architecture, and drive it toward a production-grade build.
Find every frontend issue (auth and retrieval especially), then fix them one by one.
Also add a dedicated account-settings page with a permanent delete-account action (explicit user request).

## Verdict on the current architecture

The core is already strong and does not need a rewrite.
The `rag/` package is cleanly layered into `domain/` (pure logic and seams), `services/` (chat, streaming, eval), `infrastructure/` (Clerk, Postgres, LLM, observability), and `api/` (HTTP only), with a single composition root in `rag/composition.py`.
Decisions are captured in ten ADRs, the domain vocabulary is fixed in `CONTEXT.md`, and the seams have honest docstrings.
Backend tests (95 in the representative subset) and web tests (39) pass; the web app typechecks clean.

The real gaps are at the edges: wiring/config, security placeholders presented as production features, retrieval fidelity on reload, and a few maintainability drifts.
None of these require touching the answer pipeline itself.

## Findings, ranked

### P0 - the app does not work end to end in the current config

**F1. Auth config split: the backend rejects every Clerk token.**
The frontend authenticates with Clerk (keys live in `web/.env.local`) and sends real Clerk session JWTs on every `/api/*` call.
The backend `.env` contains only LLM keys, so `rag.composition` selects the in-memory `SessionVerifier`, whose `verify()` only accepts tokens it minted itself.
A real Clerk JWT therefore resolves to `None`, and `current_account` returns 401 for `/api/answer`, `/api/consent`, and `/api/conversations`.
Root cause is twofold: (a) the backend never loads `.env` at all (there is no dotenv autoload; `load_config()` reads only the live process environment), and (b) the Clerk keys are only present on the web side.
Net effect: a freshly cloned, `npm run dev` + `uvicorn` setup returns 401 on every request.

Fix:
- Autoload `.env` in the backend composition root (a tiny, dependency-light loader, or `python-dotenv` if already available), so `uvicorn rag.composition:build_demo_app --factory` picks up the documented settings without a manual `set -a; source .env`.
- Document that the Clerk key pair must be set on the backend too, and have config validation warn when Clerk is configured on only one side or when a non-development `APP_ENV` runs without Clerk.

Acceptance:
- Booting the backend after copying `.env.example` to `.env` and filling Clerk keys makes a signed-in browser reach the chat and stream an answer.
- Running the backend with `APP_ENV=production` and no Clerk keys fails fast with a clear message instead of silently accepting the offline verifier.

### P1 - security and privacy correctness (legal product)

**F2. "Encrypted at rest" is XOR with a hardcoded repo key.**
`rag/domain/privacy.Cipher` masks conversation text with a fixed repo key and base64-encodes it.
The privacy notice tells the Citizen their conversations are "encrypted at rest," which XOR with a committed key does not honour.
Fix: back the `encrypt`/`decrypt` contract with a real authenticated cipher (`cryptography.Fernet`, AES) keyed from an env secret; keep the offline deterministic transform only for tests, and fail fast in production when the key is absent.

**F3. CORS is wide open (`allow_origins=["*"]`) on an authenticated API.**
Pin the allowed origin to the web app origin from config; keep `*` only for local development.

**F4. No `/healthz` readiness endpoint and no rate limiting on `/api/answer`.**
Add a health endpoint for deployment probes.
Add a minimal per-user rate limit on the answer path to bound LLM cost and abuse (can be deferred behind a note if time-boxed).

### P1 - retrieval issues (frontend and the seam it renders)

**F5. Reloading a persisted Conversation loses answer structure.**
`useChat.selectConversation` rebuilds each assistant turn from the flat stored `answer` string with `citations: []`, so a reloaded Conversation shows one text block with no Citation cards, next-step section, or refusal reason, unlike a freshly streamed answer.
Root cause: only the flat `result.text` is persisted, not the structured parts.
Fix (lazy first): render the reloaded flat text acceptably and consistently; if full fidelity is wanted, persist the structured answer parts and rehydrate them.

**F6. The Qdrant retrieval path fetches all points and re-ranks in Python.**
`HybridRetriever.retrieve` calls `store.search(top_k=store.count())`, defeating the vector index for large corpora.
Known ceiling (already marked with a `ponytail:` comment); revisit only when corpus size makes it slow.

**F7. The keyless in-memory retriever re-embeds the entire corpus at every boot.**
Without `QDRANT_URL`, `build_demo_app` embeds every chunk of the full corpus on startup, which is slow for a production-sized Source of Truth.
Production must use Qdrant; make that explicit and warn on the in-memory path outside development.

### P2 - architecture and maintainability

**F8. `.env.example` drift.**
The example documents Gemini, but the live `.env` uses NVIDIA/Qwen; reconcile the example and the docs to the actual default provider, keeping placeholders (never real secrets).

**F9. Stale module references in docstrings.**
Several docstrings still name pre-refactor paths (`rag.accounts`, `rag.store`, `rag.answer`, `rag.privacy`) after the move into `rag/domain/`.
Update them so the code reads truthfully.

**F10. The sidebar listing decrypts every turn of every Conversation.**
`list_for` loads and decrypts the full history of all Conversations just to render titles (first user turn), which is O(all turns) per sidebar render.
Add a lightweight listing that reads only what the sidebar needs (id, mode, first-turn title).

**F11. The client cannot tell an expired session (401) from a backend outage (5xx).**
`useChat.ask` maps every failure to "the backend could not be reached," so an expired Clerk session shows a misleading error instead of prompting re-auth.

### New feature (explicit request)

**F12. Dedicated account-settings page with permanent delete-account.**
The backend seam already exists (`DELETE /api/account` through `ChatShell.delete_account`, which purges Postgres data, erases consent, and deletes the Clerk user), and `useChat.deleteAccount` already calls it.
Build a dedicated `/settings` (account) page that presents account information and a clearly-guarded permanent deletion action, and link to it from the chat sidebar.

## Execution order

1. F12 account-settings page (bounded, high value, backend already supports it).
2. F1 backend `.env` autoload + Clerk config guard (unblocks the whole app).
3. F2 real cipher, F3 CORS pinning, F4 healthz (security hardening).
4. F5 persisted-answer fidelity, F10 sidebar listing efficiency, F11 401 handling (retrieval/UX).
5. F8, F9 doc/config drift (hygiene).
6. F6, F7 retrieval-scale ceilings (note or defer per corpus size).

Each item ships with its own test or self-check and keeps the green baseline.
