// Test doubles for the live-only seams, ported from tests/doubles.py. The
// product has no offline mode (ADR 0010); the suite still runs with no
// services because these doubles implement the same seams deterministically -
// TEST equipment, deliberately outside convex/ so nothing deployable can ever
// fall back to them.
import { createHash } from "node:crypto";

import {
  citationAnchor,
  citationFromSection,
  type Citation,
} from "../../convex/citations";
import {
  answer as answerSeam,
  Conversation,
  type AssistantSeams,
  type GroundedAnswer,
} from "../../convex/lib/answer";
import {
  inMemorySectionMembers,
  sectionProvenance,
  type RetrievalHit,
} from "../../convex/lib/expansion";
import { DISCLAIMER, type DraftAnswer } from "../../convex/lib/generation";
import {
  cosine,
  keywordOverlap,
  rankHybrid,
  type Candidate,
} from "../../convex/lib/hybrid";
import { isLoadable, type ActType, type Chunk } from "../../convex/lib/models";
import {
  BilingualGlossary,
  detectLanguage,
  GUJARATI,
  HINDI,
  TAMIL,
  type NormalizedQuery,
} from "../../convex/lib/multilingual";
import { contentStems } from "../../convex/lib/text";
import { type RetrievedSection } from "../../convex/lib/expansion";

const TOKEN_RE = /[a-z0-9]+/g;

// Hashing bag-of-words embedder with L2-normalised vectors - good enough for
// keyword-overlap retrieval in tests; no model weights, no network calls.
export function hashEmbed(text: string, dim = 512): number[] {
  const vec = new Array<number>(dim).fill(0);
  for (const token of text.toLowerCase().match(TOKEN_RE) ?? []) {
    const digest = createHash("md5").update(token, "utf8").digest("hex");
    const idx = Number(BigInt("0x" + digest) % BigInt(dim));
    vec[idx] += 1;
  }
  const norm = Math.sqrt(vec.reduce((sum, v) => sum + v * v, 0));
  return norm > 0 ? vec.map((v) => v / norm) : vec;
}

// The in-memory hybrid retriever: the same ranking function production uses,
// over hash embeddings of a fixture corpus (HybridRetriever's in-memory path).
export function inMemoryRetriever(
  corpus: Chunk[],
  options: { topK?: number; alpha?: number } = {},
) {
  const loadable = corpus.filter(isLoadable);
  const stems = loadable.map((c) => new Set(contentStems(c.text)));
  const vectors = loadable.map((c) => hashEmbed(c.text));
  return async (query: string, domains: ActType[]): Promise<RetrievalHit[]> => {
    const allowed = new Set(domains);
    const queryVec = hashEmbed(query);
    const queryStems = new Set(contentStems(query));
    const candidates: Candidate[] = [];
    for (let i = 0; i < loadable.length; i++) {
      if (!allowed.has(loadable[i].provenance.actType)) continue;
      candidates.push({
        chunk: loadable[i],
        keywordScore: keywordOverlap(queryStems, stems[i]),
        vectorScore: cosine(queryVec, vectors[i]),
      });
    }
    return rankHybrid(query, candidates, options);
  };
}

// Script-based detection and glossary lookup behind the intent seam.
export function glossaryIntentExtractor(glossary: BilingualGlossary) {
  return async (query: string): Promise<NormalizedQuery> => ({
    language: detectLanguage(query),
    englishQuery: glossary.toEnglish(query),
  });
}

// Plain-language label for each Covered Domain, used by the template framing.
const DOMAIN_LABEL: Record<ActType, string> = {
  criminal: "criminal law",
  consumer: "consumer protection law",
  ip: "intellectual property law",
  constitutional: "your fundamental rights",
  scheme: "government schemes",
  cyber: "cyber law",
  transport: "motor vehicle and traffic law",
  governance: "the right to information",
  protection: "protection from domestic violence and workplace harassment",
};

type LanguageCopy = {
  explanation: string;
  legalBasisLabel: string;
  nextStep: string;
  disclaimer: string;
};

