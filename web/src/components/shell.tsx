"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { apiUrl } from "@/lib/api";

type Role = "user" | "assistant";

type Turn = { role: Role; text: string };

// The two answering profiles of the dual-mode seam. Citizen is the default for a
// new Conversation; Professional is opted into when the Conversation is started.
type Mode = "citizen" | "professional";

type Conversation = { id: number; mode: Mode; turns: Turn[] };

// How each Mode reads in the UI - on the selector and the sidebar badge.
const MODE_LABEL: Record<Mode, string> = {
  citizen: "Citizen",
  professional: "Professional",
};

// The Supported Languages the answer seam reads back in. The code is the
// `language` parameter passed into the multilingual seam; the label is the
// language's own endonym, so a reader recognises their language by its script.
type Language = "en" | "hi" | "ta" | "gu";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
  { code: "gu", label: "ગુજરાતી" },
];

// The label shown for a Conversation in the sidebar: its first question, or a
// placeholder while it is still empty.
function conversationTitle(conversation: Conversation): string {
  const firstUser = conversation.turns.find((turn) => turn.role === "user");
  return firstUser ? firstUser.text : "New chat";
}

// The prior user turns of a Conversation, oldest first - the context the answer
// seam rewrites a dependent follow-up against. A fresh Conversation has none, so
// nothing carries across from a previous one.
function contextOf(conversation: Conversation): string[] {
  return conversation.turns
    .filter((turn) => turn.role === "user")
    .map((turn) => turn.text);
}

// How the shell obtains the signed-in user's session token. The authenticated
// app passes Clerk's `getToken`; without a session it resolves to null, so the
// component stays renderable in isolation.
type ShellProps = { getToken?: () => Promise<string | null> };

export function Shell({ getToken = async () => null }: ShellProps) {
  const [conversations, setConversations] = useState<Conversation[]>([
    { id: 1, mode: "citizen", turns: [] },
  ]);
  const [activeId, setActiveId] = useState(1);
  const [nextId, setNextId] = useState(2);
  const [question, setQuestion] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const [streaming, setStreaming] = useState(false);

  const active = conversations.find((c) => c.id === activeId)!;

  function updateActive(update: (turns: Turn[]) => Turn[]) {
    setConversations((prev) =>
      prev.map((c) => (c.id === activeId ? { ...c, turns: update(c.turns) } : c)),
    );
  }

  // The Mode is chosen only while the Conversation is empty; once it carries
  // turns it is locked, so a message never changes the profile mid-Conversation.
  function setActiveMode(mode: Mode) {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeId && c.turns.length === 0 ? { ...c, mode } : c,
      ),
    );
  }

  function newChat() {
    const id = nextId;
    setNextId(id + 1);
    setConversations((prev) => [...prev, { id, mode: "citizen", turns: [] }]);
    setActiveId(id);
    setQuestion("");
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
      { role: "assistant", text: "" },
    ]);

    try {
      // The session token attributes this request to the signed-in user, so the
      // backend scopes the Conversation to them and never to another user.
      const token = await getToken();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(apiUrl("/api/answer"), {
        method: "POST",
        headers,
        body: JSON.stringify({ query, context, mode: active.mode, language }),
      });
      if (!response.ok || !response.body) {
        throw new Error(`Request failed (${response.status})`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        updateActive((turns) => appendToLastAssistant(turns, chunk));
      }
    } catch {
      updateActive((turns) =>
        appendToLastAssistant(
          turns,
          "Something went wrong reaching the assistant. Is the backend running?",
        ),
      );
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full flex-col md:flex-row">
      <aside
        aria-label="Conversations"
        className="flex w-full flex-col gap-4 border-b p-4 md:h-screen md:w-72 md:border-r md:border-b-0"
      >
        <p className="text-sm font-semibold tracking-tight">
          Legal Awareness Assistant
        </p>
        <Button onClick={newChat} variant="outline" className="justify-start">
          + New chat
        </Button>
        <nav
          aria-label="Conversation list"
          className="flex max-h-40 flex-col gap-1 overflow-y-auto md:max-h-none"
        >
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              onClick={() => setActiveId(conversation.id)}
              aria-current={conversation.id === activeId}
              className={`flex flex-col items-start gap-1 rounded-md px-3 py-2 text-left text-sm hover:bg-muted ${
                conversation.id === activeId ? "bg-muted font-medium" : ""
              }`}
            >
              <span className="w-full truncate">
                {conversationTitle(conversation)}
              </span>
              <span className="text-muted-foreground rounded border px-1.5 text-xs font-normal">
                {MODE_LABEL[conversation.mode]}
              </span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 md:h-screen md:py-12">
        <section
          role="log"
          aria-label="Conversation"
          aria-live="polite"
          className="flex flex-1 flex-col gap-4 overflow-y-auto"
        >
          {active.turns.length === 0 && (
            <div className="text-muted-foreground mt-[8vh] text-center">
              <p className="text-foreground text-xl font-semibold">
                What do you want to understand?
              </p>
              <p className="mt-2 text-base">
                Ask about your rights in plain language. Every answer is grounded
                in a cited legal source.
              </p>
            </div>
          )}
          {active.turns.map((turn, index) => (
            <div
              key={index}
              className={`max-w-full rounded-lg border p-4 text-base leading-7 whitespace-pre-wrap ${
                turn.role === "user" ? "bg-muted self-end" : "bg-muted/40"
              }`}
            >
              {turn.text}
            </div>
          ))}
        </section>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ask();
          }}
          className="space-y-3"
        >
          {active.turns.length === 0 && (
            <fieldset
              role="radiogroup"
              aria-label="Answer mode"
              className="flex items-center gap-2 text-sm"
            >
              <legend className="text-muted-foreground mb-1">Answer mode</legend>
              {(["citizen", "professional"] as Mode[]).map((mode) => (
                <label
                  key={mode}
                  className={`cursor-pointer rounded-md border px-3 py-1 ${
                    active.mode === mode ? "bg-muted font-medium" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="mode"
                    className="sr-only"
                    checked={active.mode === mode}
                    onChange={() => setActiveMode(mode)}
                  />
                  {MODE_LABEL[mode]}
                </label>
              ))}
            </fieldset>
          )}
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Answer language</span>
            <select
              aria-label="Answer language"
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
              className="rounded-md border bg-transparent px-2 py-1"
            >
              {LANGUAGES.map(({ code, label }) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <Textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. What does the law say about theft of property?"
            rows={3}
            aria-label="Your legal question"
            disabled={streaming}
          />
          <Button type="submit" disabled={streaming || question.trim() === ""}>
            {streaming ? "Answering…" : "Ask"}
          </Button>
        </form>

        <p className="text-muted-foreground border-t pt-3 text-center text-sm">
          This assistant gives legal information, not legal advice. For help with
          your situation, contact a lawyer or your nearest Legal Services
          Authority (NALSA / DLSA).
        </p>
      </main>
    </div>
  );
}

function appendToLastAssistant(turns: Turn[], chunk: string): Turn[] {
  const next = [...turns];
  const last = next[next.length - 1];
  if (last && last.role === "assistant") {
    next[next.length - 1] = { ...last, text: last.text + chunk };
  }
  return next;
}
