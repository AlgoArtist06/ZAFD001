# LLM-backed multilingual intent extraction

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Make the multilingual query-understanding step use the live LLM the PRD calls for, rather than a deterministic stand-in, so colloquial and code-mixed questions are normalized correctly before retrieval.
The PRD specifies LLM-based intent extraction (not a generic machine-translation API): detect the language, extract intent, and normalize the query to English with legal terms preserved, handling code-mixing such as Hinglish and mapping lay complaints to legal concepts.
Wire this normalization step to the live LLM client introduced for generation, configured through the same config seam.

The rest of the multilingual layer is deliberately left deterministic: the glossary-grounded translation stays a keyed lookup whose critical terms are injected into the prompt as hard constraints, the statutory citation and verbatim quoted text remain in original authoritative English, and critical legal terms are rendered in the user's language with the English term inline in brackets.
Every normalized query still flows through the full retrieval, grounding, citation-verification, and guardrail pipeline unchanged.
Selection is keyless-safe per the config seam: with the LLM configured, intent extraction uses it; with no key, the existing deterministic normalization serves so the suite stays offline.

## Acceptance criteria

- [x] The language-detection and query-normalization step calls the live LLM client when configured, via the config seam
- [x] A code-mixed query (for example Hinglish) is normalized to an English query with legal terms preserved, then answered in the user's language
- [x] The glossary-grounded translation remains a deterministic hard-constraint lookup; the LLM does not replace it
- [x] Citations and verbatim statutory text stay in original English; critical legal terms show the English term inline in brackets
- [x] Normalized queries flow through the unchanged retrieval, grounding, citation-verification, and guardrail pipeline
- [x] With no LLM key configured, deterministic normalization serves and the full suite passes offline
- [x] Per-language behavior is covered by tests at the answer seam (Hindi, Tamil, Gujarati)

## Blocked by

- `20-config-seam-and-secret-hygiene.md`
- `21-live-gemini-grounded-answer.md`

## Comments

Added an `IntentExtractor` selection seam to `rag/multilingual.py`, mirroring the existing embedder and generator seams.
`LLMIntentExtractor` detects the language, then calls the live OpenAI-compatible LLM client (same endpoint/model/key as generation) to normalize a non-English or code-mixed query to English, injecting the glossary's critical terms for the detected language as hard `term_constraints` so the deterministic glossary - not the model - fixes legal terminology.
A pure-English query short-circuits without an LLM call, and any field the model omits falls back to the deterministic glossary lookup.
`DeterministicIntentExtractor` wraps the existing `normalize_query` so with no key the suite stays offline.

Selection runs through the config seam: `AppConfig.create_intent_extractor(glossary)` returns the LLM extractor when `LLM_API_KEY` is set, otherwise the deterministic one.
`LegalAssistant` now normalizes through `self._intent.normalize(query)`; the rest of the pipeline (screening/guardrails, IPC->BNS recognition, retrieval, expansion, grounded generation, citation verification, refusal) is unchanged, as is the glossary-grounded output rendering (critical terms in the user's language with the English term inline in brackets; citations and verbatim statutory text stay in original English).

New tests in `tests/test_live_multilingual.py` cover the keyed path at the answer seam for Hindi (code-mixed Hinglish), Tamil, and Gujarati, plus a guard that a pure-English query skips the intent model.
The deterministic offline path stays covered by the existing `test_multilingual*` suites.
