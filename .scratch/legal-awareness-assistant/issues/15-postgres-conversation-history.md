# Postgres-backed Conversation history across reload and devices

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Make Conversation history durable and cross-device by swapping the in-memory store for Postgres behind the existing store seam.
The left sidebar lists the signed-in user's past Conversations loaded from Postgres; selecting one restores its full turn history into the central thread.
A Conversation created on one device is visible after a reload and on another device for the same user.
Storage follows the PRD privacy rules: encryption at rest and no plaintext sensitive content in logs.

The store interface does not change; only its backing implementation moves from in-memory to Postgres, so the shell, accounts, and answer seams above it are untouched.

## Acceptance criteria

- [x] A Postgres-backed Conversation store implements the existing store seam interface
- [x] The sidebar lists the authenticated user's persisted Conversations, newest-first
- [x] Selecting a past Conversation restores its turns into the central thread
- [x] A Conversation persists across reload and is visible on another device for the same user
- [x] Reads and writes are scoped per user; one user can never load another user's Conversations
- [x] Stored content is encrypted at rest and excluded from plaintext logs
- [x] Postgres connection settings are present as placeholders in `.env.example`; local setup is documented

## Blocked by

- `14-clerk-auth-consent-signup.md`

## Comments

Built test-first (red -> green -> refactor) on the existing `rag.store` seam, so
the contract the shell, accounts, and answer seams sit on top of is unchanged -
only the backing implementation moved.

- `PostgresConversationStore` (in `rag/store.py`) implements the same interface
  as `InMemoryConversationStore`: `create`, `get`, `list_for`, `append_turn`,
  `delete`, `delete_all_for`. Every operation opens a fresh connection from an
  injected `connect` factory, so the store holds no in-process state - the
  database is the single source of truth, which is what makes a Conversation
  durable across a reload and visible on another device for the same user.
- Reads and writes are scoped by `user_id` in the `WHERE` clause, so one user
  can never list, load, or delete another's Conversations. Turn content is
  encrypted through the `rag.privacy.Cipher` seam before it is written and
  decrypted on read (never at rest in the clear), and the store logs nothing, so
  no plaintext content reaches a log.
- One set of SQL serves both backends: a tiny dialect shim swaps the placeholder
  marker and two column types for SQLite, the dependency-free offline driver the
  suite runs the store's real statements against. `from_dsn` wires the
  production Postgres path via `psycopg` (lazy import).
- `DATABASE_URL` is already a placeholder in `.env.example`; local setup
  (Docker Postgres, wiring the store into `ChatShell`, the privacy guarantees) is
  documented in `docs/postgres.md`.

Verified: full `pytest` suite green (215 tests, incl. 12 new in
`tests/test_postgres_store.py` covering the contract, durability across
connections, per-user scoping, encryption at rest, and no-plaintext-in-logs);
`mypy rag/store.py` clean. The shell keeps `InMemoryConversationStore` as its
offline default so the suite runs without a database.