// The per-language frame around the citation, kept court-traceable. The
// Legal-Aid Pointer (NALSA / DLSA) stays recognisable in every Disclaimer.
const COPY: Record<string, LanguageCopy> = {
  [HINDI]: {
    explanation:
      "सरल भाषा में, आपका प्रश्न भारत में {domain} से संबंधित है। नीचे बताया " +
      "गया है कि कानून स्वयं क्या कहता है, और उसके बाद वह सटीक प्रावधान दिया " +
      "गया है जिससे यह लिया गया है।",
    legalBasisLabel: "कानूनी आधार (Legal basis)",
    nextStep:
      "व्यावहारिक अगला कदम: ऊपर उद्धृत प्रावधान को पढ़ें, संबंधित दस्तावेज़ या " +
      "साक्ष्य संभाल कर रखें, और उसमें नामित उपयुक्त कार्यालय या प्राधिकरण से " +
      "संपर्क करें।",
    disclaimer:
      "यह कानूनी जानकारी है, कानूनी सलाह नहीं। अपनी विशिष्ट स्थिति में सहायता के " +
      "लिए किसी वकील या अपने निकटतम विधिक सेवा प्राधिकरण (NALSA / DLSA) से " +
      "संपर्क करें।",
  },
  [TAMIL]: {
    explanation:
      "எளிய மொழியில், உங்கள் கேள்வி இந்தியாவில் {domain} தொடர்பானது. சட்டம் " +
      "என்ன கூறுகிறது என்பது கீழே உள்ளது, அதைத் தொடர்ந்து அது எடுக்கப்பட்ட " +
      "சரியான விதி கொடுக்கப்பட்டுள்ளது.",
    legalBasisLabel: "சட்ட அடிப்படை (Legal basis)",
    nextStep:
      "நடைமுறை அடுத்த படி: மேலே மேற்கோள் காட்டப்பட்ட விதியைப் படியுங்கள், " +
      "தொடர்புடைய ஆவணங்கள் அல்லது சான்றுகளைப் பாதுகாப்பாக வைத்திருங்கள், அதில் " +
      "குறிப்பிடப்பட்ட பொருத்தமான அலுவலகம் அல்லது அதிகாரத்தை அணுகவும்.",
    disclaimer:
      "இது சட்டத் தகவல், சட்ட ஆலோசனை அல்ல. உங்கள் குறிப்பிட்ட சூழ்நிலையில் " +
      "உதவிக்கு, ஒரு வழக்கறிஞரை அல்லது உங்கள் அருகிலுள்ள சட்ட சேவை ஆணையத்தை " +
      "(NALSA / DLSA) அணுகவும்.",
  },
  [GUJARATI]: {
    explanation:
      "સરળ ભાષામાં, તમારો પ્રશ્ન ભારતમાં {domain} સંબંધિત છે. કાયદો પોતે શું " +
      "કહે છે તે નીચે આપેલ છે, ત્યારબાદ તે જે ચોક્કસ જોગવાઈમાંથી આવે છે તે " +
      "આપેલ છે.",
    legalBasisLabel: "કાનૂની આધાર (Legal basis)",
    nextStep:
      "વ્યવહારુ આગળનું પગલું: ઉપર ટાંકેલ જોગવાઈ વાંચો, સંબંધિત દસ્તાવેજો અથવા " +
      "પુરાવા સાચવી રાખો, અને તેમાં દર્શાવેલ યોગ્ય કચેરી અથવા સત્તાધિકારીનો " +
      "સંપર્ક કરો.",
    disclaimer:
      "આ કાનૂની માહિતી છે, કાનૂની સલાહ નથી. તમારી ચોક્કસ પરિસ્થિતિમાં મદદ માટે, " +
      "વકીલનો અથવા તમારી નજીકના કાનૂની સેવા સત્તામંડળ (NALSA / DLSA) નો સંપર્ક " +
      "કરો.",
  },
};

// Template generator that only ever cites the sections it was handed; answers
// in plain step-by-step language around a single focused Citation. The
// Citation Anchor stays verbatim English in every language.
export function templateGenerator(glossary: BilingualGlossary) {
  return async (
    _query: string,
    sections: RetrievedSection[],
    language: string,
  ): Promise<DraftAnswer> => {
    const top = sections[0];
    const citation: Citation = citationFromSection(top);
    const domainLabel =
      DOMAIN_LABEL[sectionProvenance(top).actType] ?? "the law";
    const copy = COPY[language];

    if (copy !== undefined) {
      const domain = glossary.render(domainLabel, language);
      return {
        explanation: copy.explanation.replace("{domain}", domain),
        legalBasis: `${copy.legalBasisLabel} - ${citationAnchor(citation)}`,
        nextStep: copy.nextStep,
        citations: [citation],
        disclaimer: copy.disclaimer,
      };
    }

    return {
      explanation:
        `In plain language, your question is about ${domainLabel} in India. ` +
        "Here is what the law itself says, followed by the exact provision it " +
        "comes from.",
      legalBasis: `Legal basis - ${citationAnchor(citation)}`,
      nextStep:
        "Practical next step: read the cited provision above, keep any " +
        "relevant documents or evidence, and approach the appropriate office " +
        "or authority named in it.",
      citations: [citation],
      disclaimer: DISCLAIMER,
    };
  };
}

// A full seam set wired entirely with deterministic doubles; any seam can be
// overridden per test.
export function offlineSeams(
  corpus: Chunk[],
  overrides: Partial<AssistantSeams> = {},
): AssistantSeams {
  const glossary = BilingualGlossary.load();
  return {
    retrieve: inMemoryRetriever(corpus),
    sectionMembers: inMemorySectionMembers(corpus.filter(isLoadable)),
    generator: templateGenerator(glossary),
    intentExtractor: glossaryIntentExtractor(glossary),
    ...overrides,
  };
}

export function offlineAnswer(
  corpus: Chunk[],
  query: string,
  language = "en",
  overrides: Partial<AssistantSeams> = {},
): Promise<GroundedAnswer> {
  return answerSeam(query, language, offlineSeams(corpus, overrides));
}

export function offlineConversation(
  corpus: Chunk[],
  overrides: Partial<AssistantSeams> = {},
): Conversation {
  return new Conversation(offlineSeams(corpus, overrides));
}
