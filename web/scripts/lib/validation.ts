// The ingestion validation gate, ported from ingestion/validation.py.
// Partitions chunks into loadable (complete Provenance Record) and flagged
// (incomplete - never loaded), and checks structural integrity: no orphaned
// child chunks, every parent link resolves, section gaps flagged (logged,
// not fatal).
import {
  isLoadable,
  missingProvenanceFields,
  type Chunk,
} from "../../convex/lib/models";
import { sectionId } from "./chunker";

export type Flag = {
  chunkId: string;
  reasons: string[];
};

export type ValidationReport = {
  loadable: Chunk[];
  flagged: Flag[];
  orphanedChildren: string[];
  sectionGaps: Array<[string, string]>;
};

export function structuralOk(report: ValidationReport): boolean {
  return report.orphanedChildren.length === 0;
}

function sectionGapsOf(chunks: Chunk[]): Array<[string, string]> {
  const byAct = new Map<string, Set<number>>();
  for (const chunk of chunks) {
    if (chunk.sectionNumber && /^\d+$/.test(chunk.sectionNumber)) {
      if (!byAct.has(chunk.actId)) byAct.set(chunk.actId, new Set());
      byAct.get(chunk.actId)!.add(parseInt(chunk.sectionNumber, 10));
    }
  }
  const gaps: Array<[string, string]> = [];
  for (const [actId, numbers] of byAct) {
    const min = Math.min(...numbers);
    const max = Math.max(...numbers);
    for (let missing = min; missing <= max; missing++) {
      if (!numbers.has(missing)) gaps.push([actId, String(missing)]);
    }
  }
  return gaps;
}

export function validateChunks(chunks: Chunk[]): ValidationReport {
  const report: ValidationReport = {
    loadable: [],
    flagged: [],
    orphanedChildren: [],
    sectionGaps: [],
  };

  const validSectionIds = new Set(
    chunks
      .filter((c) => c.sectionNumber !== undefined)
      .map((c) => sectionId(c.actId, c.sectionNumber!)),
  );

  for (const chunk of chunks) {
    if (!isLoadable(chunk)) {
      report.flagged.push({
        chunkId: chunk.chunkId,
        reasons: missingProvenanceFields(chunk.provenance),
      });
      continue;
    }
    if (
      chunk.parentSectionId !== undefined &&
      !validSectionIds.has(chunk.parentSectionId)
    ) {
      report.orphanedChildren.push(chunk.chunkId);
      continue;
    }
    report.loadable.push(chunk);
  }

  report.sectionGaps = sectionGapsOf(chunks);
  return report;
}
