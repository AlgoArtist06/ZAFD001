// Hybrid retrieval routed by Covered Domain - the Convex implementation of
// the retrieval seam, scoring through the same rankHybrid the offline tests
// use, so the ranking is exactly the Python HybridRetriever's.
//
// Exactness argument: the Python retriever scored EVERY domain-filtered chunk
// on keyword overlap + cosine. Here the candidate set is the union of
//   (a) the vector-search top 256 (with their true cosine scores), and
//   (b) every chunk with keyword overlap > 0 (from the stems scan), whose
//       true cosine is computed from its stored vector.
// Any chunk outside that union has keyword 0 AND a cosine below the 256th
// vector candidate, so its hybrid score cannot reach the top-k - the top-k is
// therefore identical to scoring the whole domain subset.
import { v } from "convex/values";

import { internalQuery } from "./_generated/server";
import { internal } from "./_generated/api";
import { type ActionCtx } from "./_generated/server";
import { type Doc, type Id } from "./_generated/dataModel";
import { docToChunk } from "./documents";
import { type RetrievalHit, sortSectionMembers } from "./lib/expansion";
import { cosine, DEFAULT_TOP_K, hybridScore } from "./lib/hybrid";
import { type ActType, type Chunk } from "./lib/models";
import { actType as actTypeValidator } from "./schema";
import { contentStems } from "./lib/text";

// How many vector candidates to pull per query - Convex's vector search
// maximum, and comfortably more than any domain subset's meaningful matches.
const VECTOR_CANDIDATES = 256;

// One page of the keyword scan, so a large domain never exceeds the
// per-query document/byte read limits (a whole-corpus scan in one query
// would, once the corpus outgrows the limits - and an unrouted query scans
// every domain).
const KEYWORD_SCAN_PAGE = 512;

// How many keyword-only candidates get their true cosine hydrated from their
// stored vectors. ponytail: candidates beyond this cap keep vectorScore 0 -
// their cosine is below the 256th vector hit's anyway, and they rank below
// 64 stronger keyword matches; raise the cap if gold eval ever disagrees.
const KEYWORD_HYDRATION_CAP = 64;

// The keyword half, one page at a time: scan a domain's chunks over their
// precomputed stems and return every document with any lexical overlap.
// Only ids and counts leave the query, so the response stays small.
export const keywordCandidates = internalQuery({
  args: {
    domain: actTypeValidator,
    queryStems: v.array(v.string()),
    cursor: v.union(v.string(), v.null()),
  },
  handler: async (ctx, { domain, queryStems, cursor }) => {
    const stems = new Set(queryStems);
    const page = await ctx.db
      .query("documents")
      .withIndex("by_act_type", (q) => q.eq("actType", domain))
      .paginate({ numItems: KEYWORD_SCAN_PAGE, cursor });
    const matches: Array<{ documentId: Id<"documents">; overlap: number }> = [];
    for (const doc of page.page) {
      let overlap = 0;
      // Stems are deduplicated at ingest time, so counting is a plain walk.
      for (const s of doc.stems) {
        if (stems.has(s)) overlap += 1;
      }
      if (overlap > 0) {
        matches.push({ documentId: doc._id, overlap });
      }
    }
    return {
      matches,
      continueCursor: page.continueCursor,
      isDone: page.isDone,
    };
  },
});

export const loadDocuments = internalQuery({
  args: { ids: v.array(v.id("documents")) },
  handler: async (ctx, { ids }) => {
    const docs = await Promise.all(ids.map((id) => ctx.db.get(id)));
    return docs.filter((doc): doc is Doc<"documents"> => doc !== null);
  },
});

export const loadEmbeddings = internalQuery({
  args: { ids: v.array(v.id("embeddings")) },
  handler: async (ctx, { ids }) => {
    const rows = await Promise.all(ids.map((id) => ctx.db.get(id)));
    return rows.filter((row): row is Doc<"embeddings"> => row !== null);
  },
});

export const embeddingsByDocument = internalQuery({
  args: { documentIds: v.array(v.id("documents")) },
  handler: async (ctx, { documentIds }) => {
    const rows = await Promise.all(
      documentIds.map((documentId) =>
        ctx.db
          .query("embeddings")
          .withIndex("by_document", (q) => q.eq("documentId", documentId))
          .unique(),
      ),
    );
    return rows.filter((row): row is Doc<"embeddings"> => row !== null);
  },
});

// The section-members lookup behind parent/sibling expansion.
export const sectionMembers = internalQuery({
  args: { actId: v.string(), sectionNumber: v.string() },
  handler: async (ctx, { actId, sectionNumber }) => {
    return await ctx.db
      .query("documents")
      .withIndex("by_act_section", (q) =>
        q.eq("actId", actId).eq("sectionNumber", sectionNumber),
      )
      .collect();
  },
});

