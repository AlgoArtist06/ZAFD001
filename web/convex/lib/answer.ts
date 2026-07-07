// The grounded answer seam, ported from rag/domain/answer.py:
//
//   route domain -> hybrid retrieve -> expand to parent + siblings ->
//   grounded generate -> verify citations -> structured Grounded Answer
//
// If no retrieved chunk is lexically grounded in the query, or no Citation
// survives verification, the seam returns a Refusal ("I do not have a sourced
// answer for that") rather than a guess. The pipeline is split into
// prepare/finalize so the streaming path can run generation incrementally
// while every decision stays in this seam.
//
// Seams (retriever, section lookup, generator, intent extractor) are
// injected: production wires Convex vector search and the live LLM
// (ADR 0010); tests inject deterministic doubles.
import {
  ADVICE_REFUSAL_NEXT_STEP,
  ADVICE_REFUSAL_TEXT,
  HIGH_STAKES_NOTICE,
  screenRequest,
  softenAdvice,
} from "../guardrails";
import { verifyCitations, type Citation } from "../citations";
import {
  expand,
  type RetrievalHit,
  type RetrievedSection,
  type SectionMembers,
} from "./expansion";
import { DISCLAIMER, type DraftAnswer, type Generator } from "./generation";
import { rewriteFollowup } from "./followup";
import { expandQuery } from "./hybrid";
import { loadIpcBnsMapping, type IpcBnsMapping, type MappingEntry } from "./mapping";
import {
  confirmationFor,
  GUJARATI,
  HINDI,
  TAMIL,
  type IntentExtractor,
} from "./multilingual";
import { formerIpcNote, recognizeIpc } from "./recognition";
import { routeDomains } from "./routing";
import { type ActType } from "./models";

export const REFUSAL_TEXT = "I do not have a sourced answer for that";

// Refusal copy per Supported Language, so a user is refused in their own
// language.
const REFUSAL_TEXT_BY_LANGUAGE: Record<string, string> = {
  [HINDI]: "मेरे पास इसका कोई स्रोत-समर्थित उत्तर नहीं है",
  [TAMIL]: "அந்தக் கேள்விக்கு என்னிடம் ஆதாரப்பூர்வமான பதில் இல்லை",
  [GUJARATI]: "મારી પાસે તેનો કોઈ સ્રોત-આધારિત જવાબ નથી",
};

export const REFUSAL_NEXT_STEP =
  "For help, consider contacting a lawyer or your nearest Legal Services " +
  "Authority (NALSA / DLSA).";

const REFUSAL_NEXT_STEP_BY_LANGUAGE: Record<string, string> = {
  [HINDI]:
    "सहायता के लिए किसी वकील या अपने निकटतम विधिक सेवा प्राधिकरण " +
    "(NALSA / DLSA) से संपर्क करने पर विचार करें।",
  [TAMIL]:
    "உதவிக்கு, ஒரு வழக்கறிஞரை அல்லது உங்கள் அருகிலுள்ள சட்ட சேவை ஆணையத்தை " +
    "(NALSA / DLSA) தொடர்பு கொள்ளவும்.",
  [GUJARATI]:
    "મદદ માટે, વકીલનો અથવા તમારી નજીકના કાનૂની સેવા સત્તામંડળ " +
    "(NALSA / DLSA) નો સંપર્ક કરવાનું વિચારો.",
};

// Why an answer was refused, for the frontend to say exactly what went wrong.
export type RefusalReason = "" | "no_match" | "advice" | "citations_unverified";

export type GroundedAnswer = {
  query: string;
  language: string;
  explanation: string;
  legalBasis: string;
  nextStep: string;
  citations: Citation[];
  refused: boolean;
  refusalReason: RefusalReason;
  highStakes: boolean;
  highStakesNotice: string;
  formerIpcNote: string;
  disclaimer: string;
  needsConfirmation: boolean;
  confirmation: string;
};

