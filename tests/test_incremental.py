"""Incremental ingestion: reload one act without touching the rest.

Point ids are deterministic (uuid5 of the chunk id), so re-running an act is
idempotent; delete-then-upsert means a removed or renamed section cannot linger
as a stale point. The ledger of source hashes powers --changed-only runs.
"""
import dataclasses

from qdrant_client import QdrantClient

from config import load_config
from ingestion.pipeline import default_config, detect_changed_acts, run_ingestion
from ingestion.vectorstore import QdrantVectorStore

from tests.doubles import HashEmbedder


def _fresh_store():
    return QdrantVectorStore(
        embedder=HashEmbedder(dim=64),
        collection="incremental-test",
        client=QdrantClient(":memory:"),
    )


def test_partial_run_loads_only_the_selected_acts():
    result = run_ingestion(
        default_config(), only_acts={"bns"}, embedder=HashEmbedder(dim=64)
    )

    assert result.loaded_acts == {"bns"}
    # Validation, coverage, and the checkpoint inputs stay whole-corpus.
    assert {c.act_id for c in result.chunks} > {"bns"}
    assert result.coverage.overall_coverage > 0
    # Only the selected act's chunks reached the store.
    stored = result.store
    assert stored.count() == len([c for c in result.chunks if c.act_id == "bns"])


def test_reloading_an_act_is_idempotent_and_replaces_stale_points(corpus):
    store = _fresh_store()
    bns = [c for c in corpus if c.act_id == "bns"]
    others = [c for c in corpus if c.act_id != "bns"]
    store.load(others)
    store.load(bns)
    full = store.count()

    # Re-loading the same act twice does not duplicate points...
    store.delete_acts(["bns"])
    store.load(bns)
    store.delete_acts(["bns"])
    store.load(bns)
    assert store.count() == full

    # ...and a section dropped from the source disappears from the store.
    store.delete_acts(["bns"])
    store.load(bns[:-1])
    assert store.count() == full - 1
    # Other acts were never touched.
    assert {c.act_id for c in store.fetch([c.chunk_id for c in others])} == {
        c.act_id for c in others
    }


def test_changed_only_detection_uses_the_source_hash_ledger():
    config = default_config(load_config({}))
    result = run_ingestion(config, embedder=HashEmbedder(dim=64))

    # A ledger written from this run marks every act unchanged...
    assert detect_changed_acts(config, dict(result.source_hashes)) == set()
    # ...an empty ledger marks every act changed...
    assert detect_changed_acts(config, {}) == set(result.source_hashes)
    # ...and corrupting one recorded hash marks exactly that act changed.
    ledger = dict(result.source_hashes)
    ledger["bns"] = "stale-hash"
    assert detect_changed_acts(config, ledger) == {"bns"}
