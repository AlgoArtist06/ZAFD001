# Postgres setup for Conversation history

The signed-in user's Conversations are stored in Postgres so their history is durable across a reload and visible on another device for the same user.
Storage sits behind the `rag.store` seam: `PostgresConversationStore` implements the same interface as the offline `InMemoryConversationStore`, so nothing above it (the shell, the accounts seam, the answer seam) changes.

## Connection settings

The connection string is read from `DATABASE_URL` in `.env` (copied from `.env.example`):

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/legal_assistant
```

`.env.example` ships a placeholder only; never commit a real credential.

## Local Postgres

Run a local instance with Docker:

```
docker run --name legal-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=legal_assistant -p 5432:5432 -d postgres:16
```

That matches the placeholder `DATABASE_URL` above.

## Wiring the store

Build the store from the connection string; it creates its tables on first use:

```python
from rag.store import PostgresConversationStore

store = PostgresConversationStore.from_dsn(os.environ["DATABASE_URL"])
```

`from_dsn` connects through `psycopg` (psycopg 3), so install it where the backend runs (`pip install psycopg[binary]`).
Inject the store into `ChatShell(assistant, store=store)`; the offline default stays `InMemoryConversationStore` so the test suite runs without a database.

## Privacy guarantees

Following the PRD privacy rules, the store:

- scopes every read and write by `user_id`, so one user can never load, list, or delete another user's Conversations;
- encrypts turn content at rest through the `rag.privacy.Cipher` seam (a managed key / AES-GCM via a KMS in production), so the words a Citizen typed never sit in storage in the clear;
- logs nothing, so no plaintext content reaches a log.

The offline test suite exercises the store's real SQL against SQLite (a dependency-free stand-in running the same statements), so the contract, durability, per-user scoping, and encryption-at-rest are all covered without a live Postgres.
