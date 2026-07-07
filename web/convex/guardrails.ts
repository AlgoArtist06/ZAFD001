// The layered guardrail stack that keeps the product on Legal Information,
// ported verbatim from rag/domain/guardrails.py.
//
// - screenRequest is the input-side scope contract: advice-seeking inputs are
//   routed to a Refusal, and High-Stakes queries (safety, arrest-in-progress,
//   active deadlines) are flagged so the answer leads with emergency contacts.
// - softenAdvice is the output-side check: it rewrites any "you should sue /
//   you will win" phrasing back to neutral, informational language.
//
// The High-Stakes notice, advice Refusal text, and Legal-Aid Pointer live here
// as the single source of the product's safety copy.

// The Legal-Aid Pointer: a concrete reference to real help, reused everywhere
// a Disclaimer or High-Stakes response needs one.
export const LEGAL_AID_POINTER =
  "a lawyer or your nearest Legal Services Authority (NALSA / DLSA)";

// The scope contract, stated plainly. The layered checks below enforce it.
export const SCOPE_CONTRACT =
  "This assistant provides Legal Information only: general, source-backed " +
  "explanation of what the law says and what the standard procedure is. It " +
  "does not provide Legal Advice - it will not predict the outcome of a case " +
  "or tell anyone what they personally should do.";

// High-Stakes Routing: leads with emergency and legal-aid contacts before the
// legal explanation when a query touches safety, arrest, or an active deadline.
export const HIGH_STAKES_NOTICE =
  "If you are in immediate danger or this is urgent, get help first:\n" +
  "- Emergency (police / fire / ambulance): 112\n" +
  "- Women's helpline: 181\n" +
  "- Free legal aid: contact " + LEGAL_AID_POINTER + ".\n" +
  "The legal information below is general and is not a substitute for urgent " +
  "help or a lawyer.";

export const ADVICE_REFUSAL_TEXT =
  "I can explain what the law says and the general procedure, but I cannot " +
  "predict the outcome of a case or tell you what you personally should do.";

export const ADVICE_REFUSAL_NEXT_STEP =
  "For guidance on your specific situation, please consult " + LEGAL_AID_POINTER + ".";

export type RequestKind = "answerable" | "advice";

// The input-side decision: what kind of request, and is it High-Stakes.
export type ScreenResult = {
  kind: RequestKind;
  highStakes: boolean;
};

// Advice-seeking markers: outcome prediction and personalised action requests.
// Deliberately curated - a guardrail errs toward refusing the personalised
// question, not toward guessing.
const ADVICE_MARKERS = [
  "will i win",
  "will i lose",
  "will i get bail",
  "will i be convicted",
  "will the court",
  "will the judge",
  "my chances",
  "chances of winning",
  "predict the outcome",
  "outcome of my case",
  "what should i do",
  "what do i do",
  "should i sue",
  "should i file",
  "should i sign",
  "should i accept",
  "should i plead",
  "should i",
  "what would you do",
  "what do you recommend",
  "do you recommend",
  "advise me",
  "give me advice",
  "tell me what to do",
];

// High-Stakes markers: safety, arrest-in-progress, active deadlines.
const HIGH_STAKES_MARKERS = [
  "being arrested",
  "police are arresting",
  "police are here",
  "they are arresting",
  "being detained",
  "in danger",
  "being attacked",
  "being beaten",
  "domestic violence",
  "threatening to kill",
  "going to kill",
  "about to be evicted",
  "deadline is today",
  "deadline is tomorrow",
  "due today",
  "due tomorrow",
  "last date is today",
  "last date is tomorrow",
  "hearing is tomorrow",
  "expires today",
  "expires tomorrow",
];

// Output-side advice phrasing to soften, mapped to neutral informational copy.
const SOFTENINGS: Array<[string, string]> = [
  ["you should sue", "one option the law provides is to approach the appropriate court or authority"],
  ["you should file", "one option the law provides is to file the appropriate complaint"],
  ["you will win", "the outcome of any case depends on its specific facts and is decided by the court"],
  ["you will lose", "the outcome of any case depends on its specific facts and is decided by the court"],
  ["you should", "you may wish to consider whether to"],
  ["i recommend", "the law provides that"],
];

function normalise(query: string): string {
  return query.toLowerCase().replace(/\s+/g, " ").trim();
}

function matchesAny(text: string, markers: string[]): boolean {
  return markers.some((marker) => text.includes(marker));
}

// Apply the input-side scope contract to a raw query. High-Stakes takes
// precedence over the advice refusal: an urgent query is answered with
// emergency contacts leading, never silently refused.
export function screenRequest(query: string): ScreenResult {
  const text = normalise(query);
  const highStakes = matchesAny(text, HIGH_STAKES_MARKERS);
  if (!highStakes && matchesAny(text, ADVICE_MARKERS)) {
    return { kind: "advice", highStakes: false };
  }
  return { kind: "answerable", highStakes };
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Rewrite any advice-style phrasing in answer text back to neutral language.
export function softenAdvice(text: string): string {
  let softened = text;
  for (const [phrase, replacement] of SOFTENINGS) {
    softened = softened.replace(
      new RegExp(escapeRegExp(phrase), "gi"),
      replacement,
    );
  }
  return softened;
}
