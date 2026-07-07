// Conversations, turns, and consent behind Convex functions - the ChatShell
// (rag/services/chat.py) and its FastAPI routes, re-homed.
//
// Every read and write is scoped by the authenticated Clerk subject, so one
// user can never list, load, append to, or delete another's Conversations -
// the same ownership rule the Python store enforced in its WHERE clauses.
// Phase 7 adds the answerQuestion pipeline action on top of these seams.
import { ConvexError, v } from "convex/values";
import {
  action,
  internalMutation,
  mutation,
  query,
  type MutationCtx,
  type QueryCtx,
} from "./_generated/server";
import { internal } from "./_generated/api";
import { type Doc, type Id } from "./_generated/dataModel";
import { citationValidator, streamFieldsValidator } from "./schema";
import { CONTEXT_TURNS, rewriteFollowup } from "./lib/followup";
import { NOTICE_VERSION, PRIVACY_NOTICE } from "./lib/privacy";

// The backend's gate: no verified identity, no work done. Mirrors the 401 the
// FastAPI dependency raised before touching any seam.
export async function requireUser(ctx: QueryCtx | MutationCtx): Promise<string> {
  const identity = await ctx.auth.getUserIdentity();
  if (identity === null) {
    throw new ConvexError("Sign in to use the assistant.");
  }
  return identity.subject;
}

// Load a Conversation only for the user who owns it; an unknown id and a
// foreign id are indistinguishable to the caller (the Python 404 behavior).
async function requireOwned(
  ctx: QueryCtx | MutationCtx,
  userId: string,
  conversationId: Id<"conversations">,
): Promise<Doc<"conversations">> {
  const conversation = await ctx.db.get(conversationId);
  if (conversation === null || conversation.userId !== userId) {
    throw new ConvexError("Conversation not found.");
  }
  return conversation;
}

// Who does Convex think is signed in? Null when the browser carries no (or an
// invalid) Clerk session.
export const viewer = query({
  args: {},
  handler: async (ctx) => {
    const identity = await ctx.auth.getUserIdentity();
    return identity ? { userId: identity.subject } : null;
  },
});

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

export const createConversation = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await requireUser(ctx);
    return await ctx.db.insert("conversations", { userId });
  },
});

// The sidebar's view: id and title only, newest first. The title is the first
// turn's query, so listing never loads whole histories.
export const listConversations = query({
  args: {},
  handler: async (ctx) => {
    const userId = await requireUser(ctx);
    const conversations = await ctx.db
      .query("conversations")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .order("desc")
      .collect();
    return await Promise.all(
      conversations.map(async (conversation) => {
        const first = await ctx.db
          .query("turns")
          .withIndex("by_conversation", (q) =>
            q.eq("conversationId", conversation._id),
          )
          .first();
        return { id: conversation._id, title: first?.query ?? "New chat" };
      }),
    );
  },
});

// The turns of one owned Conversation, oldest first.
export const getConversationHistory = query({
  args: { conversationId: v.id("conversations") },
  handler: async (ctx, { conversationId }) => {
    const userId = await requireUser(ctx);
    await requireOwned(ctx, userId, conversationId);
    const turns = await ctx.db
      .query("turns")
      .withIndex("by_conversation", (q) =>
        q.eq("conversationId", conversationId),
      )
      .collect();
    return turns.map((turn) => ({
      query: turn.query,
      resolved: turn.resolved,
      answer: turn.answer,
      refused: turn.refused,
      citations: turn.citations,
    }));
  },
});

// Record one completed turn: the user's words, the standalone rewrite, the
// answer, and the verified Citations in their wire form.
export const saveMessage = mutation({
  args: {
    conversationId: v.id("conversations"),
    query: v.string(),
    resolved: v.string(),
    answer: v.string(),
    refused: v.boolean(),
    citations: v.array(citationValidator),
  },
  handler: async (ctx, { conversationId, ...turn }) => {
    const userId = await requireUser(ctx);
    await requireOwned(ctx, userId, conversationId);
    await ctx.db.insert("turns", { conversationId, ...turn });
  },
});

