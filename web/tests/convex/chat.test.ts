// @vitest-environment edge-runtime
// Ports the persistence-seam semantics of tests/test_store.py,
// test_consent_store.py, and test_store_privacy.py: per-user ownership
// scoping, sidebar summaries, turn ordering, deletion, erasure, and consent.
import { convexTest } from "convex-test";
import { describe, expect, it } from "vitest";

import { api } from "../../convex/_generated/api";
import schema from "../../convex/schema";
import { modules } from "./modules";

const CITATION = {
  reference: "Bharatiya Nyaya Sanhita (2023), Section 303",
  verbatim: "Whoever intending to take dishonestly any movable property...",
  url: "https://www.indiacode.nic.in/bns",
};

function turnArgs(query: string) {
  return {
    query,
    resolved: query,
    answer: `answer to ${query}`,
    refused: false,
    citations: [CITATION],
  };
}

function signedIn(userId: string) {
  return convexTest(schema, modules).withIdentity({ subject: userId });
}

describe("conversation persistence", () => {
  it("creates, appends, and reads back turns oldest first", async () => {
    const asUser = signedIn("user-1");
    const id = await asUser.mutation(api.chat.createConversation, {});
    await asUser.mutation(api.chat.saveMessage, {
      conversationId: id,
      ...turnArgs("what is theft"),
    });
    await asUser.mutation(api.chat.saveMessage, {
      conversationId: id,
      ...turnArgs("what is the punishment for it"),
    });
    const turns = await asUser.query(api.chat.getConversationHistory, {
      conversationId: id,
    });
    expect(turns.map((t) => t.query)).toEqual([
      "what is theft",
      "what is the punishment for it",
    ]);
    // Citations persist in their wire form, so reloads show verbatim text.
    expect(turns[0].citations).toEqual([CITATION]);
  });

  it("lists summaries newest first with first-question titles", async () => {
    const asUser = signedIn("user-1");
    const first = await asUser.mutation(api.chat.createConversation, {});
    const second = await asUser.mutation(api.chat.createConversation, {});
    await asUser.mutation(api.chat.saveMessage, {
      conversationId: first,
      ...turnArgs("what is theft"),
    });
    const summaries = await asUser.query(api.chat.listConversations, {});
    expect(summaries.map((s) => s.id)).toEqual([second, first]);
    expect(summaries.map((s) => s.title)).toEqual(["New chat", "what is theft"]);
  });

  it("scopes every read and write to the owner", async () => {
    const t = convexTest(schema, modules);
    const asOwner = t.withIdentity({ subject: "owner" });
    const asOther = t.withIdentity({ subject: "other" });
    const id = await asOwner.mutation(api.chat.createConversation, {});
    await asOwner.mutation(api.chat.saveMessage, {
      conversationId: id,
      ...turnArgs("private question"),
    });

    await expect(
      asOther.query(api.chat.getConversationHistory, { conversationId: id }),
    ).rejects.toThrow("Conversation not found.");
    await expect(
      asOther.mutation(api.chat.saveMessage, {
        conversationId: id,
        ...turnArgs("intruding"),
      }),
    ).rejects.toThrow("Conversation not found.");
    await expect(
      asOther.mutation(api.chat.deleteConversation, { conversationId: id }),
    ).rejects.toThrow("Conversation not found.");
    expect(await asOther.query(api.chat.listConversations, {})).toEqual([]);
    // The owner still sees everything.
    const turns = await asOwner.query(api.chat.getConversationHistory, {
      conversationId: id,
    });
    expect(turns).toHaveLength(1);
  });

  it("rejects unauthenticated access outright", async () => {
    const t = convexTest(schema, modules);
    await expect(t.mutation(api.chat.createConversation, {})).rejects.toThrow(
      "Sign in to use the assistant.",
    );
    await expect(t.query(api.chat.listConversations, {})).rejects.toThrow(
      "Sign in to use the assistant.",
    );
  });

  it("deletes a conversation and its turns", async () => {
    const asUser = signedIn("user-1");
    const id = await asUser.mutation(api.chat.createConversation, {});
    await asUser.mutation(api.chat.saveMessage, {
      conversationId: id,
      ...turnArgs("what is theft"),
    });
    await asUser.mutation(api.chat.deleteConversation, { conversationId: id });
    expect(await asUser.query(api.chat.listConversations, {})).toEqual([]);
    await expect(
      asUser.query(api.chat.getConversationHistory, { conversationId: id }),
    ).rejects.toThrow("Conversation not found.");
  });

  it("erases all of one user's data and nobody else's", async () => {
    const t = convexTest(schema, modules);
    const asLeaving = t.withIdentity({ subject: "leaving" });
    const asStaying = t.withIdentity({ subject: "staying" });
    for (const user of [asLeaving, asStaying]) {
      const id = await user.mutation(api.chat.createConversation, {});
      await user.mutation(api.chat.saveMessage, {
        conversationId: id,
        ...turnArgs("a question"),
      });
      await user.mutation(api.chat.recordConsent, {});
    }

    await asLeaving.mutation(api.chat.eraseAllUserData, {});

    expect(await asLeaving.query(api.chat.listConversations, {})).toEqual([]);
    expect(
      (await asLeaving.query(api.chat.consentStatus, {})).consented,
    ).toBe(false);
    expect(await asStaying.query(api.chat.listConversations, {})).toHaveLength(1);
    expect(
      (await asStaying.query(api.chat.consentStatus, {})).consented,
    ).toBe(true);
  });
});

describe("consent ledger", () => {
  it("starts unconsented and records consent to the current notice", async () => {
    const asUser = signedIn("user-1");
    expect(await asUser.query(api.chat.consentStatus, {})).toMatchObject({
      consented: false,
      noticeVersion: null,
    });
    const record = await asUser.mutation(api.chat.recordConsent, {});
    expect(record.userId).toBe("user-1");
    const status = await asUser.query(api.chat.consentStatus, {});
    expect(status.consented).toBe(true);
    expect(status.noticeVersion).toBe(status.currentVersion);
  });

  it("re-consent replaces the record instead of duplicating it", async () => {
    const asUser = signedIn("user-1");
    await asUser.mutation(api.chat.recordConsent, {});
    await asUser.mutation(api.chat.recordConsent, {});
    const status = await asUser.query(api.chat.consentStatus, {});
    expect(status.consented).toBe(true);
  });

  it("serves the privacy notice with its version", async () => {
    const t = convexTest(schema, modules);
    const notice = await t.query(api.chat.privacyNotice, {});
    expect(notice.version).toBeTruthy();
    expect(notice.notice).toContain("third-party large language model");
    expect(notice.notice).toContain("right to erasure");
  });
});
