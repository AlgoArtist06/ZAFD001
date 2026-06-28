# Multi-turn memory within a Conversation

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Allow follow-up questions within a single Conversation to build on prior turns.
Before retrieval, rewrite each follow-up into a standalone query using the bounded recent Conversation context.
Every turn still passes through the full retrieval, parent expansion, grounding, citation verification, and guardrail pipeline.
Context is remembered within a Conversation only and is never carried across Conversations; each new Conversation starts fresh.

## Acceptance criteria

- [ ] A follow-up query is rewritten into a self-contained query using bounded recent context before retrieval
- [ ] Every turn passes the full pipeline including citation verification and guardrails
- [ ] Context is isolated per Conversation and never shared across Conversations
- [ ] A multi-turn gold eval case (question then dependent follow-up) passes

## Blocked by

- `02-grounded-answer-english-citizen.md`
