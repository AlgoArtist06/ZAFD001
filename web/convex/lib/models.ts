// Corpus domain models, ported from ingestion/models.py. The vocabulary
// follows CONTEXT.md: a ProvenanceRecord is the mandatory metadata that makes
// a Citation traceable to a government Source of Truth, and the hard rule is
// "no provenance, no answer" - enforced via isLoadable().

export const ACT_TYPES = [
  "criminal",
  "consumer",
  "ip",
  "constitutional",
  "scheme",
  "cyber",
  "transport",
  "governance",
  "protection",
] as const;

export type ActType = (typeof ACT_TYPES)[number];

export type AmendmentEntry = {
  year: number;
  description: string;
  citation?: string;
};

// "Captured" means ingestion explicitly recorded the amendment state: either
// entries, or an explicit noneRecorded flag. Empty and unflagged means the
// ingestion never looked, which fails the captured-per-section criterion.
export type AmendmentHistory = {
  entries: AmendmentEntry[];
  noneRecorded: boolean;
};

export function amendmentsCaptured(history: AmendmentHistory): boolean {
  return history.entries.length > 0 || history.noneRecorded;
}

export type ProvenanceRecord = {
  actName: string;
  actYear: number;
  actType: ActType;
  sourceUrl: string;
  sourceHash: string;
  retrievalDate: string; // ISO date
  verbatimText: string;
  sectionNumber?: string;
  subSection?: string;
  governingAuthority?: string;
  schemeUrl?: string;
};

// The unit produced by the pipeline and (if loadable) embedded into the
// vector store. Children of a large section carry a parentSectionId.
export type Chunk = {
  chunkId: string;
  actId: string;
  text: string;
  provenance: ProvenanceRecord;
  amendmentHistory: AmendmentHistory;
  sectionNumber?: string;
  subSection?: string;
  parentSectionId?: string;
  isDefinition: boolean;
  tokenEstimate: number;
};

export function provenanceIsComplete(p: ProvenanceRecord): boolean {
  const common = Boolean(
    p.actName &&
      p.actYear &&
      p.actType &&
      p.sourceUrl &&
      p.sourceHash &&
      p.retrievalDate &&
      p.verbatimText,
  );
  if (!common) return false;
  if (p.actType === "scheme") {
    return Boolean(p.governingAuthority && p.schemeUrl);
  }
  return Boolean(p.sectionNumber);
}

export function missingProvenanceFields(p: ProvenanceRecord): string[] {
  const missing = (
    [
      ["actName", p.actName],
      ["actYear", p.actYear],
      ["actType", p.actType],
      ["sourceUrl", p.sourceUrl],
      ["sourceHash", p.sourceHash],
      ["retrievalDate", p.retrievalDate],
      ["verbatimText", p.verbatimText],
    ] as const
  )
    .filter(([, value]) => !value)
    .map(([name]) => name as string);
  if (p.actType === "scheme") {
    if (!p.governingAuthority) missing.push("governingAuthority");
    if (!p.schemeUrl) missing.push("schemeUrl");
  } else if (!p.sectionNumber) {
    missing.push("sectionNumber");
  }
  return missing;
}

// No provenance, no answer: only fully-provenanced chunks load.
export function isLoadable(chunk: Chunk): boolean {
  return provenanceIsComplete(chunk.provenance);
}
