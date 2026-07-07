// Government scheme fact-card loader, ported from ingestion/schemes.py.
// Schemes are curated structured fact-cards rather than parsed statute. Each
// card becomes a single loadable scheme chunk whose Provenance Record carries
// the governing authority and official scheme URL in place of a section
// number.
import { readFileSync } from "node:fs";

import { type Chunk } from "../../convex/lib/models";

type SchemeCard = {
  id: string;
  name: string;
  year: number;
  facts: string;
  scheme_url: string;
  source_hash: string;
  governing_authority: string;
};

export function loadSchemeChunks(path: string): Chunk[] {
  const raw = JSON.parse(readFileSync(path, "utf8")) as {
    retrieval_date: string;
    schemes: SchemeCard[];
  };
  return raw.schemes.map((scheme) => ({
    chunkId: `scheme-${scheme.id}`,
    actId: scheme.id,
    text: scheme.facts,
    provenance: {
      actName: scheme.name,
      actYear: scheme.year,
      actType: "scheme" as const,
      sourceUrl: scheme.scheme_url,
      sourceHash: scheme.source_hash,
      retrievalDate: raw.retrieval_date,
      verbatimText: scheme.facts,
      governingAuthority: scheme.governing_authority,
      schemeUrl: scheme.scheme_url,
    },
    amendmentHistory: { entries: [], noneRecorded: true },
    isDefinition: false,
    tokenEstimate: 0,
  }));
}
