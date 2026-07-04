# ADR 0008: Source acquisition is assisted, never automated past the human gate

- Status: accepted
- Date: 2026-07-02

## Context

Growing the Source of Truth means turning India Code publications (HTML or PDF) into the bare-act text format the parser consumes.
Extraction is heuristic and statutory text is quoted verbatim in answers, so silent extraction damage becomes a wrong citation presented as law.

## Decision

`ingestion/import_assist.py` fetches a statute, detects sections heuristically, composes a draft bare-act file, round-trips it through the real parser, and writes a review report (`artifacts/import_report_<act>.md`) naming the section count vs the official total, suspicious sections, and verbatim samples for side-by-side checking.
The tool writes drafts only under `data/staging/` and refuses a path inside `data/sources/`.
Promoting a draft is a human move: review the report against the official source, move the file, re-run `python -m ingestion`, and approve the regenerated checkpoint.

Companion decision: ingestion is incremental.
`python -m ingestion --act <id>` reloads one act (delete-then-upsert, so renamed or removed sections cannot linger), and `--changed-only` consults the ingest ledger (`artifacts/ingest_ledger.json`, act id to source sha256) to reload only what changed.
Parsing, validation, coverage, and the checkpoint always run whole-corpus so the human gate always sees the full picture.

## Consequences

Adding an act is minutes of tooling plus a mandatory human comparison, rather than either manual transcription or blind automation.
The delete-then-upsert reload is briefly non-atomic per act; a collection-alias swap is the upgrade path if zero-downtime reloads ever matter.
