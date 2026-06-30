import { BookOpen, HandHelping, PhoneCall, TriangleAlert } from "lucide-react";

// The structured signals the answer seam returns, shaped for presentation. The
// UI only routes and renders these; it never decides them. A Citation keeps its
// reference and Verbatim Text in the original authoritative English so the basis
// stays court-traceable even when the explanation is in another language.
export type Citation = { reference: string; verbatim: string; url: string };

// The three presentation states the answer can take. A normal grounded answer, a
// high-stakes/emergency answer that must lead with help, and a graceful refusal
// when the query is out of scope or unsupported.
export type AnswerState = "normal" | "emergency" | "refusal";

export type StructuredAnswer = {
  state: AnswerState;
  explanation: string;
  citations: Citation[];
  highStakesNotice?: string;
  note?: string;
  nextStep?: string;
  disclaimer?: string;
};

// An empty answer, the seed a streamed answer accumulates its parts into.
export function emptyAnswer(): StructuredAnswer {
  return { state: "normal", explanation: "", citations: [] };
}

// How each state tints its container, so a reader tells emergency from refusal
// from a normal sourced answer at a glance. Large, readable text throughout, for
// a low-literacy reader.
const STATE_CLASS: Record<AnswerState, string> = {
  normal: "border-border bg-muted/40",
  emergency: "border-destructive/40 bg-destructive/5",
  refusal: "border-amber-500/40 bg-amber-500/5",
};

export function AnswerView({ answer }: { answer: StructuredAnswer }) {
  return (
    <div
      data-answer-state={answer.state}
      className={`flex max-w-full flex-col gap-4 rounded-lg border p-4 text-lg leading-8 ${STATE_CLASS[answer.state]}`}
    >
      {/* High-Stakes Routing: emergency and legal-aid contacts lead, before any
          legal content, so urgent help comes first. */}
      {answer.highStakesNotice && (
        <section
          role="alert"
          aria-label="Emergency and helpline contacts"
          className="border-destructive/50 bg-destructive/10 rounded-md border p-3"
        >
          <p className="text-destructive flex items-center gap-2 font-semibold">
            <PhoneCall className="size-5 shrink-0" aria-hidden />
            Get urgent help first
          </p>
          <p className="mt-2 whitespace-pre-wrap">{answer.highStakesNotice}</p>
        </section>
      )}

      {/* Plain-language explanation. A refusal says plainly that there is no
          sourced answer, rather than guessing. */}
      {answer.state === "refusal" ? (
        <p className="text-foreground flex items-start gap-2 font-medium">
          <TriangleAlert className="mt-1 size-5 shrink-0 text-amber-600" aria-hidden />
          <span>{answer.explanation}</span>
        </p>
      ) : (
        <p className="whitespace-pre-wrap">{answer.explanation}</p>
      )}

      {/* The Citation block: visually distinct, with the statutory text quoted
          verbatim in its original English. */}
      {answer.citations.length > 0 && (
        <section
          aria-label="Legal basis"
          className="border-primary/30 bg-background rounded-md border-l-4 p-3"
        >
          <p className="text-muted-foreground mb-2 flex items-center gap-2 text-sm font-semibold tracking-wide uppercase">
            <BookOpen className="size-4 shrink-0" aria-hidden />
            Legal basis (verbatim, in English)
          </p>
          <div className="flex flex-col gap-3">
            {answer.citations.map((citation, index) => (
              <figure key={index} className="m-0">
                <figcaption className="font-medium">
                  {citation.reference}
                </figcaption>
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

      {answer.note && (
        <p className="text-muted-foreground text-base">{answer.note}</p>
      )}

      {answer.nextStep && (
        <section aria-label="Practical next step">
          <p className="whitespace-pre-wrap">{answer.nextStep}</p>
        </section>
      )}

      {/* The persistent Disclaimer and Legal-Aid Pointer, on every answer. */}
      {answer.disclaimer && (
        <section
          aria-label="Disclaimer and legal aid"
          className="text-muted-foreground border-t pt-3 text-base"
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
