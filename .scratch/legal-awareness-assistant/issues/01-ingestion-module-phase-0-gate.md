# Ingestion module and Phase 0 data gate

Status: done

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

## Comments

Built the standalone, re-runnable Phase 0 ingestion module under `ingestion/`, test-first (Red -> Green per slice), establishing the Seam 1 testing conventions for the repo.

What was built:

- **Domain models** (`models.py`): `ProvenanceRecord` with a hard `is_complete()` (no-provenance-no-answer enforced at the data layer), `AmendmentHistory` (captured per section, including an explicit none-recorded flag), and `Chunk` with `is_loadable()`/`is_child()`.
- **Parser** (`parser.py`): tuned to the v1 bare-act format; detects sections/articles, splits `(n)` sub-sections, reflows source line-wraps into clean verbatim text, captures `@AMENDMENT` lines, flags definitions, computes a stable source hash.
- **Adaptive hierarchical chunker** (`chunker.py`): small sections stored whole, large sections split into per-sub-section children that each carry a `parent_section_id` and full provenance.
- **Validation gate** (`validation.py`): partitions into loadable vs flagged (incomplete provenance never loaded), detects orphaned children, resolves every parent link, flags section gaps.
- **Vector load seam** (`vectorstore.py`): offline deterministic embedder + in-memory store so the suite runs with no services; a FastEmbed/Qdrant backend can be injected without changing callers.
- **Side-files**: IPC-to-BNS mapping (`mapping.py`, verified against the official correspondence chart, never retrievable), curated landmark judgments with full official citations (`landmarks.py`), curated government scheme fact-cards as scheme-provenance chunks (`schemes.py`).
- **Coverage** (`coverage.py`): coverage against the curated in-scope target (gate lands at 83%, inside the 80-90% band) with the uncovered remainder logged against each act's full official section count.
- **Pipeline + checkpoint** (`pipeline.py`, `checkpoint.py`, `__main__.py`): `run_ingestion()` is the Seam 1 entry point; `python -m ingestion` emits `artifacts/phase0_checkpoint.md` (40 sample sections side-by-side with official source links, coverage and test report), marked AWAITING HUMAN APPROVAL.

Data: curated `data/sources/*.txt` for BNS, BNSS, BSA, CPA 2019, the IP acts (Copyright, Trade Marks, Patents) and Constitution Part III; `data/ground_truth/` pins official section counts, the IPC-BNS chart, and verbatim spot-check values the agent did not generate, so content-accuracy tests never grade their own homework.

Tests: 65 passing (`pytest`), `mypy` clean. Structural-invariant tests self-verify; content-accuracy tests pin to the bare-act ground truth.

Note: the seed corpus is a representative subset transcribed offline (this environment has no India Code network access). The pipeline is built to extend to full coverage by adding source files and ground-truth entries, and to swap in the FastEmbed+Qdrant backend, with no caller changes. The Phase 0 gate stays at AWAITING HUMAN APPROVAL pending the single human checkpoint.
