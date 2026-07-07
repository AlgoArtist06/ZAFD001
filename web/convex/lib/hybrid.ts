// The pure heart of hybrid retrieval, ported from rag/domain/retrieval.py:
// query expansion, the normalized hybrid score, and candidate ranking.
// Combines keyword overlap (exact section references, act names, statutory
// terms) with vector similarity (natural-language complaints). The keyword
// score doubles as the support gate: a hit with zero lexical overlap is not
// grounded in the Source of Truth.
//
// The Convex-backed retriever (convex/retrieval.ts) and the in-memory test
// retriever both rank through this one function, so the score is identical
// everywhere.
import { type Chunk } from "./models";
import { contentStems } from "./text";
import { type RetrievalHit } from "./expansion";

// Complaint-to-concept normalization: lay words mapped to the statutory term
// they describe, injected into the query before retrieval.
const LAY_CONCEPTS: Record<string, string> = {
  tricked: "cheating fraud",
  fooled: "cheating fraud",
  conned: "cheating fraud",
  duped: "cheating fraud",
  swindled: "cheating fraud",
  ripped: "cheating fraud",
  scammed: "cheating fraud",
};

const WORD_RE = /[a-z]+/g;

// Prepare a query for retrieval: append the legal concept behind any lay
// complaint word it recognises.
export function expandQuery(query: string): string {
  const words = new Set(query.toLowerCase().match(WORD_RE) ?? []);
  const additions = [...words]
    .filter((w) => w in LAY_CONCEPTS)
    .map((w) => LAY_CONCEPTS[w]);
  return additions.length > 0 ? `${query} ${additions.join(" ")}` : query;
}

export const DEFAULT_TOP_K = 8;
export const DEFAULT_HYBRID_ALPHA = 0.5;

// One retrieval candidate before ranking: its chunk, its keyword overlap with
// the query stems, and its vector similarity to the query embedding.
export type Candidate = {
  chunk: Chunk;
  keywordScore: number;
  vectorScore: number;
};

export function keywordOverlap(
  queryStems: Set<string>,
  chunkStems: Iterable<string>,
): number {
  const unique = new Set(chunkStems);
  let overlap = 0;
  for (const s of unique) {
    if (queryStems.has(s)) overlap += 1;
  }
  return overlap;
}

// The one normalized hybrid score. HYBRID_ALPHA weighs the two normalized
// signals: 0 = pure keyword overlap, 1 = pure vector similarity. Both land
// in [0, 1], so neither can drown the other.
export function hybridScore(
  queryStemCount: number,
  keywordScore: number,
  vectorScore: number,
  alpha: number = DEFAULT_HYBRID_ALPHA,
): number {
  const keywordNorm = queryStemCount > 0 ? keywordScore / queryStemCount : 0;
  return (1 - alpha) * keywordNorm + alpha * vectorScore;
}

// Rank candidates by the hybrid score.
export function rankHybrid(
  query: string,
  candidates: Candidate[],
  options: { topK?: number; alpha?: number } = {},
): RetrievalHit[] {
  const topK = options.topK ?? DEFAULT_TOP_K;
  const queryStemCount = new Set(contentStems(query)).size;
  const hits = candidates.map((candidate) => ({
    chunk: candidate.chunk,
    keywordScore: candidate.keywordScore,
    vectorScore: candidate.vectorScore,
    score: hybridScore(
      queryStemCount,
      candidate.keywordScore,
      candidate.vectorScore,
      options.alpha,
    ),
  }));
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, topK);
}

export function cosine(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    sum += a[i] * b[i];
  }
  return sum;
}