// The structured rendering: a Confirmation Step short-circuits to the
// clarifying question; otherwise High-Stakes Routing leads, then explanation,
// legal basis, IPC note, next step, and the Disclaimer last.
export function answerText(answer: GroundedAnswer): string {
  if (answer.needsConfirmation) return answer.confirmation;
  const parts: string[] = [];
  if (answer.highStakesNotice) parts.push(answer.highStakesNotice);
  parts.push(answer.explanation);
  if (answer.legalBasis) parts.push(answer.legalBasis);
  if (answer.formerIpcNote) parts.push(answer.formerIpcNote);
  if (answer.nextStep) parts.push(answer.nextStep);
  if (answer.disclaimer) parts.push(answer.disclaimer);
  return parts.join("\n\n");
}

// A query that passed every pre-generation gate, ready for the generator.
export type PreparedQuery = {
  kind: "prepared";
  query: string;
  language: string;
  englishQuery: string;
  sections: RetrievedSection[];
  highStakes: boolean;
  notice: string;
  references: MappingEntry[];
};

// The retrieval seam: hybrid-scored hits for an (already expanded) English
// query over the routed domains. Production is Convex vector search plus the
// stems scan; tests use an in-memory implementation over the same ranking.
export type Retriever = (
  query: string,
  domains: ActType[],
) => Promise<RetrievalHit[]>;

export type AssistantSeams = {
  retrieve: Retriever;
  sectionMembers: SectionMembers;
  generator: Generator;
  intentExtractor: IntentExtractor;
  mapping?: IpcBnsMapping;
};

function refuse(
  query: string,
  language: string,
  highStakes = false,
  notice = "",
  reason: RefusalReason = "no_match",
): GroundedAnswer {
  return {
    query,
    language,
    explanation: REFUSAL_TEXT_BY_LANGUAGE[language] ?? REFUSAL_TEXT,
    legalBasis: "",
    nextStep: REFUSAL_NEXT_STEP_BY_LANGUAGE[language] ?? REFUSAL_NEXT_STEP,
    citations: [],
    refused: true,
    refusalReason: reason,
    highStakes,
    highStakesNotice: notice,
    formerIpcNote: "",
    disclaimer: DISCLAIMER,
    needsConfirmation: false,
    confirmation: "",
  };
}

// Pose a Confirmation Step instead of answering an ambiguous query.
function confirm(
  query: string,
  language: string,
  confirmation: string,
): GroundedAnswer {
  return {
    query,
    language,
    explanation: confirmation,
    legalBasis: "",
    nextStep: "",
    citations: [],
    refused: false,
    refusalReason: "",
    highStakes: false,
    highStakesNotice: "",
    formerIpcNote: "",
    disclaimer: "",
    needsConfirmation: true,
    confirmation,
  };
}

// Refuse a request for Legal Advice and redirect to real help.
function refuseAdvice(query: string, language: string): GroundedAnswer {
  return {
    query,
    language,
    explanation: ADVICE_REFUSAL_TEXT,
    legalBasis: "",
    nextStep: ADVICE_REFUSAL_NEXT_STEP,
    citations: [],
    refused: true,
    refusalReason: "advice",
    highStakes: false,
    highStakesNotice: "",
    formerIpcNote: "",
    disclaimer: DISCLAIMER,
    needsConfirmation: false,
    confirmation: "",
  };
}

