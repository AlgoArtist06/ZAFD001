// The multilingual answering layer (Hindi, Tamil, Gujarati), ported from
// rag/domain/multilingual.py. Several Supported Languages are served over one
// English Source of Truth: the user's language is detected by script, the
// query's intent is extracted into English (legal terms preserved), and
// critical terms render back into the user's language.
//
// The Bilingual Legal Glossary is the deterministic backbone: the same
// curated table both normalises an incoming (or code-mixed) query to English
// and constrains the terminology of the output, so a term like bailable vs
// non-bailable cannot flip meaning in translation. The glossary data is
// bundled from data/glossary.json at build time.
import glossaryJson from "../../../data/glossary.json";
import { contentStems } from "./text";

export const ENGLISH = "en";
export const HINDI = "hi";
export const TAMIL = "ta";
export const GUJARATI = "gu";

export const SUPPORTED_LANGUAGES = [ENGLISH, HINDI, TAMIL, GUJARATI] as const;

// Each non-English Supported Language writes in its own Unicode block, and
// that script is what marks a query as that language rather than English.
// Code-mixing (e.g. Hinglish) still trips the right script as long as any
// word is in it. Detection walks these in order, so adding a language is
// adding one row here and its glossary column.
const SCRIPTS: Array<[string, RegExp]> = [
  [HINDI, /[ऀ-ॿ]/], // Devanagari
  [TAMIL, /[஀-௿]/], // Tamil
  [GUJARATI, /[઀-૿]/], // Gujarati
];

// Any supported non-Latin script: a token carrying one is a foreign-script
// word. Used to drop function words the glossary does not carry once legal
// terms have been mapped to English.
const FOREIGN_RE = new RegExp(
  SCRIPTS.map(([, pattern]) => pattern.source).join("|"),
);

// Whether any supported non-Latin script appears in `text`. The live intent
// extractor uses this to skip the LLM call for a pure-English query.
export function hasForeignScript(text: string): boolean {
  return FOREIGN_RE.test(text);
}

// Detect the user's language from the raw query: the first Supported
// Language whose script appears (including code-mixed queries), else "en".
export function detectLanguage(query: string): string {
  for (const [language, pattern] of SCRIPTS) {
    if (pattern.test(query)) return language;
  }
  return ENGLISH;
}

// One critical legal term and its equivalents across Supported Languages.
// `unverified` names the languages whose translation lacks an official
// central-act source and is therefore flagged for review.
export type GlossaryEntry = {
  en: string;
  byLanguage: Record<string, string>;
  unverified: Set<string>;
};

type GlossaryRow = { en: string; unverified?: string[] } & Record<
  string,
  unknown
>;

function entryFromRow(row: GlossaryRow): GlossaryEntry {
  // Every key other than the English term and the bookkeeping `unverified`
  // flag is a Supported Language column, so new languages are pure data.
  const byLanguage: Record<string, string> = {};
  for (const [key, value] of Object.entries(row)) {
    if (key !== "en" && key !== "unverified" && typeof value === "string") {
      byLanguage[key] = value;
    }
  }
  return {
    en: row.en,
    byLanguage,
    unverified: new Set(row.unverified ?? []),
  };
}

// The curated table of critical legal terms across Supported Languages. It
// serves two directions over the same rows: toEnglish rewrites a Hindi or
// code-mixed query into an English query for retrieval, and render renders an
// English term back into the user's language with the English kept inline.
export class BilingualGlossary {
  private entries: GlossaryEntry[];
  private enTo: Map<string, Map<string, string>>;
  private foreignToEn: Array<[string, string]>;

  constructor(entries: GlossaryEntry[]) {
    this.entries = entries;
    // Forward maps, one per Supported Language: English term -> target term.
    this.enTo = new Map();
    for (const entry of entries) {
      for (const [language, term] of Object.entries(entry.byLanguage)) {
        if (!this.enTo.has(language)) this.enTo.set(language, new Map());
        this.enTo.get(language)!.set(entry.en, term);
      }
    }
    // One reverse map for normalisation: every foreign term -> its English
    // equivalent, longest foreign forms first so a phrase is matched before
    // any of its component words.
    this.foreignToEn = entries
      .flatMap((entry) =>
        Object.values(entry.byLanguage).map(
          (term) => [term, entry.en] as [string, string],
        ),
      )
      .sort((a, b) => b[0].length - a[0].length);
  }

  static load(): BilingualGlossary {
    const raw = glossaryJson as { terms?: GlossaryRow[]; domains?: GlossaryRow[] };
    const rows = [...(raw.terms ?? []), ...(raw.domains ?? [])];
    return new BilingualGlossary(rows.map(entryFromRow));
  }

