# Dual-mode: Citizen and Professional over a single corpus

Status: done

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

## Comments

Added the Professional Mode answering profile alongside the existing Citizen Mode, both over the single shared `LegalAssistant` corpus, retrieval index, provenance layer, and citation verifier - the law never diverges between Modes.

- `Conversation` (in `rag/answer.py`), opened via `assistant.start_conversation(mode=...)`, locks a Mode at start for its lifetime. `mode` is a read-only property (reassignment raises `AttributeError`); `Conversation.ask(query)` answers every turn in that locked Mode. Citizen is the default for new Conversations.
- Mode shapes the query, not the corpus. `rag/retrieval.expand_query(query, mode)` does Citizen-only complaint-to-concept normalization (lay words like "tricked" mapped to the statutory concept "cheating fraud"); Professional Mode returns the query unchanged for exact keyword matching with no expansion. A lay query that Citizen Mode reaches the right section on is refused in Professional Mode rather than guessed.
- `DeterministicGenerator` now branches on Mode: Citizen keeps the plain-language, single-focused-Citation, step-by-step answer; Professional answers tersely ("Applicable provisions:") and densely cites every grounded section. `GroundedAnswer.text` skips an empty next step so the terse Professional rendering stays clean.
- `rag/eval.load_gold_cases` gained a `mode` filter; added Professional gold cases (BNS 303, BNS 318, CPA 35, and an out-of-scope Refusal) to `data/eval/seam2_gold.json`. The English subset (now spanning both Modes) and the new per-Mode subset both pass green.

Tests: `tests/test_conversation.py` (new) plus additions to `tests/test_eval.py`. Full suite green; flake8 and mypy clean on all touched files.
