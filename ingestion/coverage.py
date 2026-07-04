"""Coverage report.

Coverage is the proportion of an in-scope act's sections that made it into the
Source of Truth. We report two numbers per act: coverage against the curated v1
in-scope target (the Phase 0 gate, expected 80-90%), and the uncovered remainder
against the act's full official section count (logged and known, so partial
coverage is safe under the no-provenance-no-answer and graceful out-of-scope
rules).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class ActCoverage:
    act_id: str
    ingested: int
    in_scope_target: int
    official_total: int
    coverage: float
    uncovered_remainder: int
    missing_sections: List[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    per_act: Dict[str, ActCoverage]

    @property
    def overall_coverage(self) -> float:
        target = sum(a.in_scope_target for a in self.per_act.values())
        covered = sum(a.coverage * a.in_scope_target for a in self.per_act.values())
        return covered / target if target else 0.0

    def meets_threshold(self, minimum: float = 0.80) -> bool:
        return self.overall_coverage >= minimum and all(
            a.coverage >= minimum for a in self.per_act.values()
        )


def build_coverage_report(
    ingested_by_act: Dict[str, Set[str]], manifest: Dict[str, dict]
) -> CoverageReport:
    per_act: Dict[str, ActCoverage] = {}
    for act_id, spec in manifest.items():
        in_scope = list(spec["in_scope_sections"])
        ingested = ingested_by_act.get(act_id, set())
        covered = [s for s in in_scope if s in ingested]
        missing = [s for s in in_scope if s not in ingested]
        official_total = spec["official_total_sections"]
        per_act[act_id] = ActCoverage(
            act_id=act_id,
            ingested=len(ingested),
            in_scope_target=len(in_scope),
            official_total=official_total,
            coverage=len(covered) / len(in_scope) if in_scope else 0.0,
            # Amended acts ingest lettered insertions (66C, 194B, ...) beyond
            # the base published count, so the remainder floors at zero.
            uncovered_remainder=max(0, official_total - len(ingested)),
            missing_sections=missing,
        )
    return CoverageReport(per_act=per_act)
