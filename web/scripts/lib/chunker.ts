// Adaptive hierarchical chunking, ported from ingestion/chunker.py. A section
// under the token threshold is stored as one whole chunk; a larger section is
// split into per-sub-section child chunks that each carry a parentSectionId.
// Sub-section text is stored once (parent expansion is a query-time concern).
import {
  type AmendmentHistory,
  type Chunk,
  type ProvenanceRecord,
} from "../../convex/lib/models";
import { type ParsedAct, type Section } from "./parser";

// Cheap, monotonic token estimate (whitespace words).
export function estimateTokens(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

export function sectionId(actId: string, sectionNumber: string): string {
  return `${actId}-${sectionNumber}`;
}

function provenance(
  act: ParsedAct,
  section: Section,
  verbatim: string,
  subSection?: string,
): ProvenanceRecord {
  return {
    actName: act.actName,
    actYear: act.actYear,
    actType: act.actType,
    sourceUrl: act.sourceUrl,
    sourceHash: act.sourceHash,
    retrievalDate: act.retrievalDate,
    verbatimText: verbatim,
    sectionNumber: section.sectionNumber,
    subSection,
  };
}

function amendmentHistory(section: Section): AmendmentHistory {
  return {
    entries: [...section.amendments],
    noneRecorded: section.amendments.length === 0,
  };
}

export function chunkSection(
  act: ParsedAct,
  section: Section,
  tokenThreshold: number,
): Chunk[] {
  const parentId = sectionId(act.actId, section.sectionNumber);
  const whole = section.fullText;
  if (estimateTokens(whole) <= tokenThreshold || section.subSections.length === 0) {
    return [
      {
        chunkId: parentId,
        actId: act.actId,
        sectionNumber: section.sectionNumber,
        text: whole,
        provenance: provenance(act, section, whole),
        amendmentHistory: amendmentHistory(section),
        isDefinition: section.isDefinition,
        tokenEstimate: estimateTokens(whole),
      },
    ];
  }

  const children: Chunk[] = [];
  // A chunkId is the point's primary key in the store, so it must be unique.
  // Sub-section labels can repeat within one section (e.g. a definitions
  // section where many clauses carry an inner "(i)"); disambiguate a repeated
  // label with a positional suffix while the displayed subSection keeps the
  // real label.
  const seen = new Map<string, number>();
  for (const sub of section.subSections) {
    const count = (seen.get(sub.label) ?? 0) + 1;
    seen.set(sub.label, count);
    const uniqueLabel = count === 1 ? sub.label : `${sub.label}-${count}`;
    children.push({
      chunkId: `${parentId}-${uniqueLabel}`,
      actId: act.actId,
      sectionNumber: section.sectionNumber,
      subSection: sub.label,
      parentSectionId: parentId,
      text: sub.text,
      provenance: provenance(act, section, sub.text, sub.label),
      amendmentHistory: amendmentHistory(section),
      isDefinition: section.isDefinition,
      tokenEstimate: estimateTokens(sub.text),
    });
  }
  return children;
}

export function chunkAct(act: ParsedAct, tokenThreshold = 512): Chunk[] {
  return act.sections.flatMap((section) =>
    chunkSection(act, section, tokenThreshold),
  );
}
