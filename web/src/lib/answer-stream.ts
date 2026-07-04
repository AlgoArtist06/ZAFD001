// The frontend half of the NDJSON answer contract: the structured signals the
// answer seam streams, and the pure folding logic that accumulates them. The
// UI only routes and renders these; it never decides them.

// A Citation keeps its reference and Verbatim Text in the original
// authoritative English so the basis stays court-traceable even when the
// explanation is in another language.
export type Citation = { reference: string; verbatim: string; url: string };

// The presentation states an answer can take: a normal grounded answer, a
// high-stakes/emergency answer that must lead with help, a graceful refusal
// when the query is out of scope or unsupported, and an explicit error when
// the language model failed to produce an answer at all.
export type AnswerState = "normal" | "emergency" | "refusal" | "error";

// Why a refusal happened, so the UI can say exactly what went wrong:
// "no_match" - the query matched no stored source document;
// "advice" - the request asked for personalised legal advice;
// "citations_unverified" - the model's draft cited nothing verifiable.
export type RefusalReason = "no_match" | "advice" | "citations_unverified";

export type StructuredAnswer = {
  state: AnswerState;
  explanation: string;
  citations: Citation[];
  // BCP 47 tag of the answer's language (from the meta frame), for lang= and
  // script-aware rendering. Citations stay lang="en" regardless.
  language?: string;
  // The machine-readable why of a refusal (state === "refusal").
  reason?: RefusalReason;
  // What actually failed (state === "error"): exception type and message.
  detail?: string;
  highStakesNotice?: string;
  note?: string;
  nextStep?: string;
  disclaimer?: string;
};

// An empty answer, the seed a streamed answer accumulates its parts into.
export function emptyAnswer(): StructuredAnswer {
  return { state: "normal", explanation: "", citations: [] };
}

// One NDJSON frame from the answer seam, folded into the structured answer as
// it arrives. Frames replace their field (the backend streams cumulative
// explanation text), except citations, which append. An unrecognised or
// malformed frame is ignored, so a partial line never corrupts what is already
// rendered.
export function applyFrame(
  answer: StructuredAnswer,
  line: string,
): StructuredAnswer {
  let frame: Record<string, unknown>;
  try {
    frame = JSON.parse(line) as Record<string, unknown>;
  } catch {
    return answer;
  }
  const text = typeof frame.text === "string" ? frame.text : "";
  switch (frame.kind) {
    case "meta":
      return {
        ...answer,
        state: frame.state as StructuredAnswer["state"],
        language:
          typeof frame.language === "string" ? frame.language : answer.language,
        reason:
          typeof frame.reason === "string"
            ? (frame.reason as RefusalReason)
            : answer.reason,
        detail: typeof frame.detail === "string" ? frame.detail : answer.detail,
      };
    case "highStakesNotice":
      return { ...answer, highStakesNotice: text };
    case "explanation":
      return { ...answer, explanation: text };
    case "citation":
      return {
        ...answer,
        citations: [
          ...answer.citations,
          {
            reference: String(frame.reference ?? ""),
            verbatim: String(frame.verbatim ?? ""),
            url: String(frame.url ?? ""),
          },
        ],
      };
    case "note":
      return { ...answer, note: text };
    case "nextStep":
      return { ...answer, nextStep: text };
    case "disclaimer":
      return { ...answer, disclaimer: text };
    default:
      return answer;
  }
}

// Read an NDJSON response body line by line, invoking `onLine` for each
// newline-complete line (and once more for a trailing unterminated line). Lines
// are buffered until complete so a frame split across network chunks still
// parses whole.
export async function readNdjson(
  body: ReadableStream<Uint8Array>,
  onLine: (line: string) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const drain = (final: boolean) => {
    let newline = buffer.indexOf("\n");
    while (newline !== -1) {
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (line.trim()) onLine(line);
      newline = buffer.indexOf("\n");
    }
    if (final && buffer.trim()) {
      onLine(buffer);
      buffer = "";
    }
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    drain(false);
  }
  drain(true);
}
