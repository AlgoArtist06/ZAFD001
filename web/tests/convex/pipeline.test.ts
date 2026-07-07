// @vitest-environment node
// The deployed pipeline end to end under convex-test: ask -> scheduled
// runAnswer -> vector search + stems scan over a seeded corpus -> (stubbed)
// LLM -> citation verification -> stream document + persisted turn. This is
// the Convex counterpart of tests/test_fastapi_app.py + test_streaming.py:
// the transport changed, every legal decision must not have.
import { createHash } from "node:crypto";
import { convexTest, type TestConvex } from "convex-test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../convex/_generated/api";
import { type Id } from "../../convex/_generated/dataModel";
import schema from "../../convex/schema";
import { contentStems } from "../../convex/lib/text";
import { isLoadable, type Chunk } from "../../convex/lib/models";
import { buildCorpus } from "../helpers/corpus";
import { hashEmbed } from "../helpers/doubles";
import { modules } from "./modules";

const DIM = 768;

function toRows(chunk: Chunk) {
  return {
    doc: {
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
      sourceFile: "test-fixture",
      contentHash: createHash("sha256").update(chunk.text).digest("hex"),
      embeddingModel: "test-embed",
      lastEmbeddedAt: 0,
      stems: [...new Set(contentStems(chunk.text))],
    },
    embedding: hashEmbed(chunk.text, DIM),
  };
}

async function seedCorpus(t: TestConvex<typeof schema>) {
  const corpus = buildCorpus().filter(isLoadable);
  await t.run(async (ctx) => {
    for (const chunk of corpus) {
      const { doc, embedding } = toRows(chunk);
      const documentId = await ctx.db.insert("documents", doc);
      await ctx.db.insert("embeddings", {
        chunkId: doc.chunkId,
        documentId,
        actType: doc.actType,
        model: doc.embeddingModel,
        embedding,
      });
    }
  });
}

// The stubbed provider: /embeddings answers with the same deterministic hash
// embedding the corpus was seeded with; /chat/completions streams an SSE
// response whose JSON cites the top supplied source - the TemplateGenerator
// contract, over the wire.
function stubProvider() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const payload = JSON.parse(String(init?.body ?? "{}"));
      if (url.endsWith("/embeddings")) {
        return new Response(
          JSON.stringify({
            data: (payload.input as string[]).map((text, index) => ({
              index,
              embedding: hashEmbed(text, DIM),
            })),
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/chat/completions")) {
        const user = JSON.parse(payload.messages[1].content);
        const top = user.sources[0];
        const content = JSON.stringify({
          explanation: top
            ? `In plain language, the law addresses this. (${top.act_name})`
            : "",
          legal_basis: top ? `Legal basis - ${top.verbatim_text}` : "",
          next_step: top ? "Practical next step: read the cited provision." : "",
          citations: top
            ? [{ act_id: top.act_id, section_number: top.section_number }]
            : [],
        });
        const sse =
          content
            .match(/[\s\S]{1,20}/g)!
            .map(
              (piece) =>
                `data: ${JSON.stringify({ choices: [{ delta: { content: piece } }] })}\n`,
            )
            .join("") + "data: [DONE]\n";
        return new Response(sse, { status: 200 });
      }
      throw new Error(`unexpected fetch: ${url}`);
    }),
  );
}

let t: TestConvex<typeof schema>;

