# ADR 0009: Covered Domains expand with the highest-traffic citizen laws

- Status: accepted
- Date: 2026-07-02

## Context

The corpus covered criminal, consumer, IP, fundamental-rights, and scheme domains.
The most common citizen legal questions - online fraud, traffic stops, information requests, and domestic or workplace safety - had no Source of Truth, so every such query was refused.

## Decision

Four Covered Domains join the product, each a new `ActType` value with its own trigger-word set in `rag/domain/routing.py`, plain-language label in `rag/domain/generation.py`, glossary rows in `data/glossary.json`, topic tile in `web/src/lib/topics.ts`, and manifest + gold entries:

| ActType | Source | Covers |
|---|---|---|
| `cyber` | Information Technology Act, 2000 | Hacking, online fraud, identity theft, privacy breach |
| `transport` | Motor Vehicles Act, 1988 | Licences, drunk driving, traffic offences, insurance |
| `governance` | Right to Information Act, 2005 | RTI requests, exemptions, appeals |
| `protection` | DV Act 2005 + POSH Act 2013 | Domestic violence, workplace sexual harassment |

DV and POSH share the `protection` domain: both are protection-of-persons statutes with heavy trigger-word overlap.
Source text is curated by hand from India Code (the import-assist tool of ADR 0008 drafts, a human verifies), kept to a small in-scope slice per act at 100% coverage of that slice, with spot checks pinning verbatim text in the ground-truth manifest.
Tamil and Gujarati glossary terms for the new domains are flagged `unverified` where no official central-act translation was checked, rather than presented as authoritative.

## Consequences

The gold eval runs before and after with no regression: the new trigger words did not re-route any existing query (`test_new_domains.test_full_gold_set_still_passes_after_the_expansion`).
Overall coverage is 91% across thirteen acts; the per-act and overall gates still hold.
Adding the next domain is now a well-worn path: one `ActType` value and the five ripple edits above.
