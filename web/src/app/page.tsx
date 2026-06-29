"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

// The FastAPI demo endpoint. Override with NEXT_PUBLIC_API_URL when the backend
// runs somewhere other than the default localhost port.
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/answer";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [streaming, setStreaming] = useState(false);

  async function ask() {
    const query = question.trim();
    if (!query || streaming) return;

    setAnswer("");
    setStreaming(true);
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Request failed (${response.status})`);
      }

      // Render the Grounded Answer as it streams back, chunk by chunk, rather
      // than waiting for the whole blob.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        setAnswer((prev) => prev + decoder.decode(value, { stream: true }));
      }
    } catch {
      setAnswer(
        "Something went wrong reaching the assistant. Is the FastAPI backend running?",
      );
    } finally {
      setStreaming(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 px-6 py-16">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Legal Awareness Assistant
        </h1>
        <p className="text-muted-foreground text-base">
          Ask a question about your legal rights in plain English. Every answer
          is grounded in a cited legal source.
        </p>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask();
        }}
        className="space-y-3"
      >
        <Textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void ask();
            }
          }}
          placeholder="e.g. What does the law say about theft of property?"
          rows={3}
          aria-label="Your legal question"
          disabled={streaming}
        />
        <Button type="submit" disabled={streaming || question.trim() === ""}>
          {streaming ? "Answering…" : "Ask"}
        </Button>
      </form>

      {answer && (
        <section
          aria-label="Grounded answer"
          aria-live="polite"
          className="bg-muted/40 rounded-lg border p-5 text-base leading-7 whitespace-pre-wrap"
        >
          {answer}
        </section>
      )}
    </main>
  );
}
