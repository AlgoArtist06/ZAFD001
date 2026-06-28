# Multilingual layer: Hindi

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Build the multilingual answering layer, proving it out with Hindi first.
Detect the user's language and use LLM-based intent extraction to normalize the query to English with legal terms preserved (handling code-mixing such as Hinglish).
Retrieve and reason over the English Source of Truth, then generate the answer in Hindi.
The Bilingual Legal Glossary (Hindi rows) constrains terminology in the output so critical terms cannot flip meaning.
The Citation Anchor stays verbatim in English, and critical legal terms are rendered in Hindi with the English term inline in brackets.
Citizen Mode includes a Confirmation Step for ambiguous queries before answering.

## Acceptance criteria

- [x] Language detection plus intent extraction normalizes a Hindi (or Hinglish) query to English with legal terms preserved
- [x] Retrieval and reasoning run over the English corpus; the answer is generated in Hindi
- [x] The Bilingual Legal Glossary constrains Hindi terminology in the output
- [x] The Citation Anchor remains verbatim English
- [x] Critical terms appear in Hindi with the English term inline in brackets
- [x] Confirmation Step fires for ambiguous Citizen-mode queries
- [x] The gold eval set runs for Hindi

## Blocked by

- `02-grounded-answer-english-citizen.md`
- `03-guardrails-information-not-advice.md`

## Comments

Built the multilingual answering layer over the single English Source of Truth, proven out with Hindi.

- New `rag/multilingual.py` holds the seam: `detect_language` (Devanagari -> `hi`, else `en`, so code-mixed Hinglish still detects as Hindi), the `BilingualGlossary` (loaded from the new `data/glossary.json`), and `confirmation_for`.
- Intent extraction: `BilingualGlossary.to_english` rewrites Hindi terms to English (longest phrases first), drops remaining Devanagari function words, and keeps Latin-script tokens verbatim so legal terms and code-mixed English words survive. The whole downstream pipeline (screening, IPC recognition, routing, retrieval, reasoning) runs over this English query.
- The answer is generated back in the detected language: `DeterministicGenerator` now takes the glossary and renders Hindi Citizen/Professional templates. The glossary constrains the Hindi terminology and renders critical terms as `Hindi (English)`; the Citation Anchor stays verbatim English.
- Confirmation Step: an ambiguous Citizen-mode query (one whose only content word is an ambiguous term, e.g. bare "rights") short-circuits to a clarifying question in the user's language; Professional Mode skips it. Carried on `GroundedAnswer.needs_confirmation` / `confirmation`.
- Refusals are localised per language.
- The gold eval set gains a Hindi subset (cited cases across all Covered Domains, an out-of-scope Refusal, and an ambiguous-query Confirmation) plus an `expect_confirmation` expectation in the harness.

Tests: `tests/test_multilingual.py` (10 cases) plus the Hindi gold subset; full suite green (122 passed). No lint tool configured; mypy on touched files is clean (the 4 remaining errors are pre-existing in the untouched `rag/expansion.py`).
