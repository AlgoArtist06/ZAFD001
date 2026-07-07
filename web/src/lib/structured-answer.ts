export type Citation = { reference: string; verbatim: string; url: string };
export type AnswerState = "normal" | "emergency" | "refusal" | "error";
export type RefusalReason = "no_match" | "advice" | "citations_unverified";

export type StructuredAnswer = {
  state: AnswerState;
  explanation: string;
  citations: Citation[];
  language?: string;
  reason?: RefusalReason;
  detail?: string;
  highStakesNotice?: string;
  note?: string;
  nextStep?: string;
  disclaimer?: string;
};

export function emptyAnswer(): StructuredAnswer {
  return { state: "normal", explanation: "", citations: [] };
}