export const deleteConversation = mutation({
  args: { conversationId: v.id("conversations") },
  handler: async (ctx, { conversationId }) => {
    const userId = await requireUser(ctx);
    await requireOwned(ctx, userId, conversationId);
    const turns = await ctx.db
      .query("turns")
      .withIndex("by_conversation", (q) =>
        q.eq("conversationId", conversationId),
      )
      .collect();
    for (const turn of turns) {
      await ctx.db.delete(turn._id);
    }
    await ctx.db.delete(conversationId);
  },
});

// Purge every Conversation, stream row, and the consent record the user owns
// - the data half of the right to erasure.
async function eraseUserData(ctx: MutationCtx, userId: string): Promise<void> {
  const conversations = await ctx.db
    .query("conversations")
    .withIndex("by_user", (q) => q.eq("userId", userId))
    .collect();
  for (const conversation of conversations) {
    const turns = await ctx.db
      .query("turns")
      .withIndex("by_conversation", (q) =>
        q.eq("conversationId", conversation._id),
      )
      .collect();
    for (const turn of turns) {
      await ctx.db.delete(turn._id);
    }
    await ctx.db.delete(conversation._id);
  }
  const streams = await ctx.db
    .query("streams")
    .withIndex("by_user", (q) => q.eq("userId", userId))
    .collect();
  for (const stream of streams) {
    await ctx.db.delete(stream._id);
  }
  const consent = await ctx.db
    .query("consents")
    .withIndex("by_user", (q) => q.eq("userId", userId))
    .unique();
  if (consent) {
    await ctx.db.delete(consent._id);
  }
}

export const eraseAllUserData = mutation({
  args: {},
  handler: async (ctx) => {
    await eraseUserData(ctx, await requireUser(ctx));
  },
});

// ---------------------------------------------------------------------------
// Consent (a legal fact under the DPDP Act - durable, per user)
// ---------------------------------------------------------------------------

// The notice shown at signup, including the third-party-LLM disclosure.
export const privacyNotice = query({
  args: {},
  handler: async () => ({ version: NOTICE_VERSION, notice: PRIVACY_NOTICE }),
});

// Whether the signed-in user has already consented, and to which version -
// lets the consent gate skip itself for a returning user.
export const consentStatus = query({
  args: {},
  handler: async (ctx) => {
    const userId = await requireUser(ctx);
    const record = await ctx.db
      .query("consents")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    return {
      consented: record !== null,
      noticeVersion: record?.noticeVersion ?? null,
      currentVersion: NOTICE_VERSION,
    };
  },
});

// ---------------------------------------------------------------------------
// Asking a question (the pipeline entry; the heavy lifting runs in
// internal.llm.runAnswer, streaming into a `streams` document)
// ---------------------------------------------------------------------------

// One question in. Authenticates, checks consent, resolves a dependent
// follow-up against the Conversation's persisted turns (or the supplied
// context for an unpersisted chat), opens a stream document, and schedules
// the pipeline. Returns the stream id the client subscribes to.
export const ask = mutation({
  args: {
    query: v.string(),
    conversationId: v.optional(v.id("conversations")),
    language: v.optional(v.string()),
    context: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const userId = await requireUser(ctx);
    // An answer is served only once the user consented to the third-party
    // LLM processing - the same 403 gate the FastAPI route enforced.
    const consent = await ctx.db
      .query("consents")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    if (consent === null) {
      throw new ConvexError("Consent to the privacy notice is required.");
    }

    // Resolve a dependent follow-up against the Conversation's recent turns
    // before anything streams, so an unknown Conversation still fails
    // cleanly. Memory is bounded and rebuilt from the persisted turns.
    let resolved: string;
    if (args.conversationId !== undefined) {
      await requireOwned(ctx, userId, args.conversationId);
      const turns = await ctx.db
        .query("turns")
        .withIndex("by_conversation", (q) =>
          q.eq("conversationId", args.conversationId!),
        )
        .collect();
      const recent = turns.map((t) => t.resolved).slice(-CONTEXT_TURNS);
      resolved = rewriteFollowup(args.query, recent);
    } else {
      resolved = rewriteFollowup(
        args.query,
        (args.context ?? []).slice(-CONTEXT_TURNS),
      );
    }

    // Sweep this user's finished stream rows: the client keeps completed
    // answers in its own state, so old rows are garbage once a new ask lands.
    const stale = await ctx.db
      .query("streams")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    for (const row of stale) {
      if (row.done) await ctx.db.delete(row._id);
    }

    const language = args.language ?? "en";
    const streamId = await ctx.db.insert("streams", {
      userId,
      conversationId: args.conversationId,
      done: false,
      state: "normal",
      explanation: "",
      citations: [],
      language,
    });
    await ctx.scheduler.runAfter(0, internal.llm.runAnswer, {
      streamId,
      userId,
      conversationId: args.conversationId,
      query: args.query,
      resolved,
      language,
    });
    return streamId;
  },
});

