"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "convex/react";

import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";
import { emptyAnswer, type StructuredAnswer } from "@/lib/structured-answer";

export type Turn =
  | { role: "user"; text: string }
  | { role: "assistant"; answer: StructuredAnswer };

export type Conversation = {
  id: number;
  turns: Turn[];
  storageId?: Id<"conversations">;
  title?: string;
  loaded?: boolean;
};

export function conversationTitle(conversation: Conversation): string {
  const first = conversation.turns.find((turn) => turn.role === "user");
  return first?.text ?? conversation.title ?? "New chat";
}

function contextOf(conversation: Conversation): string[] {
  return conversation.turns
    .filter((turn): turn is Extract<Turn, { role: "user" }> => turn.role === "user")
    .map((turn) => turn.text);
}

function streamAnswer(stream: NonNullable<ReturnType<typeof useStream>>): StructuredAnswer {
  return {
    state: stream.state,
    explanation: stream.explanation,
    citations: stream.citations,
    language: stream.language,
    reason: stream.reason as StructuredAnswer["reason"],
    highStakesNotice: stream.highStakesNotice,
    note: stream.note,
    nextStep: stream.nextStep,
    disclaimer: stream.disclaimer,
    detail: stream.detail,
  };
}

function useStream(streamId: Id<"streams"> | null) {
  return useQuery(api.chat.getStream, streamId ? { streamId } : "skip");
}

export function useChat() {
  const listed = useQuery(api.chat.listConversations);
  const createConversation = useMutation(api.chat.createConversation);
  const removeStoredConversation = useMutation(api.chat.deleteConversation);
  const askQuestion = useMutation(api.chat.ask);
  const [conversations, setConversations] = useState<Conversation[]>([{ id: 1, turns: [] }]);
  const [activeId, setActiveId] = useState(1);
  const [nextId, setNextId] = useState(2);
  const [question, setQuestion] = useState("");
  // The in-flight answer and the local conversation it belongs to, bound
  // together so a user switching conversations mid-stream can never have one
  // conversation's answer written into another.
  const [pending, setPending] = useState<{
    streamId: Id<"streams">;
    conversationId: number;
  } | null>(null);
  const stream = useStream(pending?.streamId ?? null);
  const active = conversations.find((conversation) => conversation.id === activeId)!;
  const history = useQuery(
    api.chat.getConversationHistory,
    active?.storageId && !active.loaded ? { conversationId: active.storageId } : "skip",
  );

  useEffect(() => {
    if (!listed?.length) return;
    setConversations((current) => {
      const known = new Set(current.flatMap((item) => item.storageId ? [item.storageId] : []));
      const added = listed
        .filter((item) => !known.has(item.id))
        .map((item, index) => ({ id: 1000 + index, turns: [], storageId: item.id, title: item.title }));
      return added.length ? [...current, ...added] : current;
    });
    setNextId((value) => Math.max(value, 1000 + listed.length));
  }, [listed]);

  useEffect(() => {
    if (!active?.storageId || active.loaded || history === undefined) return;
    const turns: Turn[] = history.flatMap((turn) => [
      { role: "user" as const, text: turn.query },
      {
        role: "assistant" as const,
        answer: {
          state: turn.refused ? "refusal" as const : "normal" as const,
          explanation: turn.answer,
          citations: turn.citations,
        },
      },
    ]);
    setConversations((current) => current.map((item) =>
      item.id === activeId ? { ...item, turns, loaded: true } : item,
    ));
  }, [active?.loaded, active?.storageId, activeId, history]);

  useEffect(() => {
    if (!pending) return;
    // A missing row (swept, or the pipeline died before finishing) must not
    // block the composer forever: treat it as terminal.
    if (stream === null) {
      setPending(null);
      return;
    }
    if (stream === undefined) return;
    setConversations((current) => current.map((conversation) => {
      if (conversation.id !== pending.conversationId) return conversation;
      const turns = [...conversation.turns];
      const last = turns.at(-1);
      if (last?.role === "assistant") turns[turns.length - 1] = { role: "assistant", answer: streamAnswer(stream) };
      return { ...conversation, turns };
    }));
    if (stream.done) setPending(null);
  }, [pending, stream]);

  function newChat() {
    const id = nextId;
    setNextId(id + 1);
    setConversations((current) => [...current, { id, turns: [] }]);
    setActiveId(id);
    setQuestion("");
  }

  async function deleteConversation(conversation: Conversation) {
    if (conversation.storageId) await removeStoredConversation({ conversationId: conversation.storageId });
    const remaining = conversations.filter((item) => item.id !== conversation.id);
    if (remaining.length) {
      setConversations(remaining);
      if (activeId === conversation.id) setActiveId(remaining[0].id);
    } else {
      setConversations([{ id: nextId, turns: [] }]);
      setActiveId(nextId);
      setNextId(nextId + 1);
    }
  }

  async function ask() {
    const query = question.trim();
    if (!query || pending) return;
    const context = contextOf(active);
    const asking = activeId;
    setQuestion("");
    setConversations((current) => current.map((conversation) =>
      conversation.id === activeId
        ? { ...conversation, turns: [...conversation.turns, { role: "user", text: query }, { role: "assistant", answer: emptyAnswer() }] }
        : conversation,
    ));
    try {
      let conversationId = active.storageId;
      if (!conversationId) {
        conversationId = await createConversation({});
        setConversations((current) => current.map((conversation) =>
          conversation.id === activeId ? { ...conversation, storageId: conversationId, loaded: true } : conversation,
        ));
      }
      setPending({
        streamId: await askQuestion({ query, context, conversationId }),
        conversationId: asking,
      });
    } catch (cause) {
      setConversations((current) => current.map((conversation) => {
        if (conversation.id !== asking) return conversation;
        const turns = [...conversation.turns];
        turns[turns.length - 1] = { role: "assistant", answer: {
          state: "error",
          explanation: "The question was not answered because the assistant backend could not be reached.",
          detail: cause instanceof Error ? cause.message : String(cause),
          citations: [],
        } };
        return { ...conversation, turns };
      }));
    }
  }

  return {
    conversations,
    active,
    activeId,
    setActiveId,
    question,
    setQuestion,
    streaming: pending !== null,
    ask,
    newChat,
    deleteConversation,
  };
}