// Everything before generation: normalize, screen, retrieve, gate, expand.
// Returns a complete GroundedAnswer when the pipeline decides without
// generating (a Confirmation Step, an advice Refusal, or an ungrounded
// Refusal); otherwise a PreparedQuery for the generator.
export async function prepare(
  query: string,
  language: string,
  seams: AssistantSeams,
): Promise<PreparedQuery | GroundedAnswer> {
  // Multilingual layer: detect the language and extract the intent into
  // English so every downstream step runs over the single English Source of
  // Truth; an explicit non-English language is honoured when the query
  // carries no script of its own.
  const normalized = await seams.intentExtractor(query);
  const outLanguage =
    normalized.language !== "en" ? normalized.language : language;
  const englishQuery = normalized.englishQuery;

  // Confirmation Step: an ambiguous query is clarified, never guessed at.
  const confirmation = confirmationFor(englishQuery, outLanguage);
  if (confirmation !== null) {
    return confirm(query, outLanguage, confirmation);
  }

  // Input-side scope contract first: refuse advice, flag High-Stakes.
  const screen = screenRequest(englishQuery);
  const notice = screen.highStakes ? HIGH_STAKES_NOTICE : "";
  if (screen.kind === "advice") {
    return refuseAdvice(query, outLanguage);
  }

  // Recognise repealed IPC numbers and normalise them to the current BNS
  // section before retrieval; carry the former number forward to annotate.
  const mapping = seams.mapping ?? loadIpcBnsMapping();
  const recognized = recognizeIpc(englishQuery, mapping);

  // Expand lay phrasing toward legal concepts before retrieval.
  const retrievalQuery = expandQuery(recognized.query);
  const domains = routeDomains(retrievalQuery);
  const hits = await seams.retrieve(retrievalQuery, domains);
  // The cheap support gate: a hit with zero lexical overlap is not grounded
  // at all. A weak incidental overlap can still pass here; the model then
  // judges relevance itself (an empty draft becomes a "no_match" Refusal in
  // finalize), so garbage never becomes an answer.
  const grounded = hits.filter((h) => h.keywordScore > 0);
  if (grounded.length === 0) {
    return refuse(query, outLanguage, screen.highStakes, notice);
  }

  return {
    kind: "prepared",
    query,
    language: outLanguage,
    englishQuery,
    sections: await expand(grounded, seams.sectionMembers),
    highStakes: screen.highStakes,
    notice,
    references: recognized.references,
  };
}

// Everything after generation: verify citations, soften, assemble. The
// anti-hallucination backstop lives here: a draft whose every citation fails
// verification becomes a Refusal, never a guess. An empty draft is the model
// saying the sources do not answer the question ("no_match"); a substantive
// draft stripped of every citation is "citations_unverified".
export function finalize(
  prepared: PreparedQuery,
  draft: DraftAnswer,
): GroundedAnswer {
  const citations = verifyCitations(draft.citations, prepared.sections);
  if (citations.length === 0) {
    const empty =
      draft.explanation.trim() === "" && draft.citations.length === 0;
    return refuse(
      prepared.query,
      prepared.language,
      prepared.highStakes,
      prepared.notice,
      empty ? "no_match" : "citations_unverified",
    );
  }

  // Output-side check: soften any phrasing that slipped into advice.
  return {
    query: prepared.query,
    language: prepared.language,
    explanation: softenAdvice(draft.explanation),
    legalBasis: softenAdvice(draft.legalBasis),
    nextStep: softenAdvice(draft.nextStep),
    citations,
    refused: false,
    refusalReason: "",
    highStakes: prepared.highStakes,
    highStakesNotice: prepared.notice,
    formerIpcNote: formerIpcNote(prepared.references),
    disclaimer: draft.disclaimer,
    needsConfirmation: false,
    confirmation: "",
  };
}

export async function answer(
  query: string,
  language: string,
  seams: AssistantSeams,
): Promise<GroundedAnswer> {
  const prepared = await prepare(query, language, seams);
  if (!("kind" in prepared)) {
    return prepared;
  }
  const draft = await seams.generator(
    prepared.englishQuery,
    prepared.sections,
    prepared.language,
  );
  return finalize(prepared, draft);
}

// How many recent standalone turns are kept as context for rewriting a
// follow-up (mirrors Conversation._CONTEXT_TURNS in rag/domain/answer.py).
export const CONTEXT_TURNS = 4;

// A single chat over one shared seam set, remembering context across its own
// turns only: a dependent follow-up is rewritten into a standalone query
// against the bounded recent turns before retrieval, then runs the same full
// pipeline. Used by the gold-eval harness; the deployed pipeline rebuilds the
// same bounded memory from the persisted turns instead.
export class Conversation {
  private recent: string[] = [];

  constructor(private seams: AssistantSeams) {}

  async ask(query: string, language = "en"): Promise<GroundedAnswer> {
    const resolved = rewriteFollowup(query, this.recent);
    this.recent = [...this.recent, resolved].slice(-CONTEXT_TURNS);
    const result = await answer(resolved, language, this.seams);
    // Keep the user's actual words on the returned answer, not the rewrite.
    result.query = query;
    return result;
  }
}
