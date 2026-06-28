# Ingestion module and Phase 0 data gate

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Build the standalone ingestion module that compiles the legal Source of Truth, run once but kept re-runnable.
It draws only from government sources: the India Code portal for statutes, official sources for scheme information, and the consumer and IP acts.
Scope is the v1 acts: BNS, BNSS, BSA, Consumer Protection Act 2019, the IP acts, and Constitution Part III.
Each act is parsed and chunked with adaptive hierarchical chunking: a section under a token threshold is stored whole, while a larger section is split into per-sub-section child chunks that each carry a parent_section_id.
Every chunk receives a complete Provenance Record and Amendment History.
The IPC-to-BNS Mapping is loaded as a separate structured lookup, never as a retrievable source.
A curated Landmark Judgment file is created with full official citations.
Government schemes are curated structured fact-cards rather than parsed.
The pipeline has a validation gate and loads vectors into the vector store.
Claude authors and runs the Seam 1 tests and iterates the parser until all pass.
Structural-invariant tests self-verify; content-accuracy tests are pinned to bare-act ground truth.
The slice ends at the single human checkpoint, with no mid-build interference.

## Acceptance criteria

- [ ] 80 to 90 percent Coverage of in-scope acts, with the uncovered remainder logged and known
- [ ] 100 percent provenance completeness; any chunk lacking a complete Provenance Record is flagged and never loaded (no-provenance-no-answer enforced at the data layer)
- [ ] Structural integrity: no orphaned child chunks, every parent link resolves, section gaps flagged
- [ ] Adaptive chunking verified: small sections whole, large sections split by sub-section with parent_section_id
- [ ] IPC-to-BNS Mapping loaded and verified against the official correspondence chart
- [ ] Amendment History captured per section
- [ ] Curated Landmark Judgment file created with full official citations
- [ ] Retrieval smoke test: known queries return the correct section as top hit
- [ ] Seam 1 unit tests green (structural self-verifying; accuracy pinned to source-of-truth values)
- [ ] Consolidated checkpoint artifact produced (30 to 50 sample sections side-by-side with official source links, plus coverage and test report) and human-approved before any downstream work begins

## Blocked by

- None - can start immediately
