# ADR 0004: Consent records persist in the application database, in the clear

- Status: accepted
- Date: 2026-07-02

## Context

Consent to the privacy notice gates every answer (a 403 without it).
The ledger was in-memory only: a process restart forgot every consent, locking out all previously-consented users and destroying the record of when they consented - a record the DPDP Act expects to exist.

## Decision

`DurableConsentLedger` (in `rag/infrastructure/persistence.py`) persists one row per user - user id, notice version, UTC timestamp - behind the same seam as the in-memory `ConsentLedger`.
It is selected in the composition root whenever `DATABASE_URL` is set, alongside the conversation store.
Rows are stored in the clear, unlike conversation turns: they contain no free text, and `user_id` must stay queryable for the consent gate on every answer.
A companion `GET /api/consent` endpoint reports the signed-in user's consent status so the frontend gate can skip itself for a returning user.

## Consequences

A restart no longer 403s consented users, and the consent date survives as a legal record.
Re-consent replaces the previous row, so a bumped `NOTICE_VERSION` can be re-required by comparing versions.
The offline in-memory ledger remains the default with no database, keeping the suite service-free.
