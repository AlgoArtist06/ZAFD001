"use client";

import { useEffect, useState } from "react";

import {
  applyFrame,
  emptyAnswer,
  readNdjson,
  type StructuredAnswer,
} from "@/lib/answer-stream";
import { apiUrl } from "@/lib/api";

// A turn is either the user's question (plain text) or the assistant's Grounded
// Answer, rendered in its structured, safe form from the seam's signals.
export type Turn =
  | { role: "user"; text: string }
  | { role: "assistant"; answer: StructuredAnswer };

export type Conversation = {
  id: number;
  turns: Turn[];
  storageId?: string;
  // The server-side title of a hydrated Conversation whose turns are not
  // loaded yet; once turns exist the first user turn is the title.
  title?: string;
  // Whether a persisted Conversation's turns have been fetched.
  loaded?: boolean;
};

// The label shown for a Conversation in the sidebar: its first question, or a
// placeholder while it is still empty.
export function conversationTitle(conversation: Conversation): string {
  for (const turn of conversation.turns) {
    if (turn.role === "user") return turn.text;
  }
  return conversation.title ?? "New chat";
}

// The prior user turns of a Conversation, oldest first - the context the answer
// seam rewrites a dependent follow-up against. A fresh Conversation has none, so
// nothing carries across from a previous one.
function contextOf(conversation: Conversation): string[] {
  return conversation.turns
    .filter((turn): turn is Extract<Turn, { role: "user" }> => turn.role === "user")
    .map((turn) => turn.text);
}

// Apply a structured-answer update to the Conversation's latest assistant turn,
// which is the one currently streaming its parts in.
function mapLastAssistant(
  turns: Turn[],
  apply: (answer: StructuredAnswer) => StructuredAnswer,
): Turn[] {
  const next = [...turns];
  const last = next[next.length - 1];
  if (last && last.role === "assistant") {
    next[next.length - 1] = { role: "assistant", answer: apply(last.answer) };
  }
  return next;
}

// A backend response that carried no answer, tagged with its HTTP status so the
// error path can tell an expired session or missing consent from an outage.
class RequestFailed extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type UseChatOptions = {
  getToken: () => Promise<string | null>;
};

