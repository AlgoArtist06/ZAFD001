// Grounded generation types, ported from rag/domain/generation.py.
// Generation runs under a hard contract: answer only from retrieved Source of
// Truth text, attach a Citation to every claim, never invent a section. The
// only production implementation is the live adapter in convex/llm.ts
// (ADR 0010); tests inject deterministic doubles.
import { type Citation } from "../citations";
import { type RetrievedSection } from "./expansion";

export const DISCLAIMER =
  "This is legal information, not legal advice. For help with your specific " +
  "situation, consult a lawyer or your nearest Legal Services Authority " +
  "(NALSA / DLSA).";

// A grounded draft: the three structured parts plus its Citations.
export type DraftAnswer = {
  explanation: string;
  legalBasis: string;
  nextStep: string;
  citations: Citation[];
  disclaimer: string;
};

export type Generator = (
  query: string,
  sections: RetrievedSection[],
  language: string,
) => Promise<DraftAnswer>;

// A streaming generator additionally reports the cumulative explanation text
// mid-generation (full text so far, not a delta). Optional: generators
// without it are served by running `generate` whole.
export type StreamingGenerator = (
  query: string,
  sections: RetrievedSection[],
  language: string,
  onExplanation: (textSoFar: string) => Promise<void>,
) => Promise<DraftAnswer>;
