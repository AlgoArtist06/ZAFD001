// Coverage report, ported from ingestion/coverage.py. Coverage is the
// proportion of an in-scope act's sections that made it into the Source of
// Truth: reported against the curated v1 in-scope target (the human gate,
// expected 80-90%) and the uncovered remainder against the act's full
// official section count. Anything outside coverage is a Refusal, never a
// guess.

export type ActCoverage = {
  actId: string;
  ingested: number;
  inScopeTarget: number;
  officialTotal: number;
  coverage: number;
  uncoveredRemainder: number;
  missingSections: string[];
};

export type CoverageReport = {
  perAct: Record<string, ActCoverage>;
};

export function overallCoverage(report: CoverageReport): number {
  const acts = Object.values(report.perAct);
  const target = acts.reduce((sum, a) => sum + a.inScopeTarget, 0);
  const covered = acts.reduce((sum, a) => sum + a.coverage * a.inScopeTarget, 0);
  return target > 0 ? covered / target : 0;
}

export function meetsThreshold(report: CoverageReport, minimum = 0.8): boolean {
  return (
    overallCoverage(report) >= minimum &&
    Object.values(report.perAct).every((a) => a.coverage >= minimum)
  );
}

type ManifestAct = {
  official_total_sections: number;
  in_scope_sections: string[];
};

export function buildCoverageReport(
  ingestedByAct: Record<string, Set<string>>,
  manifest: Record<string, ManifestAct>,
): CoverageReport {
  const perAct: Record<string, ActCoverage> = {};
  for (const [actId, spec] of Object.entries(manifest)) {
    const inScope = [...spec.in_scope_sections];
    const ingested = ingestedByAct[actId] ?? new Set<string>();
    const covered = inScope.filter((s) => ingested.has(s));
    const missing = inScope.filter((s) => !ingested.has(s));
    const officialTotal = spec.official_total_sections;
    perAct[actId] = {
      actId,
      ingested: ingested.size,
      inScopeTarget: inScope.length,
      officialTotal,
      coverage: inScope.length > 0 ? covered.length / inScope.length : 0,
      // Amended acts ingest lettered insertions (66C, 194B, ...) beyond the
      // base published count, so the remainder floors at zero.
      uncoveredRemainder: Math.max(0, officialTotal - ingested.size),
      missingSections: missing,
    };
  }
  return { perAct };
}
