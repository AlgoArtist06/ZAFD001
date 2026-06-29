# Postgres-backed Conversation history across reload and devices

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Make Conversation history durable and cross-device by swapping the in-memory store for Postgres behind the existing store seam.
The left sidebar lists the signed-in user's past Conversations loaded from Postgres; selecting one restores its full turn history into the central thread.
A Conversation created on one device is visible after a reload and on another device for the same user.
Storage follows the PRD privacy rules: encryption at rest and no plaintext sensitive content in logs.

The store interface does not change; only its backing implementation moves from in-memory to Postgres, so the shell, accounts, and answer seams above it are untouched.

## Acceptance criteria

- [ ] A Postgres-backed Conversation store implements the existing store seam interface
- [ ] The sidebar lists the authenticated user's persisted Conversations, newest-first
- [ ] Selecting a past Conversation restores its turns into the central thread
- [ ] A Conversation persists across reload and is visible on another device for the same user
- [ ] Reads and writes are scoped per user; one user can never load another user's Conversations
- [ ] Stored content is encrypted at rest and excluded from plaintext logs
- [ ] Postgres connection settings are present as placeholders in `.env.example`; local setup is documented

## Blocked by

- `14-clerk-auth-consent-signup.md`
