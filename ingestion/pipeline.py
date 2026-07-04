"""The Phase 0 ingestion pipeline orchestrator.

Re-runnable end to end: parse -> chunk (adaptive) -> validate gate -> embed and
load -> plus the structured side-files (IPC-BNS mapping, landmark judgments,
scheme fact-cards) and the coverage report. ``run_ingestion`` is the Seam 1
entry point; everything downstream tests against the :class:`IngestionResult`
it returns, independent of the RAG layer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from config import AppConfig, load_config
from ingestion.chunker import chunk_act
from ingestion.coverage import CoverageReport, build_coverage_report
from ingestion.landmarks import LandmarkJudgment, load_landmark_judgments
from ingestion.mapping import IpcBnsMapping, load_ipc_bns_mapping
from ingestion.models import Chunk
from ingestion.parser import parse_act
from ingestion.schemes import load_scheme_chunks
from ingestion.validation import ValidationReport, validate_chunks
from ingestion.vectorstore import VectorStore, create_embedder, create_vector_store

_DATA = Path(__file__).resolve().parent.parent / "data"


@dataclass
class IngestionConfig:
    sources_dir: Path
    schemes_path: Path
    mapping_path: Path
    correspondence_path: Path
    landmarks_path: Path
    manifest_path: Path
    token_threshold: int = 512
    embedding_dim: int = 512


def default_config(app_config: AppConfig | None = None) -> IngestionConfig:
    """The standard ingestion wiring, chunked at the one configured threshold.

    ``CHUNK_TOKEN_THRESHOLD`` drives chunking here and in the RAG runtime's
    corpus load, so the chunk ids in the vector store always match the ids the
    runtime expects (the startup consistency check depends on this).
    """
    settings = app_config or load_config()
    return IngestionConfig(
        sources_dir=_DATA / "sources",
        schemes_path=_DATA / "schemes.json",
        mapping_path=_DATA / "ipc_bns_mapping.json",
        correspondence_path=_DATA / "ground_truth" / "ipc_bns_correspondence.json",
        landmarks_path=_DATA / "landmark_judgments.json",
        manifest_path=_DATA / "ground_truth" / "manifest.json",
        token_threshold=settings.chunk_token_threshold,
    )


@dataclass
class IngestionResult:
    chunks: List[Chunk]
    validation: ValidationReport
    store: VectorStore
    coverage: CoverageReport
    mapping: IpcBnsMapping
    mapping_verified: bool
    landmarks: List[LandmarkJudgment]
    manifest: dict = field(default_factory=dict)
    # act_id -> sha256 of its source file, for the ingest ledger that powers
    # --changed-only runs. Statute acts only; schemes carry their own hashes.
    source_hashes: Dict[str, str] = field(default_factory=dict)
    # The act_ids whose chunks were (re)loaded into the vector store this run.
    loaded_acts: Set[str] = field(default_factory=set)


def detect_changed_acts(config: IngestionConfig, ledger: Dict[str, str]) -> Set[str]:
    """The statute acts whose source file changed since the ledger was written.

    An act missing from the ledger counts as changed, so a fresh checkout or a
    brand-new source is always ingested.
    """
    changed: Set[str] = set()
    for source in sorted(Path(config.sources_dir).glob("*.txt")):
        act = parse_act(source.read_text())
        if ledger.get(act.act_id) != act.source_hash:
            changed.add(act.act_id)
    return changed


def _ingested_by_act(chunks: List[Chunk]) -> Dict[str, Set[str]]:
    by_act: Dict[str, Set[str]] = {}
    for chunk in chunks:
        if chunk.section_number is not None:
            by_act.setdefault(chunk.act_id, set()).add(chunk.section_number)
    return by_act


def run_ingestion(
    config: IngestionConfig,
    app_config: AppConfig | None = None,
    only_acts: Optional[Set[str]] = None,
    embedder=None,
) -> IngestionResult:
    """Run the pipeline; ``only_acts`` restricts the vector load to those acts.

    Parsing, validation, coverage, and the checkpoint always run whole-corpus -
    they are cheap, and the human gate must always see the full picture. Only
    step 4 (embed + load) narrows: each selected act's points are deleted then
    re-upserted, so a removed or renamed section cannot linger as a stale point.
    """
    # 1. Parse + adaptively chunk every in-scope act.
    all_chunks: List[Chunk] = []
    source_hashes: Dict[str, str] = {}
    for source in sorted(Path(config.sources_dir).glob("*.txt")):
        act = parse_act(source.read_text())
        source_hashes[act.act_id] = act.source_hash
        all_chunks.extend(chunk_act(act, token_threshold=config.token_threshold))

    # 2. Curated scheme fact-cards join the corpus as scheme-provenance chunks.
    all_chunks.extend(load_scheme_chunks(config.schemes_path))

    # 3. Validation gate: only complete-provenance, structurally-sound chunks load.
    validation = validate_chunks(all_chunks)

    # 4. Embed + load (no-provenance-no-answer: only validated chunks reach the
    # store). Embeddings are FastEmbed unless the caller injects one - tests
    # pass a double; the product has no offline embedder (ADR 0010).
    settings = app_config or load_config()
    if embedder is None:
        embedder = create_embedder(settings)
    store = create_vector_store(settings, embedder)
    to_load = (
        validation.loadable
        if only_acts is None
        else [c for c in validation.loadable if c.act_id in only_acts]
    )
    loaded_acts = {c.act_id for c in to_load}
    # ponytail: delete-then-upsert is briefly non-atomic per act; move to a
    # collection-alias swap if zero-downtime reloads ever matter.
    store.delete_acts(sorted(loaded_acts))
    store.load(to_load)

    # 5. IPC-BNS mapping, verified against the official correspondence chart.
    mapping = load_ipc_bns_mapping(config.mapping_path)
    chart = json.loads(Path(config.correspondence_path).read_text())["pairs"]
    mapping_verified = mapping.verify(chart)

    # 6. Curated landmark judgments.
    landmarks = load_landmark_judgments(config.landmarks_path)

    # 7. Coverage report against the ground-truth manifest.
    manifest = json.loads(Path(config.manifest_path).read_text())
    coverage = build_coverage_report(
        _ingested_by_act(validation.loadable), manifest["acts"]
    )

    return IngestionResult(
        chunks=validation.loadable,
        validation=validation,
        store=store,
        coverage=coverage,
        mapping=mapping,
        mapping_verified=mapping_verified,
        landmarks=landmarks,
        manifest=manifest,
        source_hashes=source_hashes,
        loaded_acts=loaded_acts,
    )