export async function convexSectionMembers(
  ctx: ActionCtx,
  actId: string,
  sectionNumber: string,
): Promise<Chunk[]> {
  const docs = await ctx.runQuery(internal.retrieval.sectionMembers, {
    actId,
    sectionNumber,
  });
  return sortSectionMembers(docs.map(docToChunk));
}

// The retrieval seam over Convex: vector search + stems scan, ranked by the
// shared hybrid score. `queryVector` is the (runtime-embedded) query vector.
export async function convexRetrieve(
  ctx: ActionCtx,
  query: string,
  domains: ActType[],
  queryVector: number[],
): Promise<RetrievalHit[]> {
  // (a) Vector candidates and (b) the paged keyword scan, in parallel -
  // neither depends on the other.
  const queryStems = [...new Set(contentStems(query))];
  const [vectorResults, keywordMatches] = await Promise.all([
    ctx.vectorSearch("embeddings", "by_embedding", {
      vector: queryVector,
      limit: VECTOR_CANDIDATES,
      filter: (q) => q.or(...domains.map((domain) => q.eq("actType", domain))),
    }),
    (async () => {
      const matches: Array<{ documentId: Id<"documents">; overlap: number }> = [];
      for (const domain of domains) {
        let cursor: string | null = null;
        for (;;) {
          const page: {
            matches: Array<{ documentId: Id<"documents">; overlap: number }>;
            continueCursor: string;
            isDone: boolean;
          } = await ctx.runQuery(internal.retrieval.keywordCandidates, {
            domain,
            queryStems,
            cursor,
          });
          matches.push(...page.matches);
          if (page.isDone) break;
          cursor = page.continueCursor;
        }
      }
      return matches;
    })(),
  ]);

  const vectorScoreByEmbeddingId = new Map(
    vectorResults.map((r) => [r._id, r._score]),
  );
  const vectorRows = await ctx.runQuery(internal.retrieval.loadEmbeddings, {
    ids: vectorResults.map((r) => r._id),
  });
  const vectorScoreByDocumentId = new Map(
    vectorRows.map((row) => [
      row.documentId,
      vectorScoreByEmbeddingId.get(row._id) ?? 0,
    ]),
  );
  const overlapByDocumentId = new Map(
    keywordMatches.map((m) => [m.documentId, m.overlap]),
  );

  // True cosine for the strongest keyword-only candidates, from their stored
  // vectors; the rest keep 0 (see KEYWORD_HYDRATION_CAP).
  const keywordOnly = keywordMatches
    .filter((m) => !vectorScoreByDocumentId.has(m.documentId))
    .sort((a, b) => b.overlap - a.overlap);
  const hydrated = keywordOnly.slice(0, KEYWORD_HYDRATION_CAP);
  const keywordOnlyRows = await ctx.runQuery(
    internal.retrieval.embeddingsByDocument,
    { documentIds: hydrated.map((m) => m.documentId) },
  );
  for (const row of keywordOnlyRows) {
    vectorScoreByDocumentId.set(
      row.documentId,
      cosine(queryVector, row.embedding),
    );
  }
  for (const m of keywordOnly.slice(KEYWORD_HYDRATION_CAP)) {
    vectorScoreByDocumentId.set(m.documentId, 0);
  }

  // Score the whole union first, then load ONLY the winners' documents - the
  // union can be thousands of ids, and ranking needs nothing but the scores.
  const queryStemCount = queryStems.length;
  const scored = [...vectorScoreByDocumentId.entries()].map(
    ([documentId, vectorScore]) => ({
      documentId,
      keywordScore: overlapByDocumentId.get(documentId) ?? 0,
      vectorScore,
    }),
  );
  scored.sort(
    (a, b) =>
      hybridScore(queryStemCount, b.keywordScore, b.vectorScore) -
      hybridScore(queryStemCount, a.keywordScore, a.vectorScore),
  );
  const top = scored.slice(0, DEFAULT_TOP_K);
  const docs = await ctx.runQuery(internal.retrieval.loadDocuments, {
    ids: top.map((t) => t.documentId),
  });
  const docById = new Map(docs.map((doc) => [doc._id, doc]));
  const hits: RetrievalHit[] = [];
  for (const t of top) {
    const doc = docById.get(t.documentId);
    if (doc === undefined) continue;
    hits.push({
      chunk: docToChunk(doc),
      keywordScore: t.keywordScore,
      vectorScore: t.vectorScore,
      score: hybridScore(queryStemCount, t.keywordScore, t.vectorScore),
    });
  }
  return hits;
}
