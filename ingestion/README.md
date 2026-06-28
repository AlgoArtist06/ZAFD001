# Ingestion module (Phase 0 - the data gate)

Standalone, re-runnable pipeline that compiles the legal Source of Truth from government sources and loads it into the vector store.
It is the hard gate before any RAG work: the gate stays closed until the Seam 1 tests are green and the human checkpoint is approved.

## Run

```bash
python -m ingestion
```

This parses every in-scope act, chunks adaptively, runs the validation gate, embeds and loads the validated chunks, verifies the IPC-to-BNS mapping, and writes `artifacts/phase0_checkpoint.md` for the single human review.

## Pipeline (Seam 1)

`run_ingestion(config) -> IngestionResult` is the seam everything downstream tests against, independent of the RAG layer:

1. **parse** - `parser.py` turns each bare-act source file in `data/sources/` into structured sections.
2. **chunk** - `chunker.py` does adaptive hierarchical chunking: small sections stay whole, large sections split into per-sub-section children carrying a `parent_section_id`.
3. **validate** - `validation.py` is the gate: incomplete-provenance chunks are flagged and never loaded (no provenance, no answer); orphaned children and section gaps are reported.
4. **embed + load** - `vectorstore.py` provides an offline deterministic embedder and in-memory store. This is a seam: a FastEmbed (`BAAI/bge-base-en-v1.5`) + Qdrant backend can be substituted without changing callers.
5. **side-files** - `mapping.py` (IPC-to-BNS, verified against the official chart, never retrievable), `landmarks.py` (curated judgments with full citations), `schemes.py` (curated scheme fact-cards).
6. **coverage** - `coverage.py` reports coverage against the curated in-scope target and logs the uncovered remainder against each act's full official section count.
7. **checkpoint** - `checkpoint.py` renders the consolidated human-review artifact.

## Ground truth

`data/ground_truth/` holds values the agent did not generate from the corpus (official section counts, the IPC-BNS correspondence chart, and verbatim spot-check values). Content-accuracy tests pin to these so the loop never grades its own homework.

## Production swap-in

The default embedder/store are offline so the Seam 1 suite needs no services. For a real run, implement the `Embedder` protocol with FastEmbed and a Qdrant-backed store, then inject them into the pipeline. The `.env.example` carries the relevant config.
