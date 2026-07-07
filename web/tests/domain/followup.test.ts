// Ports tests/test_followup_memory.py: dependent follow-ups resolve against
// the Conversation's bounded recent context, context never leaks across
// Conversations, and the user's own words stay on the answer.
import { beforeAll, describe, expect, it } from "vitest";

import { isFollowup, rewriteFollowup } from "../../convex/lib/followup";
import { type Chunk } from "../../convex/lib/models";
import { buildCorpus } from "../helpers/corpus";
import { offlineAnswer, offlineConversation } from "../helpers/doubles";

let corpus: Chunk[];
beforeAll(() => {
  corpus = buildCorpus();
});

describe("follow-up detection and rewriting", () => {
  it("detects referential follow-ups", () => {
    expect(isFollowup("what is the punishment for it?")).toBe(true);
    expect(isFollowup("what is theft?")).toBe(false);
  });

  it("prefixes the bounded recent context", () => {
    expect(rewriteFollowup("what about it?", ["what is theft"])).toBe(
      "what is theft what about it?",
    );
    expect(rewriteFollowup("what is cheating?", ["what is theft"])).toBe(
      "what is cheating?",
    );
  });
});

describe("conversation memory", () => {
  it("answers a dependent follow-up using the prior turn", async () => {
    const conversation = offlineConversation(corpus);
    await conversation.ask("Someone cheated me by fraud and took my property dishonestly");
    const result = await conversation.ask("What is the punishment for it?");
    expect(result.refused).toBe(false);
    expect(result.citations.some((c) => c.sectionNumber === "318")).toBe(true);
  });

  it("refuses the same follow-up without conversation context", async () => {
    const result = await offlineAnswer(corpus, "What is the punishment for it?");
    expect(result.refused).toBe(true);
  });

  it("does not share context across conversations", async () => {
    const first = offlineConversation(corpus);
    await first.ask("Someone cheated me by fraud and took my property dishonestly");
    const second = offlineConversation(corpus);
    const result = await second.ask("What is the punishment for it?");
    expect(result.refused).toBe(true);
  });

  it("leaves a self-contained turn unaffected by memory", async () => {
    const conversation = offlineConversation(corpus);
    await conversation.ask("What protects my life and personal liberty?");
    const result = await conversation.ask(
      "What is the punishment for theft of movable property?",
    );
    expect(result.refused).toBe(false);
    expect(result.citations.some((c) => c.sectionNumber === "303")).toBe(true);
  });

  it("keeps the user's own words on the answer, not the rewrite", async () => {
    const conversation = offlineConversation(corpus);
    await conversation.ask("Someone cheated me by fraud and took my property dishonestly");
    const result = await conversation.ask("What is the punishment for it?");
    expect(result.query).toBe("What is the punishment for it?");
  });
});
