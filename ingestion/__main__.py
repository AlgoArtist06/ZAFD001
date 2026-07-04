"""Run the Phase 0 ingestion pipeline and emit the checkpoint artifact.

    python -m ingestion                    # full corpus
    python -m ingestion --act bns --act cpa  # reload only these acts
    python -m ingestion --changed-only     # reload only acts whose source changed

Re-runnable: parse/chunk/validate/embed/load, then write the consolidated
checkpoint artifact for the single human review. Parsing, validation, and
coverage always run whole-corpus; only the vector load narrows. The ingest
ledger (act_id -> source sha256) makes ``--changed-only`` possible.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_dotenv
from ingestion.checkpoint import build_checkpoint
from ingestion.pipeline import default_config, detect_changed_acts, run_ingestion

_ROOT = Path(__file__).resolve().parent.parent
_ARTIFACTS = _ROOT / "artifacts"
_ARTIFACT = _ARTIFACTS / "phase0_checkpoint.md"
_LEDGER = _ARTIFACTS / "ingest_ledger.json"


def _read_ledger() -> dict:
    try:
        return json.loads(_LEDGER.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main(argv: list[str] | None = None) -> None:
    # Pick up .env so QDRANT_URL, EMBEDDING_*, and the rest are read the same way
    # the backend reads them - no manual `set -a; source .env` needed.
    load_dotenv(str(_ROOT / ".env"))
    parser = argparse.ArgumentParser(prog="python -m ingestion")
    parser.add_argument(
        "--act",
        action="append",
        dest="acts",
        metavar="ACT_ID",
        help="reload only this act's chunks (repeatable)",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="reload only acts whose source file changed since the last run",
    )
    args = parser.parse_args(argv)

    config = default_config()
    only_acts = set(args.acts) if args.acts else None
    if args.changed_only:
        changed = detect_changed_acts(config, _read_ledger())
        only_acts = changed if only_acts is None else only_acts & changed
        if not only_acts:
            print("Nothing changed since the last run; vector store untouched.")

    result = run_ingestion(config, only_acts=only_acts)
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    _ARTIFACT.write_text(build_checkpoint(result))

    # The ledger records the hash of every act now consistent with the store:
    # on a full run, all of them; on a partial run, only the reloaded ones.
    ledger = _read_ledger()
    for act_id, source_hash in result.source_hashes.items():
        if only_acts is None or act_id in result.loaded_acts:
            ledger[act_id] = source_hash
    _LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")

    cov = result.coverage
    print("Phase 0 ingestion complete.")
    if only_acts is not None:
        print(f"  acts reloaded:       {', '.join(sorted(result.loaded_acts)) or '(none)'}")
    print(f"  chunks loaded:       {len(result.chunks)}")
    print(f"  flagged (withheld):  {len(result.validation.flagged)}")
    print(f"  orphaned children:   {len(result.validation.orphaned_children)}")
    print(f"  overall coverage:    {cov.overall_coverage:.0%}")
    print(f"  coverage gate >=80%: {cov.meets_threshold(0.80)}")
    print(f"  IPC-BNS verified:    {result.mapping_verified}")
    print(f"  landmark judgments:  {len(result.landmarks)}")
    print(f"  checkpoint artifact: {_ARTIFACT}")
    print("  status: AWAITING HUMAN APPROVAL")


if __name__ == "__main__":
    main()
