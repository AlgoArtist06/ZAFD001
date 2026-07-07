import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

// The Covered Domains, mirroring the Python ActType enum. Retrieval is
// metadata-filtered by this field, so it is also the vector index filter.
export const actType = v.union(
  v.literal("criminal"),
  v.literal("consumer"),
  v.literal("ip"),
  v.literal("constitutional"),
  v.literal("scheme"),
  v.literal("cyber"),
  v.literal("transport"),
  v.literal("governance"),
  v.literal("protection"),
);

// A verified Citation in its wire form, as persisted on a turn - the same
// shape the FastAPI backend stored, so reloads show verbatim text.
export const citationValidator = v.object({
  reference: v.string(),
  verbatim: v.string(),
  url: v.string(),
});

const streamState = v.union(
  v.literal("normal"),
  v.literal("emergency"),
  v.literal("refusal"),
  v.literal("error"),
);

// The mutable fields of a stream document, as the pipeline writes them - so
// the internal update/finish mutations stay schema-validated instead of
// taking an untyped bag.
export const streamFieldsValidator = v.object({
  state: v.optional(streamState),
  explanation: v.optional(v.string()),
  citations: v.optional(v.array(citationValidator)),
  language: v.optional(v.string()),
  reason: v.optional(v.string()),
  detail: v.optional(v.string()),
  highStakesNotice: v.optional(v.string()),
  note: v.optional(v.string()),
  nextStep: v.optional(v.string()),
  disclaimer: v.optional(v.string()),
});

export default defineSchema({
  // The Source of Truth: one row per corpus chunk, with its Provenance Record
  // inline (no provenance, no answer - enforced at ingest time).
  //
  // Embedding lifecycle rule: embeddings are an ingestion-time artifact only.
  // `contentHash` + `embeddingModel` are the change-detection key - the ingest
  // script skips any chunk whose hash and model are unchanged, and nothing at
  // runtime ever (re)embeds corpus text. Runtime embeds the query, only.
  documents: defineTable({
    chunkId: v.string(),
    actId: v.string(),
    text: v.string(),
    sectionNumber: v.optional(v.string()),
    subSection: v.optional(v.string()),
    parentSectionId: v.optional(v.string()),
    isDefinition: v.boolean(),
    tokenEstimate: v.float64(),
    // Provenance Record (citation metadata, traceable to a government source).
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
    // The corpus is English-only by design; queries are normalised to English
    // before retrieval.
    language: v.literal("en"),
    // Embedding lifecycle bookkeeping (see rule above).
    sourceFile: v.string(),
    contentHash: v.string(),
    embeddingModel: v.string(),
    lastEmbeddedAt: v.float64(),
    // Precomputed content stems, so keyword scoring never re-tokenises the
    // corpus per query. Must be produced by the same stemmer retrieval uses.
    stems: v.array(v.string()),
  })
    .index("by_chunk_id", ["chunkId"])
    .index("by_act_section", ["actId", "sectionNumber"])
    .index("by_act_type", ["actType"])
    .index("by_source_file", ["sourceFile"]),

  // Corpus vectors, one row per chunk, separate from `documents` so keyword
  // scans of the corpus never read 768-float arrays (Convex reads whole rows;
  // this is what keeps the exact hybrid score affordable).
  embeddings: defineTable({
    chunkId: v.string(),
    documentId: v.id("documents"),
    actType,
    model: v.string(),
    embedding: v.array(v.float64()),
  })
    .vectorIndex("by_embedding", {
      vectorField: "embedding",
      dimensions: 768,
      filterFields: ["actType"],
    })
    .index("by_chunk_id", ["chunkId"])
    .index("by_document", ["documentId"]),

  // A Conversation is owned by exactly one user (the Clerk subject); every
  // read and write is scoped by that owner.
  conversations: defineTable({
    userId: v.string(),
  }).index("by_user", ["userId"]),

  // One exchange in a Conversation: the user's words, the standalone query
  // they resolved to (follow-up memory), and the structured answer.
  turns: defineTable({
    conversationId: v.id("conversations"),
    query: v.string(),
    resolved: v.string(),
    answer: v.string(),
    refused: v.boolean(),
    citations: v.array(citationValidator),
  }).index("by_conversation", ["conversationId"]),

  // Consent is a legal fact (DPDP Act): the recorded acceptance of a specific
  // privacy-notice version, erased on a right-to-erasure request.
  consents: defineTable({
    userId: v.string(),
    noticeVersion: v.string(),
    consentedAt: v.string(),
  }).index("by_user", ["userId"]),

  // One in-flight (or just-finished) answer, streamed to the client as
  // reactive document updates - the Convex replacement for the NDJSON frame
  // stream. The fields mirror the frontend's StructuredAnswer exactly; the
  // explanation grows cumulatively while generation runs. Rows are transient:
  // a user's finished rows are swept when they ask their next question.
  streams: defineTable({
    userId: v.string(),
    conversationId: v.optional(v.id("conversations")),
    done: v.boolean(),
    state: streamState,
    explanation: v.string(),
    citations: v.array(citationValidator),
    language: v.optional(v.string()),
    reason: v.optional(v.string()),
    detail: v.optional(v.string()),
    highStakesNotice: v.optional(v.string()),
    note: v.optional(v.string()),
    nextStep: v.optional(v.string()),
    disclaimer: v.optional(v.string()),
  }).index("by_user", ["userId"]),
});
