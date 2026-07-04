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
4. **embed + load** - `vectorstore.py` uses local FastEmbed (`BAAI/bge-base-en-v1.5`) and Qdrant when `QDRANT_URL` is set. Without it, the deterministic in-memory adapters keep development and tests offline.
5. **side-files** - `mapping.py` (IPC-to-BNS, verified against the official chart, never retrievable), `landmarks.py` (curated judgments with full citations), `schemes.py` (curated scheme fact-cards).
6. **coverage** - `coverage.py` reports coverage against the curated in-scope target and logs the uncovered remainder against each act's full official section count.
7. **checkpoint** - `checkpoint.py` renders the consolidated human-review artifact.

## Ground truth

`data/ground_truth/` holds values the agent did not generate from the corpus (official section counts, the IPC-BNS correspondence chart, and verbatim spot-check values). Content-accuracy tests pin to these so the loop never grades its own homework.

## Local Qdrant

Install the project, start Qdrant, and enable the live adapters:

```bash
python -m pip install -e .
docker run --rm -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
export QDRANT_URL=http://localhost:6333
python -m ingestion
```

`BAAI/bge-base-en-v1.5` is the configured 768-dimensional English BGE model. FastEmbed downloads its ONNX weights on first use and runs them locally on CPU with no API key. Set `QDRANT_API_KEY` only for a protected remote Qdrant instance; `QDRANT_COLLECTION` defaults to `legal_documents`.

With Qdrant running, `QDRANT_URL=http://localhost:6333 python -m pytest tests/test_live_retrieval.py` runs the Phase-0 known-query smoke test. Leave `QDRANT_URL` unset for the fully offline suite.
