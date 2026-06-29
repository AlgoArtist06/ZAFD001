# Multi-turn memory within a Conversation

Status: done

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

## Comments

Added per-Conversation multi-turn memory.

- New `rag/followup.py`: a deterministic `rewrite_followup(query, recent_context)` that detects a dependent follow-up (back-referential pronouns / elliptical connectors like "it", "that", "also", "else") and folds the bounded recent context into a standalone query. A self-contained turn, or a turn with no context yet, is returned unchanged.
- `Conversation` (in `rag/answer.py`) now keeps a bounded history (last 4 resolved standalone turns) on the instance. `ask()` rewrites a dependent follow-up before handing it to the unchanged `LegalAssistant.answer` pipeline, so every turn still runs the full retrieval -> parent expansion -> grounding -> citation verification -> guardrail path. The returned answer keeps the user's own words. History lives on the instance, so a fresh Conversation (and the stateless `answer`) starts empty - context is never shared across Conversations.
- Extended the gold eval harness (`rag/eval.py`): `GoldCase.turns` carries a multi-turn case, run through one Conversation and judged on its final turn. Added a multi-turn English gold case (`multi-turn-cheating-followup-en`): "Someone cheated me by fraud..." then the dependent "What is the punishment for it?", which must cite BNS 318 - and is refused when run without the Conversation context.
- Tests in `tests/test_followup_memory.py` cover: dependent follow-up answered from memory, the same follow-up refused standalone and refused in a separate Conversation (isolation), self-contained turns unaffected, the user's words preserved, and the multi-turn gold case holding. Full suite: 142 passing.
