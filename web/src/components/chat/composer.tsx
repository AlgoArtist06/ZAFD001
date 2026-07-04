"use client";

import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ComposerProps = {
  question: string;
  onQuestionChange: (value: string) => void;
  streaming: boolean;
  onSubmit: () => void;
};

export function Composer({
  question,
  onQuestionChange,
  streaming,
  onSubmit,
}: ComposerProps) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      className="bg-card space-y-3 rounded-xl border p-3 shadow-sm"
    >
      <Textarea
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="e.g. What does the law say about theft of property?"
        rows={2}
        aria-label="Your legal question"
        disabled={streaming}
        className="min-h-16 resize-none border-0 bg-transparent px-2 text-sm shadow-none focus-visible:ring-0 dark:bg-transparent"
      />
      <div className="flex items-center justify-between px-1">
        <span className="text-muted-foreground text-xs">
          Enter your question in any supported language
        </span>
        <Button
          type="submit"
          size="lg"
          disabled={streaming || question.trim() === ""}
          className="min-h-11 rounded-lg px-4"
        >
          {streaming ? "Answering…" : "Ask"}
          {!streaming && <Send className="size-4" aria-hidden />}
        </Button>
      </div>
    </form>
  );
}
