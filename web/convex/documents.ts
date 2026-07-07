// The Source of Truth's storage seam: corpus chunks in the `documents` table
// plus their vectors in `embeddings`, written only by
// scripts/ingestLegalCorpus.ts.
//
// Embedding lifecycle rule: corpus embeddings are created at ingest time and
// stored permanently. Nothing here calls an embedding API; the ingest script
// compares each chunk's contentHash + embeddingModel against `corpusMeta` and
// skips unchanged chunks, so the system restarts forever with zero corpus
// embedding calls. Whole-corpus wipes never happen implicitly: the script
// deletes only chunks that disappeared from the sources.
import { ConvexError, v } from "convex/values";

import { mutation, query } from "./_generated/server";
import { type Doc } from "./_generated/dataModel";
import { actType } from "./schema";
import { provenanceIsComplete, type Chunk } from "./lib/models";

// Ingestion is an operator action, not a user one: the script authenticates
// with the INGEST_KEY set on the deployment, never with a user session.
function requireIngestKey(provided: string): void {
  const expected = process.env.INGEST_KEY;
  if (!expected || provided !== expected) {
    throw new ConvexError(
      "Ingestion requires the deployment's INGEST_KEY (npx convex env set INGEST_KEY ...).",
    );
  }
}

// A corpus row (stored, or about to be stored - system columns not needed)
// in the domain Chunk shape the retrieval pipeline uses.
export function docToChunk(
  doc: Omit<Doc<"documents">, "_id" | "_creationTime">,
): Chunk {
  return {
    chunkId: doc.chunkId,
    actId: doc.actId,
    text: doc.text,
    sectionNumber: doc.sectionNumber,
    subSection: doc.subSection,
    parentSectionId: doc.parentSectionId,
    isDefinition: doc.isDefinition,
    tokenEstimate: doc.tokenEstimate,
    provenance: {
      actName: doc.actName,
      actYear: doc.actYear,
      actType: doc.actType,
      sourceUrl: doc.sourceUrl,
      sourceHash: doc.sourceHash,
      retrievalDate: doc.retrievalDate,
      verbatimText: doc.text,
      sectionNumber: doc.sectionNumber,
      subSection: doc.subSection,
      governingAuthority: doc.governingAuthority,
      schemeUrl: doc.schemeUrl,
    },
    amendmentHistory: {
      entries: doc.amendments,
      noneRecorded: doc.amendmentsNoneRecorded,
    },
  };
}

const chunkInput = v.object({
  chunkId: v.string(),
  actId: v.string(),
  text: v.string(),
  sectionNumber: v.optional(v.string()),
  subSection: v.optional(v.string()),
  parentSectionId: v.optional(v.string()),
  isDefinition: v.boolean(),
  tokenEstimate: v.float64(),
  actName: v.string(),
  actYear: v.float64(),
  actType,
  sourceUrl: v.string(),
  sourceHash: v.string(),
  retrievalDate: v.string(),
  governingAuthority: v.optional(v.string()),
  schemeUrl: v.optional(v.string()),
  amendments: v.array(
    v.object({
      year: v.float64(),
      description: v.string(),
      citation: v.optional(v.string()),
    }),
  ),
  amendmentsNoneRecorded: v.boolean(),
  language: v.literal("en"),
  sourceFile: v.string(),
  contentHash: v.string(),
  embeddingModel: v.string(),
  lastEmbeddedAt: v.float64(),
  stems: v.array(v.string()),
  embedding: v.array(v.float64()),
});

// The change-detection view: stored chunks' identity and lifecycle
// fingerprints, one page at a time (a whole-corpus collect() would blow the
// per-query read limits once the corpus is large). The ingest script loops
// the cursor.
export const corpusMeta = query({
  args: { ingestKey: v.string(), cursor: v.union(v.string(), v.null()) },
  handler: async (ctx, { ingestKey, cursor }) => {
    requireIngestKey(ingestKey);
    const page = await ctx.db
      .query("documents")
      .paginate({ numItems: 500, cursor });
    return {
      page: page.page.map((doc) => ({
        chunkId: doc.chunkId,
        contentHash: doc.contentHash,
        embeddingModel: doc.embeddingModel,
      })),
      continueCursor: page.continueCursor,
      isDone: page.isDone,
    };
  },
});

// Insert or replace a batch of chunks and their vectors. "No provenance, no
// answer" is enforced HERE, at the storage boundary, not only in the ingest
// script: a chunk with an incomplete Provenance Record can never enter the
// Source of Truth, whatever wrote it.
export const upsertChunks = mutation({
  args: { ingestKey: v.string(), chunks: v.array(chunkInput) },
  handler: async (ctx, { ingestKey, chunks }) => {
    requireIngestKey(ingestKey);
    for (const chunk of chunks) {
      if (!provenanceIsComplete(docToChunk(chunk).provenance)) {
        throw new ConvexError(
          `chunk ${chunk.chunkId} has an incomplete Provenance Record - ` +
            "no provenance, no answer",
        );
      }
    }
    for (const { embedding, ...doc } of chunks) {
      const existing = await ctx.db
        .query("documents")
        .withIndex("by_chunk_id", (q) => q.eq("chunkId", doc.chunkId))
        .unique();
      let documentId;
      if (existing) {
        await ctx.db.replace(existing._id, doc);
        documentId = existing._id;
      } else {
        documentId = await ctx.db.insert("documents", doc);
      }
      const existingEmbedding = await ctx.db
        .query("embeddings")
        .withIndex("by_document", (q) => q.eq("documentId", documentId))
        .unique();
      const embeddingRow = {
        chunkId: doc.chunkId,
        documentId,
        actType: doc.actType,
        model: doc.embeddingModel,
        embedding,
      };
      if (existingEmbedding) {
        await ctx.db.replace(existingEmbedding._id, embeddingRow);
      } else {
        await ctx.db.insert("embeddings", embeddingRow);
      }
    }
  },
});

// Remove chunks that disappeared from the sources (a renamed or deleted
// section must not linger as a stale document).
export const removeChunks = mutation({
  args: { ingestKey: v.string(), chunkIds: v.array(v.string()) },
  handler: async (ctx, { ingestKey, chunkIds }) => {
    requireIngestKey(ingestKey);
    for (const chunkId of chunkIds) {
      const doc = await ctx.db
        .query("documents")
        .withIndex("by_chunk_id", (q) => q.eq("chunkId", chunkId))
        .unique();
      if (doc === null) continue;
      const embedding = await ctx.db
        .query("embeddings")
        .withIndex("by_document", (q) => q.eq("documentId", doc._id))
        .unique();
      if (embedding) await ctx.db.delete(embedding._id);
      await ctx.db.delete(doc._id);
    }
  },
});
