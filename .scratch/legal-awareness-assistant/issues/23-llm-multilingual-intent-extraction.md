# LLM-backed multilingual intent extraction

Status: ready-for-agent

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

- [ ] The language-detection and query-normalization step calls the live LLM client when configured, via the config seam
- [ ] A code-mixed query (for example Hinglish) is normalized to an English query with legal terms preserved, then answered in the user's language
- [ ] The glossary-grounded translation remains a deterministic hard-constraint lookup; the LLM does not replace it
- [ ] Citations and verbatim statutory text stay in original English; critical legal terms show the English term inline in brackets
- [ ] Normalized queries flow through the unchanged retrieval, grounding, citation-verification, and guardrail pipeline
- [ ] With no LLM key configured, deterministic normalization serves and the full suite passes offline
- [ ] Per-language behavior is covered by tests at the answer seam (Hindi, Tamil, Gujarati)

## Blocked by

- `20-config-seam-and-secret-hygiene.md`
- `21-live-gemini-grounded-answer.md`