  // Normalise a query to an English query, preserving legal terms. Each known
  // foreign term (longest first) is replaced with its English equivalent;
  // remaining foreign-script tokens are dropped, while Latin-script tokens -
  // English words mixed into a code-mixed query - are kept verbatim.
  toEnglish(query: string): string {
    let text = query;
    for (const [foreign, en] of this.foreignToEn) {
      text = text.split(foreign).join(` ${en} `);
    }
    return text
      .split(/\s+/)
      .filter((t) => t && !FOREIGN_RE.test(t))
      .join(" ");
  }

  // The glossary's equivalent of an English term in `language`, if any.
  termFor(englishTerm: string, language: string): string | null {
    return this.enTo.get(language)?.get(englishTerm) ?? null;
  }

  // Foreign term -> authoritative English term for a Supported Language: the
  // deterministic hard constraints injected into the LLM intent-extraction
  // prompt, so the curated glossary - not the model - fixes the terminology.
  constraintsFor(language: string): Record<string, string> {
    const constraints: Record<string, string> = {};
    for (const entry of this.entries) {
      const term = entry.byLanguage[language];
      if (term !== undefined) constraints[term] = entry.en;
    }
    return constraints;
  }

  // Render a critical term in `language` with the English inline in brackets,
  // so the critical legal term appears in the user's language while its
  // authoritative English stays visible.
  render(englishTerm: string, language: string): string {
    if (language === ENGLISH) return englishTerm;
    const translated = this.termFor(englishTerm, language);
    return translated ? `${translated} (${englishTerm})` : englishTerm;
  }

  // English terms whose `language` translation lacks an official source.
  unverifiedTerms(language: string): string[] {
    return this.entries
      .filter((e) => e.unverified.has(language))
      .map((e) => e.en);
  }
}

// A raw query after detection and intent extraction.
export type NormalizedQuery = {
  language: string;
  englishQuery: string;
};

// Detect the language and normalise a query to English for retrieval. The
// live implementation (convex/llm.ts) wires an LLM behind this; tests inject
// deterministic doubles. Same live-only seam as generation (ADR 0010).
export type IntentExtractor = (query: string) => Promise<NormalizedQuery>;

// Ambiguous terms that, on their own, do not pin down a single Covered
// Domain. Such a query triggers a Confirmation Step rather than a guess.
const AMBIGUOUS: Record<string, Record<string, string>> = {
  right: {
    [ENGLISH]:
      "Did you mean your fundamental rights, your consumer rights, or your " +
      "intellectual property rights? Please clarify so I can answer " +
      "accurately.",
    [HINDI]:
      "क्या आपका मतलब आपके मौलिक अधिकार (fundamental rights), उपभोक्ता अधिकार " +
      "(consumer rights), या बौद्धिक संपदा अधिकार (intellectual property rights) " +
      "से है? कृपया स्पष्ट करें ताकि मैं सटीक उत्तर दे सकूँ।",
    [TAMIL]:
      "நீங்கள் உங்கள் அடிப்படை உரிமைகள் (fundamental rights), நுகர்வோர் உரிமைகள் " +
      "(consumer rights), அல்லது அறிவுசார் சொத்து உரிமைகள் (intellectual property " +
      "rights) குறித்து கேட்கிறீர்களா? துல்லியமாக பதிலளிக்க தயவுசெய்து " +
      "தெளிவுபடுத்தவும்.",
    [GUJARATI]:
      "શું તમારો અર્થ તમારા મૂળભૂત અધિકારો (fundamental rights), ગ્રાહક અધિકારો " +
      "(consumer rights), અથવા બૌદ્ધિક સંપદા અધિકારો (intellectual property " +
      "rights) છે? કૃપા કરીને સ્પષ્ટ કરો જેથી હું સચોટ જવાબ આપી શકું.",
  },
};

// The Confirmation Step question for an ambiguous query, or null. A query is
// ambiguous when its only content words are ambiguous terms - it carries no
// other legal content to disambiguate against.
export function confirmationFor(
  englishQuery: string,
  language: string = ENGLISH,
): string | null {
  const stems = new Set(contentStems(englishQuery));
  if (stems.size === 0) return null;
  const ambiguousTerms = new Set(Object.keys(AMBIGUOUS));
  if (![...stems].every((s) => ambiguousTerms.has(s))) return null;
  for (const term of Object.keys(AMBIGUOUS)) {
    if (stems.has(term)) {
      const texts = AMBIGUOUS[term];
      return texts[language] ?? texts[ENGLISH];
    }
  }
  return null;
}