beforeEach(() => {
  vi.stubEnv("LLM_API_KEY", "test-llm-key");
  vi.stubEnv("LLM_MODEL", "test-model");
  vi.stubEnv("LLM_BASE_URL", "https://llm.test/v1");
  stubProvider();
  t = convexTest(schema, modules);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function askAndFinish(
  asUser: ReturnType<TestConvex<typeof schema>["withIdentity"]>,
  args: {
    query: string;
    conversationId?: Id<"conversations">;
    language?: string;
  },
) {
  vi.useFakeTimers();
  try {
    const streamId = await asUser.mutation(api.chat.ask, args);
    await t.finishAllScheduledFunctions(vi.runAllTimers);
    return await asUser.query(api.chat.getStream, { streamId });
  } finally {
    vi.useRealTimers();
  }
}

describe("the deployed answer pipeline", () => {
  it("answers a grounded question with verified citations and persists the turn", async () => {
    await seedCorpus(t);
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await asUser.mutation(api.chat.recordConsent, {});
    const conversationId = await asUser.mutation(api.chat.createConversation, {});

    const stream = await askAndFinish(asUser, {
      query: "What is the punishment for theft of movable property?",
      conversationId,
    });

    expect(stream?.done).toBe(true);
    expect(stream?.state).toBe("normal");
    expect(stream?.citations.length).toBeGreaterThan(0);
    expect(stream?.citations[0].reference).toContain("Bharatiya Nyaya Sanhita");
    expect(stream?.citations[0].verbatim).toContain(
      "intending to take dishonestly any movable property",
    );
    expect(stream?.disclaimer).toContain("NALSA / DLSA");

    const turns = await asUser.query(api.chat.getConversationHistory, {
      conversationId,
    });
    expect(turns).toHaveLength(1);
    expect(turns[0].refused).toBe(false);
    expect(turns[0].citations[0].reference).toContain("Section 303");
  });

  it("refuses an out-of-scope question without calling the generator", async () => {
    await seedCorpus(t);
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await asUser.mutation(api.chat.recordConsent, {});

    const stream = await askAndFinish(asUser, {
      query: "What is the best recipe for biryani?",
    });

    expect(stream?.done).toBe(true);
    expect(stream?.state).toBe("refusal");
    expect(stream?.reason).toBe("no_match");
    expect(stream?.citations).toEqual([]);
    const chatCalls = (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url]) => String(url).endsWith("/chat/completions"),
    );
    expect(chatCalls).toEqual([]);
  });

  it("refuses an advice request and redirects to legal aid", async () => {
    await seedCorpus(t);
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await asUser.mutation(api.chat.recordConsent, {});

    const stream = await askAndFinish(asUser, {
      query: "Should I sue my landlord?",
    });

    expect(stream?.state).toBe("refusal");
    expect(stream?.reason).toBe("advice");
    expect(stream?.nextStep).toContain("NALSA / DLSA");
  });

  it("resolves a dependent follow-up against the persisted conversation", async () => {
    await seedCorpus(t);
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await asUser.mutation(api.chat.recordConsent, {});
    const conversationId = await asUser.mutation(api.chat.createConversation, {});

    await askAndFinish(asUser, {
      query: "Someone cheated me by fraud and took my property dishonestly",
      conversationId,
    });
    const stream = await askAndFinish(asUser, {
      query: "What is the punishment for it?",
      conversationId,
    });

    expect(stream?.state).toBe("normal");
    expect(stream?.citations[0].reference).toContain("Section 318");
    const turns = await asUser.query(api.chat.getConversationHistory, {
      conversationId,
    });
    expect(turns[1].resolved).toContain("cheated me by fraud");
  });

  it("blocks asking without consent (the 403 gate)", async () => {
    await seedCorpus(t);
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await expect(
      asUser.mutation(api.chat.ask, { query: "what is theft" }),
    ).rejects.toThrow("Consent to the privacy notice is required.");
  });

  it("surfaces a missing LLM configuration as a service error, never an answer (ADR 0010)", async () => {
    vi.stubEnv("LLM_API_KEY", "");
    await seedCorpus(t);
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await asUser.mutation(api.chat.recordConsent, {});

    const stream = await askAndFinish(asUser, {
      query: "What is the punishment for theft of movable property?",
    });

    expect(stream?.done).toBe(true);
    expect(stream?.state).toBe("error");
    expect(stream?.detail).toContain("ConfigurationError");
    expect(stream?.citations).toEqual([]);
  });

  it("turns a draft with only unverifiable citations into a refusal", async () => {
    await seedCorpus(t);
    // Re-stub generation to cite a fabricated section.
    const baseFetch = fetch as ReturnType<typeof vi.fn>;
    baseFetch.mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const payload = JSON.parse(String(init?.body ?? "{}"));
        if (url.endsWith("/embeddings")) {
          return new Response(
            JSON.stringify({
              data: (payload.input as string[]).map((text, index) => ({
                index,
                embedding: hashEmbed(text, DIM),
              })),
            }),
            { status: 200 },
          );
        }
        const content = JSON.stringify({
          explanation: "A confident but fabricated claim.",
          legal_basis: "Made-up basis.",
          next_step: "Do something.",
          citations: [{ act_id: "bns", section_number: "999" }],
        });
        const sse =
          `data: ${JSON.stringify({ choices: [{ delta: { content } }] })}\n` +
          "data: [DONE]\n";
        return new Response(sse, { status: 200 });
      },
    );
    const asUser = t.withIdentity({ subject: "citizen-1" });
    await asUser.mutation(api.chat.recordConsent, {});
    const conversationId = await asUser.mutation(api.chat.createConversation, {});

    const stream = await askAndFinish(asUser, {
      query: "What is the punishment for theft of movable property?",
      conversationId,
    });

    expect(stream?.state).toBe("refusal");
    expect(stream?.reason).toBe("citations_unverified");
    expect(stream?.citations).toEqual([]);
    // The refusal is persisted as a refusal, not as the fabricated draft.
    const turns = await asUser.query(api.chat.getConversationHistory, {
      conversationId,
    });
    expect(turns[0].refused).toBe(true);
  });
});
