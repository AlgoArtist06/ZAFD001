# ADR 0005: Hybrid retrieval scores are a normalized weighted sum, not RRF

- Status: accepted
- Date: 2026-07-02

## Context

`RETRIEVAL_TOP_K` and `HYBRID_ALPHA` existed in config but were never wired: retrieval hardcoded `top_k=8` and ranked by `keyword_overlap_count + cosine`, where the integer overlap count unconditionally dominated the cosine term.
The keyword overlap also serves a second duty: a hit with zero overlap is treated as ungrounded and triggers a Refusal.

## Decision

Score = `(1 - alpha) * (keyword_overlap / query_stem_count) + alpha * cosine`, with `alpha` from `HYBRID_ALPHA` and the result list cut at `RETRIEVAL_TOP_K` (both from `AppConfig`, defaulting to 0.5 and 8 when no config is injected).
Both signals land in [0, 1], so neither can drown the other.
The raw integer `keyword_score` stays on every `RetrievalHit` because the grounding gate needs it.
Reciprocal Rank Fusion was rejected: it discards score magnitudes, needs two full rankings per query, and gives `HYBRID_ALPHA` no natural meaning, while the weighted sum is one line and honors the documented semantics of the setting (0 = pure keyword, 1 = pure vector).

## Consequences

Tuning retrieval is now an environment change, not a code change.
Rank order can differ from the old integer-dominated scheme; the gold eval and retrieval tests pin the behavior that matters and pass unchanged.
