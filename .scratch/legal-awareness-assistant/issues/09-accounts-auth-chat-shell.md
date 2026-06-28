# Accounts, Clerk auth, and ChatGPT-style shell

Status: ready-for-agent

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
