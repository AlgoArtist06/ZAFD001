# Dual-mode: Citizen and Professional over a single corpus

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Add the Professional Mode answering profile alongside the existing Citizen Mode, both over the single shared corpus.
Professional Mode takes queries as precise legal terms, leans on exact keyword matching with no query expansion, and answers tersely with dense Citations.
Citizen Mode remains the default and keeps its complaint-to-concept normalization and plain step-by-step answers.
Mode is chosen when a Conversation starts and is locked for that Conversation's lifetime; switching requires a new Conversation.
Both modes share one corpus, one provenance layer, one retrieval index, and one citation verifier, so the law never diverges between them.

## Acceptance criteria

- [ ] Professional Mode uses exact keyword retrieval with no expansion and terse citation-dense answers
- [ ] Citizen Mode remains the default for new users
- [ ] Mode is fixed at Conversation start and cannot change mid-Conversation
- [ ] Both modes resolve against the same corpus, provenance layer, retrieval index, and citation verifier
- [ ] Gold eval cases pass for each Mode

## Blocked by

- `02-grounded-answer-english-citizen.md`
