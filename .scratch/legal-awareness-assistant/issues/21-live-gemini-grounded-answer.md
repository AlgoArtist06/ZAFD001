# Live Gemini-backed Grounded Answer over the existing seam

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Make the assistant produce real generated answers from the configured LLM, replacing the offline template generator as the production path while keeping it as the keyless fallback.
Implement the `Generator` protocol against an OpenAI-API-compatible endpoint, with the v1 default being Google Gemini 2.5 Flash via its OpenAI-compatible endpoint as the PRD specifies, configured through the LLM settings from the config seam (provider, key, base URL, model).
The model sits behind the same `Generator` protocol the deterministic generator already satisfies, so everything above it - retrieval, parent expansion, citation verification, guardrails, the `answer(query, mode, language)` entry - is untouched.

The generated answer stays bound by the hard grounding contract: it may only present claims backed by retrieved chunks with complete provenance, every claim carries its citation, and it says "I do not have a sourced answer for this" rather than guess.
The citation verifier still runs after generation and rejects or strips any cited section that was not actually retrieved, exactly as it does for the deterministic generator - the LLM does not get to bypass it.
Selection is keyless-safe per the config seam: with `LLM_API_KEY` present, answers come from the live model; with no key, the deterministic generator continues to serve, so the suite stays offline.

## Acceptance criteria

- [ ] A `Generator` implementation calls an OpenAI-compatible LLM endpoint configured from the config seam (default Gemini 2.5 Flash)
- [ ] With a key configured, an in-scope question returns a live-generated grounded answer with its cited legal basis through the existing `answer()` entry
- [ ] With no key configured, the deterministic generator serves and the full suite passes offline
- [ ] The citation verifier runs unchanged after generation and rejects/strips any cited section not present in the retrieved chunks
- [ ] An out-of-scope or advice-seeking input still refuses; the live model cannot produce an answer the grounding/guardrail contract would reject
- [ ] No retrieval, expansion, verification, or guardrail logic is reimplemented in the generator; only the generation step changes
- [ ] The grounding and refusal behavior of the live generator is covered by tests at the answer seam

## Blocked by

- `20-config-seam-and-secret-hygiene.md`

## Comments

Added a stdlib OpenAI-compatible Generator selected by the existing config seam,
defaulting to Gemini 2.5 Flash while retaining the keyless deterministic fallback.
Live answer-seam tests cover grounded generation, fabricated-citation refusal, and
advice refusal before any model call. Verified 237 Python and 25 frontend tests,
ESLint, TypeScript, and changed-file mypy; full mypy retains four pre-existing
errors in `rag/expansion.py`.