// All Conversation state and backend traffic for the chat shell: the local
// Conversation list, the active one, streaming an answer into it, and deletion.
// Account erasure lives on the dedicated settings screen, not here. Presentation
// components consume this and stay markup-only.
export function useChat({ getToken }: UseChatOptions) {
  const [conversations, setConversations] = useState<Conversation[]>([
    { id: 1, turns: [] },
  ]);
  const [activeId, setActiveId] = useState(1);
  const [nextId, setNextId] = useState(2);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);

  const active = conversations.find((c) => c.id === activeId)!;

  // Hydrate the sidebar from the server once: a signed-in user's persisted
  // Conversations reappear after a reload or on another device. The fresh
  // empty Conversation stays first and active; history lists below it.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const headers = await authHeaders();
        if (!headers.Authorization) return;
        const response = await fetch(apiUrl("/api/conversations"), { headers });
        if (!response.ok) return;
        const data = await response.json();
        const listed: { id: string; title: string }[] =
          data?.conversations ?? [];
        if (cancelled || listed.length === 0) return;
        setConversations((prev) => {
          const known = new Set(
            prev.map((c) => c.storageId).filter(Boolean) as string[],
          );
          const hydrated = listed
            .filter((record) => !known.has(record.id))
            .map((record, index) => ({
              id: 1000 + index,
              turns: [],
              storageId: record.id,
              title: record.title,
            }));
          return [...prev, ...hydrated];
        });
        setNextId((value) => Math.max(value, 1000 + listed.length));
      } catch {
        // Offline or incompatible backend: the shell still works locally.
      }
    })();
    return () => {
      cancelled = true;
    };
    // Runs once per mount; getToken is stable for the session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Selecting a hydrated Conversation loads its persisted turns on demand.
  async function selectConversation(id: number) {
    setActiveId(id);
    const conversation = conversations.find((c) => c.id === id);
    if (!conversation?.storageId || conversation.loaded || conversation.turns.length) {
      return;
    }
    try {
      const response = await fetch(
        apiUrl(`/api/conversations/${conversation.storageId}`),
        { headers: await authHeaders() },
      );
      if (!response.ok) return;
      const data = await response.json();
      const turns: Turn[] = (data?.turns ?? []).flatMap(
        (turn: {
          query: string;
          answer: string;
          refused: boolean;
          citations?: { reference: string; verbatim: string; url: string }[];
        }) => [
          { role: "user" as const, text: turn.query },
          {
            role: "assistant" as const,
            answer: {
              // Persisted turns store the flat rendered answer plus the
              // verified Citations, so a reload shows the same verbatim
              // statutory text the live answer streamed.
              state: turn.refused ? ("refusal" as const) : ("normal" as const),
              explanation: turn.answer,
              citations: turn.citations ?? [],
            },
          },
        ],
      );
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, turns, loaded: true } : c)),
      );
    } catch {
      // History stays unloaded; asking still works.
    }
  }

  function updateActive(update: (turns: Turn[]) => Turn[]) {
    setConversations((prev) =>
      prev.map((c) => (c.id === activeId ? { ...c, turns: update(c.turns) } : c)),
    );
  }

  function newChat() {
    const id = nextId;
    setNextId(id + 1);
    setConversations((prev) => [...prev, { id, turns: [] }]);
    setActiveId(id);
    setQuestion("");
  }

  async function authHeaders(): Promise<Record<string, string>> {
    const token = await getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function deleteConversation(conversation: Conversation) {
    if (conversation.storageId) {
      const response = await fetch(
        apiUrl(`/api/conversations/${conversation.storageId}`),
        { method: "DELETE", headers: await authHeaders() },
      );
      if (!response.ok) return;
    }
    removeConversation(conversation);
  }

  function removeConversation(conversation: Conversation) {
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
    if (!query || streaming) return;

    // The context is captured from the active Conversation before this turn is
    // appended, so the follow-up is resolved against the prior turns only.
    const context = contextOf(active);

    setQuestion("");
    setStreaming(true);
    updateActive((turns) => [
      ...turns,
      { role: "user", text: query },
      { role: "assistant", answer: emptyAnswer() },
    ]);

    function applyToActiveAnswer(
      apply: (answer: StructuredAnswer) => StructuredAnswer,
    ) {
      updateActive((turns) => mapLastAssistant(turns, apply));
    }

    try {
      // The session token attributes this request to the signed-in user, so the
      // backend scopes the Conversation to them and never to another user.
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(await authHeaders()),
      };

      let storageId = active.storageId;
      if (headers.Authorization && !storageId) {
        const created = await fetch(apiUrl("/api/conversations"), {
          method: "POST",
          headers,
        });
        if (!created.ok)
          throw new RequestFailed(created.status, `Request failed (${created.status})`);
        storageId = String((await created.json()).id);
        setConversations((prev) =>
          prev.map((conversation) =>
            conversation.id === active.id
              ? { ...conversation, storageId }
              : conversation,
          ),
        );
      }

      const response = await fetch(apiUrl("/api/answer"), {
        method: "POST",
        headers,
        body: JSON.stringify({
          query,
          context,
          conversation_id: storageId,
        }),
      });
      if (!response.ok || !response.body) {
        throw new RequestFailed(
          response.status,
          `The backend answered ${response.status} ${response.statusText}`.trim(),
        );
      }
      // The seam streams its structured signals as NDJSON, one part per line, so
      // each part is rendered safely in place as it arrives.
      await readNdjson(response.body, (line) =>
        applyToActiveAnswer((answer) => applyFrame(answer, line)),
      );
    } catch (cause) {
      // A failed request is an error, never a refusal: the answer view shows
      // exactly what went wrong. An expired session (401) or missing consent
      // (403) is not an outage - say so, so the user knows to sign in or consent
      // rather than think the assistant is down.
      const status = cause instanceof RequestFailed ? cause.status : 0;
      const explanation =
        status === 401
          ? "Your session has expired. Please sign in again to continue."
          : status === 403
            ? "Answering needs your consent to the privacy notice first."
            : "The question was not answered because the assistant backend could not be reached.";
      applyToActiveAnswer((answer) => ({
        ...answer,
        state: "error",
        detail: cause instanceof Error ? cause.message : String(cause),
        explanation,
      }));
    } finally {
      setStreaming(false);
    }
  }

  return {
    conversations,
    active,
    activeId,
    setActiveId: (id: number) => void selectConversation(id),
    question,
    setQuestion,
    streaming,
    ask,
    newChat,
    deleteConversation,
  };
}
