# Guardrails: information, not advice

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Add the layered guardrail stack that keeps the product firmly on the Legal Information side of the line and never on the Legal Advice side.
A scope contract constrains the assistant to general law and procedure.
Input classification routes case-outcome prediction and personalised "what should I do" requests to a Refusal with redirection.
An output-side check softens any answer that slipped into "you should sue / you will win / do X specifically" language.
High-Stakes Routing leads with emergency and legal-aid contacts before the legal explanation when a query touches safety, arrest-in-progress, or active deadlines.
Every answer carries a persistent Disclaimer with a Legal-Aid Pointer.
Out-of-scope queries (outside the Covered Domains) get a graceful Refusal, never a guess.

## Acceptance criteria

- [x] Scope contract enforced so only Legal Information is produced
- [x] Advice-seeking inputs (outcome prediction, personalised action) are refused and redirected
- [x] Output refusal check catches and softens advice-style phrasing
- [x] High-Stakes Routing leads with emergency and legal-aid contacts (for example 112, 181, NALSA/DLSA)
- [x] Persistent Disclaimer with a Legal-Aid Pointer appears on every answer
- [x] Out-of-scope queries return a graceful Refusal with a pointer to where to go
- [x] Gold eval cases covering refusal and guardrail behavior pass

## Blocked by

- `02-grounded-answer-english-citizen.md`

## Comments

Built the layered guardrail stack in a new deep module `rag/guardrails.py` and wired it through the existing answer seam (`rag/answer.py`).

- Input-side scope contract: `screen_request(query)` classifies a request before any retrieval runs. Outcome-prediction and personalised "what should I do" phrasing routes to an advice Refusal with redirection to NALSA/DLSA; High-Stakes queries (arrest-in-progress, safety, active deadlines) are flagged so the answer leads with emergency contacts. High-Stakes takes precedence over the advice refusal so urgent queries are never silently refused.
- Output-side check: `soften_advice(text)` rewrites any "you should sue / you will win / you should / I recommend" phrasing back to neutral informational language; applied to every grounded draft's parts.
- High-Stakes Routing: a single `HIGH_STAKES_NOTICE` (112, 181, NALSA/DLSA) leads the answer ahead of the legal explanation in both `GroundedAnswer.text` and the streaming API. Added `high_stakes` / `high_stakes_notice` fields to `GroundedAnswer`.
- Persistent Disclaimer with a Legal-Aid Pointer continues to ride every path (grounded, out-of-scope Refusal, advice Refusal), now verified by test.
- Gold eval: extended `GoldCase` with `expect_high_stakes`, taught the harness to verify the notice leads, and added three gold cases (advice-outcome Refusal, advice-action Refusal, arrest High-Stakes) to `data/eval/seam2_gold.json`.

Tests: new `tests/test_guardrails.py` (8 cases) plus the existing English gold subset all pass; full suite green. No new mypy errors (the 4 in `rag/expansion.py` pre-date this issue).
