import { AnswerView } from "@/components/answer-view";
import { EmptyState } from "@/components/chat/empty-state";
import type { Turn } from "@/hooks/use-chat";

// The Conversation log: the user's questions as right-aligned bubbles, each
// Grounded Answer in its structured, safe form. aria-live announces streamed
// parts to screen readers as they arrive.
export function Thread({
  turns,
  onPickTopic,
}: {
  turns: Turn[];
  onPickTopic: (prompt: string) => void;
}) {
  return (
    <section
      role="log"
      aria-label="Conversation"
      aria-live="polite"
      className="flex flex-1 flex-col gap-4 overflow-y-auto px-1 pb-4"
    >
      {turns.length === 0 && <EmptyState onPick={onPickTopic} />}
      {turns.map((turn, index) =>
        turn.role === "user" ? (
          <div
            key={index}
            className="bg-primary text-primary-foreground max-w-[85%] self-end rounded-xl rounded-br-sm px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-xs"
          >
            {turn.text}
          </div>
        ) : (
          <AnswerView key={index} answer={turn.answer} />
        ),
      )}
    </section>
  );
}
