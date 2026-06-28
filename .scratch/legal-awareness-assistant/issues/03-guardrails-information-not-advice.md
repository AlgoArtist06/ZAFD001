# Guardrails: information, not advice

Status: ready-for-agent

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

- [ ] Scope contract enforced so only Legal Information is produced
- [ ] Advice-seeking inputs (outcome prediction, personalised action) are refused and redirected
- [ ] Output refusal check catches and softens advice-style phrasing
- [ ] High-Stakes Routing leads with emergency and legal-aid contacts (for example 112, 181, NALSA/DLSA)
- [ ] Persistent Disclaimer with a Legal-Aid Pointer appears on every answer
- [ ] Out-of-scope queries return a graceful Refusal with a pointer to where to go
- [ ] Gold eval cases covering refusal and guardrail behavior pass

## Blocked by

- `02-grounded-answer-english-citizen.md`
