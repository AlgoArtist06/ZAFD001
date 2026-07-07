// The legal corpus ingestion pipeline: data/ -> parse -> chunk -> validate ->
// embed (changed chunks ONLY) -> store permanently in Convex.
//
//   npx tsx scripts/ingestLegalCorpus.ts             # incremental (default)
//   npx tsx scripts/ingestLegalCorpus.ts --dry-run   # report, change nothing
//
// Embedding lifecycle rule: embeddings are an ingestion-time artifact. Every
// chunk's contentHash + embeddingModel is compared against what Convex
// already stores; unchanged chunks are SKIPPED - re-running this script on an
// unchanged corpus makes zero embedding API calls. Chunks that disappeared
// from the sources are deleted; the corpus as a whole is never dropped.
//
// Environment (web/.env.local or the shell):
//   CONVEX_URL / NEXT_PUBLIC_CONVEX_URL - the deployment to load
//   INGEST_KEY                          - must match the deployment's env var
//   LLM_API_KEY (or EMBEDDING_API_KEY)  - the embedding credential
//   EMBEDDING_MODEL / EMBEDDING_BASE_URL / LLM_BASE_URL - provider selection
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { ConvexHttpClient } from "convex/browser";

import { api } from "../convex/_generated/api";
import { embeddingConfig, embedTexts } from "../convex/embeddings";
import { loadIpcBnsMapping } from "../convex/lib/mapping";
import { contentStems } from "../convex/lib/text";
import { type Chunk } from "../convex/lib/models";
import { chunkAct } from "./lib/chunker";
import {
  buildCoverageReport,
  meetsThreshold,
  overallCoverage,
} from "./lib/coverage";
import { loadEnvLocal } from "./lib/env";
import { parseAct } from "./lib/parser";
import { dataPath } from "./lib/repo";
import { loadSchemeChunks } from "./lib/schemes";
import { structuralOk, validateChunks } from "./lib/validation";

const CHUNK_TOKEN_THRESHOLD = 512;
const EMBED_BATCH = 64;
const UPSERT_BATCH = 100;

type StorableChunk = {
  chunkId: string;
  sourceFile: string;
  contentHash: string;
  chunk: Chunk;
  stems: string[];
};

type CorpusMetaPage = {
  page: Array<{
    chunkId: string;
    contentHash: string;
    embeddingModel: string;
  }>;
  continueCursor: string;
  isDone: boolean;
};

// The change-detection fingerprint: everything stored about the chunk except
// the embedding itself. Any change here (text, provenance, chunking) - or a
// different embedding model - triggers re-embedding; nothing else does.
function contentHashOf(chunk: Chunk, sourceFile: string): string {
  return createHash("sha256")
    .update(JSON.stringify({ chunk, sourceFile }))
    .digest("hex");
}

function buildCorpus(): StorableChunk[] {
  const sourcesDir = dataPath("sources");
  const all: StorableChunk[] = [];
  for (const file of readdirSync(sourcesDir).filter((f) => f.endsWith(".txt")).sort()) {
    const act = parseAct(readFileSync(join(sourcesDir, file), "utf8"));
    for (const chunk of chunkAct(act, CHUNK_TOKEN_THRESHOLD)) {
      all.push({
        chunkId: chunk.chunkId,
        sourceFile: `sources/${file}`,
        contentHash: contentHashOf(chunk, `sources/${file}`),
        chunk,
        stems: [...new Set(contentStems(chunk.text))],
      });
    }
  }
  for (const chunk of loadSchemeChunks(dataPath("schemes.json"))) {
    all.push({
      chunkId: chunk.chunkId,
      sourceFile: "schemes.json",
      contentHash: contentHashOf(chunk, "schemes.json"),
      chunk,
      stems: [...new Set(contentStems(chunk.text))],
    });
  }
  return all;
}

function toDocument(
  storable: StorableChunk,
  embeddingModel: string,
  embedding: number[],
) {
  const { chunk } = storable;
  return {
    chunkId: chunk.chunkId,
    actId: chunk.actId,
    text: chunk.text,
    sectionNumber: chunk.sectionNumber,
    subSection: chunk.subSection,
    parentSectionId: chunk.parentSectionId,
    isDefinition: chunk.isDefinition,
    tokenEstimate: chunk.tokenEstimate,
    actName: chunk.provenance.actName,
    actYear: chunk.provenance.actYear,
    actType: chunk.provenance.actType,
    sourceUrl: chunk.provenance.sourceUrl,
    sourceHash: chunk.provenance.sourceHash,
    retrievalDate: chunk.provenance.retrievalDate,
    governingAuthority: chunk.provenance.governingAuthority,
    schemeUrl: chunk.provenance.schemeUrl,
    amendments: chunk.amendmentHistory.entries,
    amendmentsNoneRecorded: chunk.amendmentHistory.noneRecorded,
    language: "en" as const,
    sourceFile: storable.sourceFile,
    contentHash: storable.contentHash,
    embeddingModel,
    lastEmbeddedAt: Date.now(),
    stems: storable.stems,
    embedding,
  };
}