// The in-flight (or finished) answer the client renders reactively - the
// replacement for reading the NDJSON stream.
export const getStream = query({
  args: { streamId: v.id("streams") },
  handler: async (ctx, { streamId }) => {
    const userId = await requireUser(ctx);
    const stream = await ctx.db.get(streamId);
    if (stream === null || stream.userId !== userId) return null;
    return stream;
  },
});

// Progressive updates from the pipeline (cumulative explanation, meta).
export const updateStream = internalMutation({
  args: { streamId: v.id("streams"), fields: streamFieldsValidator },
  handler: async (ctx, { streamId, fields }) => {
    const stream = await ctx.db.get(streamId);
    if (stream === null) return;
    await ctx.db.patch(streamId, fields);
  },
});

// The final, authoritative answer state - replaces whatever streamed.
export const finishStream = internalMutation({
  args: { streamId: v.id("streams"), fields: streamFieldsValidator },
  handler: async (ctx, { streamId, fields }) => {
    const stream = await ctx.db.get(streamId);
    if (stream === null) return;
    await ctx.db.replace(streamId, {
      userId: stream.userId,
      conversationId: stream.conversationId,
      explanation: "",
      citations: [],
      state: "normal",
      ...fields,
      done: true,
    });
  },
});

// Record one completed turn from the pipeline. A turn is persisted only once
// its answer is complete - service errors never reach here.
export const persistTurn = internalMutation({
  args: {
    userId: v.string(),
    conversationId: v.id("conversations"),
    query: v.string(),
    resolved: v.string(),
    answer: v.string(),
    refused: v.boolean(),
    citations: v.array(citationValidator),
  },
  handler: async (ctx, { userId, conversationId, ...turn }) => {
    const conversation = await ctx.db.get(conversationId);
    if (conversation === null || conversation.userId !== userId) return;
    await ctx.db.insert("turns", { conversationId, ...turn });
  },
});

// Erase the account entirely: all Convex data, then the Clerk user (the
// right to erasure). Clerk's API sits behind the deployment's secret key;
// a 404 means already gone, which is success for erasure.
export const deleteAccount = action({
  args: {},
  handler: async (ctx) => {
    const identity = await ctx.auth.getUserIdentity();
    if (identity === null) {
      throw new ConvexError("Sign in to use the assistant.");
    }
    await ctx.runMutation(internal.chat.eraseAllUserDataInternal, {
      userId: identity.subject,
    });
    const secretKey = process.env.CLERK_SECRET_KEY;
    if (!secretKey) return;
    const url = `https://api.clerk.com/v1/users/${identity.subject}`;
    for (let attempt = 1; attempt <= 2; attempt++) {
      let response: Response;
      try {
        response = await fetch(url, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${secretKey}` },
        });
      } catch (error) {
        if (attempt === 2) throw error;
        continue;
      }
      if (response.status === 404) return; // already gone is success
      if (response.status >= 500 && attempt === 1) continue;
      if (!response.ok) {
        throw new Error(`clerk delete_account failed: ${response.status}`);
      }
      return;
    }
  },
});

// The erasure worker behind deleteAccount (actions cannot touch the db).
export const eraseAllUserDataInternal = internalMutation({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    await eraseUserData(ctx, userId);
  },
});

// Record, server-side, the signed-in user's explicit consent to the notice.
export const recordConsent = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await requireUser(ctx);
    const existing = await ctx.db
      .query("consents")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    if (existing) {
      await ctx.db.delete(existing._id);
    }
    await ctx.db.insert("consents", {
      userId,
      noticeVersion: NOTICE_VERSION,
      consentedAt: new Date().toISOString(),
    });
    return { userId, noticeVersion: NOTICE_VERSION };
  },
});
