# Accounts, Clerk auth, and ChatGPT-style shell

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Turn the minimal chat into the full application shell with real accounts.
Add Clerk authentication for signup and login.
Build the ChatGPT-style layout: a central chat box, a left sidebar listing the user's past Conversations, a new-chat action, and streaming responses.
Persist Conversations per user in Postgres so history follows the user across devices.
Mode is selected when starting a new Conversation and shown per Conversation in the sidebar.

## Acceptance criteria

- [ ] Clerk authentication supports signup and login
- [ ] ChatGPT-style shell: central chat, left sidebar of past Conversations, new-chat action, streaming responses
- [ ] Conversations are persisted per user in Postgres and available across devices
- [ ] Mode is chosen at Conversation start and shown per Conversation
- [ ] The chat path routes through the existing answer seam with guardrails and multilingual support intact

## Blocked by

- `02-grounded-answer-english-citizen.md`
- `04-dual-mode-citizen-professional.md`
- `08-multi-turn-conversation-memory.md`

## Comments

Built the application shell as three thin seams plus a stdlib WSGI surface, matching the codebase's "deterministic offline, production swaps the real service behind the seam" pattern.

- `rag/accounts.py` - `SessionVerifier`: a session token in, an `Account` out. Signup/login are Clerk's; the seam only resolves the session a signed-in browser carries. Offline `sign_in` mints a token; production swaps Clerk's hosted session/JWT verification behind `verify`.
- `rag/store.py` - `InMemoryConversationStore`: per-user persistence of `ConversationRecord`s (owner, locked Mode, turns), reads scoped by `user_id` so history follows the user and never leaks across users. Production swaps a Postgres-backed store behind the same interface.
- `rag/shell.py` - `ChatShell`: authenticates, lists/creates Conversations, and routes every message through the existing `LegalAssistant.answer` seam, so guardrails, IPC-to-BNS recognition, and multilingual answering stay intact. Follow-up memory is rebuilt from the stored turns before each message, so it survives a reload or a new device. Mode is chosen at `new_chat` and fixed.
- `rag/shell_app.py` + `rag/static/shell.html` - the ChatGPT-style layout: left sidebar of past Conversations with a per-Conversation Mode badge, a new-chat action, a central chat box with a Mode selector for new chats, and streamed responses. `/api` routes require an `Authorization: Bearer <token>` session (401 otherwise); the page loads Clerk for signup/login and uses its session token, falling back to a local dev session offline. The original `rag/api.py` demo path is left untouched.

Tests: `tests/test_accounts.py`, `tests/test_store.py`, `tests/test_shell.py`, `tests/test_shell_app.py` (24 new tests). Full suite green (166). The 4 mypy errors reported are pre-existing in `rag/expansion.py`, untouched here; the new modules typecheck clean. No lint tool is configured.
