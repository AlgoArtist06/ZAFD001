# ADR 0007: Token streaming via cumulative explanation frames and corrective meta

- Status: accepted
- Date: 2026-07-02

## Context

The NDJSON "streaming" response was chunked delivery of an already-complete answer: the LLM call blocked until done, then frames were written.
True token streaming collides with two product invariants: the frontend contract folds an ``explanation`` frame by replacement, and the post-generation citation-verification gate can turn a fully-generated answer into a Refusal after text has been shown.

## Decision

Streaming reuses the existing frame kinds and their replace semantics instead of adding a delta protocol:

- ``explanation`` frames are cumulative: each carries the full text so far. The frontend's existing replace fold renders progressive streaming with zero changes; answers are a few KB so the resend cost is noise.
- ``meta`` may be emitted again mid-stream as a correction: when verification strips every citation (or the transport fails), the stream ends with ``meta{state: refusal}`` plus a refusal ``explanation``, both replacing prior state client-side.
- ``meta`` gains an additive ``language`` field for script-aware rendering.
- The pipeline split ``LegalAssistant.prepare()`` / ``finalize()`` keeps every decision in the seam; ``answer()`` composes them so all sync callers are untouched.
- The generation seam grows an optional async ``stream()`` (implemented by the httpx adapter, which incrementally extracts the growing ``"explanation"`` field from the partial JSON body); the deterministic generator has no ``stream`` and is served whole from a worker thread - the offline suite never touches asyncio.
- A turn persists only when its answer completes; a client disconnect raises ``GeneratorExit`` through the ``yield`` and skips persistence.

Rejected: a two-phase generation (generate fully, then replay as fake tokens) defeats the latency point; an ``explanationDelta`` append frame would need frontend changes and versioning for no benefit at these payload sizes.

## Consequences

Either side can deploy first: old frontends fold the new stream correctly, and the new frontend renders the old backend.
The refusal gate remains absolute - text a user briefly saw is replaced by the Refusal, which is the honest rendering of "generated but unverifiable".
The urllib adapters became httpx with explicit timeouts and one retry on transient failure.
