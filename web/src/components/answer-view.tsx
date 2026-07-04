import { BookOpen, CircleX, HandHelping, PhoneCall, TriangleAlert } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import type {
  AnswerState,
  RefusalReason,
  StructuredAnswer,
} from "@/lib/answer-stream";

// The structured signals live in the answer-stream contract; re-exported here
// so existing imports (and tests) keep working.
export { emptyAnswer } from "@/lib/answer-stream";
export type { AnswerState, Citation, StructuredAnswer } from "@/lib/answer-stream";

// How each state tints its container, so a reader tells emergency from refusal
// from error from a normal sourced answer at a glance. Large, readable text
// throughout, for a low-literacy reader.
const STATE_CLASS: Record<AnswerState, string> = {
  normal: "border-border bg-card",
  emergency: "border-destructive/40 bg-destructive/5",
  refusal: "border-highlight/40 bg-highlight/5",
  error: "border-destructive/40 bg-destructive/5",
};

// A plain-English heading per refusal reason, so the user is told exactly what
// went wrong rather than left guessing. The localised explanation follows it.
const REFUSAL_HEADING: Record<RefusalReason, string> = {
  no_match: "No matching source documents",
  advice: "This needs a lawyer, not this assistant",
  citations_unverified: "The model's answer could not be verified",
};

const REFUSAL_DETAIL: Record<RefusalReason, string> = {
  no_match:
    "Your question did not match any document in the stored legal sources, so no answer was generated.",
  advice:
    "The assistant only explains what the law says; it cannot give personalised legal advice.",
  citations_unverified:
    "The language model produced an answer, but none of its citations could be verified against the stored sources, so it was withheld.",
};

export function AnswerView({ answer }: { answer: StructuredAnswer }) {
  return (
    <div
      data-answer-state={answer.state}
      // The answer reads in the user's language; each Citation Anchor below
      // overrides back to lang="en" because it stays authoritative English.
      lang={answer.language}
      className={`flex flex-col gap-3 rounded-xl rounded-bl-sm border p-4 text-sm leading-relaxed shadow-xs ${STATE_CLASS[answer.state]}`}
    >
      {/* High-Stakes Routing: emergency and legal-aid contacts lead, before any
          legal content, so urgent help comes first. */}
      {answer.highStakesNotice && (
        <section
          role="alert"
          aria-label="Emergency and helpline contacts"
          className="border-destructive/40 bg-destructive/10 rounded-xl border p-4"
        >
          <p className="text-destructive flex items-center gap-2 font-semibold">
            <PhoneCall className="size-5 shrink-0" aria-hidden />
            Get urgent help first
          </p>
          <p className="mt-2 whitespace-pre-wrap">{answer.highStakesNotice}</p>
        </section>
      )}

      {/* An explicit error: the language model failed to produce an answer.
          The heading and the failure detail say exactly what went wrong. */}
      {answer.state === "error" ? (
        <section role="alert" aria-label="Assistant error">
          <p className="text-destructive flex items-start gap-2 font-semibold">
            <CircleX className="mt-1 size-5 shrink-0" aria-hidden />
            <span>The language model did not return an answer</span>
          </p>
          <p className="mt-2 whitespace-pre-wrap">{answer.explanation}</p>
          {answer.detail && (
            <p
              lang="en"
              className="text-muted-foreground bg-background/70 mt-2 rounded-md border p-2 font-mono text-xs"
            >
              {answer.detail}
            </p>
          )}
        </section>
      ) : answer.state === "refusal" ? (
        <section aria-label="No sourced answer">
          <p className="text-foreground flex items-start gap-2 font-semibold">
            <TriangleAlert className="text-highlight mt-1 size-5 shrink-0" aria-hidden />
            <span lang="en">
              {answer.reason ? REFUSAL_HEADING[answer.reason] : "No sourced answer"}
            </span>
          </p>
          {answer.reason && (
            <p lang="en" className="text-muted-foreground mt-2 text-xs leading-5">
              {REFUSAL_DETAIL[answer.reason]}
            </p>
          )}
          <p className="mt-2 whitespace-pre-wrap font-medium">{answer.explanation}</p>
        </section>
      ) : answer.explanation === "" && answer.citations.length === 0 ? (
        <div aria-hidden className="space-y-2 py-1">
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/5" />
          <Skeleton className="h-4 w-2/5" />
        </div>
      ) : (
        <p className="whitespace-pre-wrap">{answer.explanation}</p>
      )}

      {/* The Citation block: visually distinct, with the statutory text quoted
          verbatim in its original English. */}
      {answer.citations.length > 0 && (
        <section
          aria-label="Legal basis"
          className="border-primary/25 bg-background/70 rounded-xl border p-4"
        >
          <p className="text-muted-foreground mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide uppercase">
            <BookOpen className="size-4 shrink-0" aria-hidden />
            Legal basis (verbatim, in English)
          </p>
          <div className="flex flex-col gap-3">
            {answer.citations.map((citation, index) => (
              <figure key={index} className="m-0">
                <figcaption className="text-primary font-semibold">{citation.reference}</figcaption>
                <blockquote
                  lang="en"
                  className="border-primary/40 text-foreground mt-1 border-l-2 pl-3 italic"
                >
                  {citation.verbatim}
                </blockquote>
              </figure>
            ))}
          </div>
        </section>
      )}

      {answer.note && <p className="text-muted-foreground">{answer.note}</p>}

      {answer.nextStep && (
        <section aria-label="Practical next step">
          <p className="whitespace-pre-wrap">{answer.nextStep}</p>
        </section>
      )}

      {/* The persistent Disclaimer and Legal-Aid Pointer, on every answer. */}
      {answer.disclaimer && (
        <section
          aria-label="Disclaimer and legal aid"
          className="text-muted-foreground border-t pt-3 text-xs leading-5"
        >
          <p className="flex items-start gap-2">
            <HandHelping className="mt-1 size-4 shrink-0" aria-hidden />
            <span>{answer.disclaimer}</span>
          </p>
        </section>
      )}
    </div>
  );
}
