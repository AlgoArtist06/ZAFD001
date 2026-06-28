"""Run the Phase 0 ingestion pipeline and emit the checkpoint artifact.

    python -m ingestion

Re-runnable: download/parse/chunk/validate/embed/load, then write the
consolidated checkpoint artifact for the single human review.
"""
from __future__ import annotations

from pathlib import Path

from ingestion.checkpoint import build_checkpoint
from ingestion.pipeline import default_config, run_ingestion

_ARTIFACT = Path(__file__).resolve().parent.parent / "artifacts" / "phase0_checkpoint.md"


def main() -> None:
    result = run_ingestion(default_config())
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    _ARTIFACT.write_text(build_checkpoint(result))

    cov = result.coverage
    print("Phase 0 ingestion complete.")
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