async function main(): Promise<void> {
  loadEnvLocal(join(__dirname, ".."));
  const dryRun = process.argv.includes("--dry-run");
  const convexUrl =
    process.env.CONVEX_URL ?? process.env.NEXT_PUBLIC_CONVEX_URL;
  const ingestKey = process.env.INGEST_KEY;
  if (!convexUrl) throw new Error("CONVEX_URL / NEXT_PUBLIC_CONVEX_URL is not set");
  if (!ingestKey) throw new Error("INGEST_KEY is not set");

  // 1. Parse + chunk every in-scope act, plus the scheme fact-cards.
  const storables = buildCorpus();

  // 2. Validation gate: no provenance, no answer - only loadable chunks.
  const validation = validateChunks(storables.map((s) => s.chunk));
  if (!structuralOk(validation)) {
    throw new Error(
      `orphaned child chunks: ${validation.orphanedChildren.join(", ")}`,
    );
  }
  const loadableIds = new Set(validation.loadable.map((c) => c.chunkId));
  const loadable = storables.filter((s) => loadableIds.has(s.chunkId));
  console.log(
    `parsed ${storables.length} chunks; loadable ${loadable.length}; ` +
      `flagged ${validation.flagged.length}`,
  );

  // 3. IPC-BNS mapping verified against the official correspondence chart.
  const mapping = loadIpcBnsMapping();
  const chart = JSON.parse(
    readFileSync(dataPath("ground_truth", "ipc_bns_correspondence.json"), "utf8"),
  ) as { pairs: Record<string, string> };
  if (!mapping.verify(chart.pairs)) {
    throw new Error("IPC-BNS mapping does not reproduce the official chart");
  }

  // 4. Coverage report against the ground-truth manifest.
  const ingestedByAct: Record<string, Set<string>> = {};
  for (const chunk of validation.loadable) {
    if (chunk.sectionNumber === undefined) continue;
    (ingestedByAct[chunk.actId] ??= new Set()).add(chunk.sectionNumber);
  }
  const manifest = JSON.parse(
    readFileSync(dataPath("ground_truth", "manifest.json"), "utf8"),
  ) as { acts: Record<string, { official_total_sections: number; in_scope_sections: string[] }> };
  const coverage = buildCoverageReport(ingestedByAct, manifest.acts);
  console.log(
    `coverage: ${(overallCoverage(coverage) * 100).toFixed(1)}% of in-scope ` +
      `target (threshold ${meetsThreshold(coverage) ? "met" : "NOT met"})`,
  );

  // 5. Change detection against what Convex already stores (paged, so the
  // query never exceeds the deployment's per-call read limits).
  const client = new ConvexHttpClient(convexUrl);
  const embedding = embeddingConfig();
  const existing: Array<{
    chunkId: string;
    contentHash: string;
    embeddingModel: string;
  }> = [];
  for (let cursor: string | null = null; ; ) {
    const page: CorpusMetaPage = await client.query(api.documents.corpusMeta, {
      ingestKey,
      cursor,
    });
    existing.push(...page.page);
    if (page.isDone) break;
    cursor = page.continueCursor;
  }
  const existingById = new Map(existing.map((e) => [e.chunkId, e]));
  const currentIds = new Set(loadable.map((s) => s.chunkId));

  const toEmbed = loadable.filter((s) => {
    const stored = existingById.get(s.chunkId);
    return (
      stored === undefined ||
      stored.contentHash !== s.contentHash ||
      stored.embeddingModel !== embedding.model
    );
  });
  const stale = existing
    .filter((e) => !currentIds.has(e.chunkId))
    .map((e) => e.chunkId);
  console.log(
    `stored ${existing.length}; unchanged (skipped) ` +
      `${loadable.length - toEmbed.length}; to embed ${toEmbed.length}; ` +
      `stale to delete ${stale.length}`,
  );
  if (dryRun) {
    console.log("dry run: no embeddings generated, nothing written");
    return;
  }

  // 6. Embed ONLY the changed chunks, in batches.
  for (let start = 0; start < toEmbed.length; start += EMBED_BATCH) {
    const batch = toEmbed.slice(start, start + EMBED_BATCH);
    const vectors = await embedTexts(
      batch.map((s) => s.chunk.text),
      embedding,
    );
    const documents = batch.map((s, i) =>
      toDocument(s, embedding.model, vectors[i]),
    );
    for (let u = 0; u < documents.length; u += UPSERT_BATCH) {
      await client.mutation(api.documents.upsertChunks, {
        ingestKey,
        chunks: documents.slice(u, u + UPSERT_BATCH),
      });
    }
    console.log(
      `embedded + stored ${Math.min(start + EMBED_BATCH, toEmbed.length)}/${toEmbed.length}`,
    );
    // Pace requests to stay within the provider's per-minute quota.
    if (start + EMBED_BATCH < toEmbed.length) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }

  // 7. Delete chunks that disappeared from the sources (never the corpus).
  for (let start = 0; start < stale.length; start += UPSERT_BATCH) {
    await client.mutation(api.documents.removeChunks, {
      ingestKey,
      chunkIds: stale.slice(start, start + UPSERT_BATCH),
    });
  }

  // Final sweep: the stored corpus must be exactly what this run produced.
  let count = 0;
  for (let cursor: string | null = null; ; ) {
    const page: CorpusMetaPage = await client.query(api.documents.corpusMeta, {
      ingestKey,
      cursor,
    });
    count += page.page.length;
    if (page.isDone) break;
    cursor = page.continueCursor;
  }
  console.log(`done: Convex now holds ${count} corpus chunks`);
  if (count !== loadable.length) {
    throw new Error(
      `count mismatch: Convex holds ${count}, expected ${loadable.length}`,
    );
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
