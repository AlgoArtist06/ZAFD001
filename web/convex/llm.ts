"use node";
// Live LLM adapters (generation + intent extraction) over the same
// OpenAI-compatible /chat/completions contract as rag/infrastructure/llm.py,
// with the same prompts, JSON object response format, token budget, and
// one-retry policy - plus the answerQuestion pipeline action that wires the
// whole grounded answer seam over Convex.
//
// ADR 0010: everything here calls validateLLMConfigured() before any work.
// No key, no answer - a missing provider surfaces to the user as a service
// configuration error, never an ungrounded legal response.
import { v, type Infer } from "convex/values";

import { internal } from "./_generated/api";
import { internalAction } from "./_generated/server";
import { type ActionCtx } from "./_generated/server";
import {
  citationFromSection,
  citationReference,
  type Citation,
} from "./citations";
import { validateLLMConfigured, type LLMConfig } from "./config";
import { embeddingConfig, embedQuery } from "./embeddings";
import {
  answerText,
  finalize,
  prepare,
  type AssistantSeams,
  type GroundedAnswer,
} from "./lib/answer";
import {
  sectionVerbatimText,
  sectionProvenance,
  type RetrievedSection,
} from "./lib/expansion";
import { DISCLAIMER, type DraftAnswer } from "./lib/generation";
import {
  BilingualGlossary,
  detectLanguage,
  ENGLISH,
  hasForeignScript,
  type NormalizedQuery,
} from "./lib/multilingual";
import { convexRetrieve, convexSectionMembers } from "./retrieval";
import { type streamFieldsValidator } from "./schema";

type StreamFields = Infer<typeof streamFieldsValidator>;

const GENERATION_SYSTEM_PROMPT =
  "Return JSON with explanation, legal_basis, next_step, and " +
  "citations. Answer only from the supplied sources. End every " +
  "legal claim with its exact Act (year), Section citation. " +
  "citations must be a list of act_id and section_number pairs " +
  "from the supplied sources. If the sources do not answer the " +
  "question, return empty strings and an empty citations list. " +
  "Do not give personalised legal advice.";

// A failed model call is a SERVICE problem, not a legal Refusal: the answer
// says so in the user's language, and the turn is never persisted.
const SERVICE_ERROR: Record<string, string> = {
  en:
    "The assistant could not reach its language model just now, so this " +
    "question was not answered. Please try again in a moment.",
  hi:
    "सहायक अभी अपने भाषा मॉडल से संपर्क नहीं कर सका, इसलिए इस प्रश्न का उत्तर " +
    "नहीं दिया गया। कृपया थोड़ी देर में फिर से प्रयास करें।",
  ta:
    "உதவியாளரால் இப்போது அதன் மொழி மாதிரியை அணுக முடியவில்லை, எனவே இந்தக் " +
    "கேள்விக்கு பதில் அளிக்கப்படவில்லை. சிறிது நேரத்தில் மீண்டும் முயற்சிக்கவும்.",
  gu:
    "સહાયક હમણાં તેના ભાષા મોડેલ સુધી પહોંચી શક્યો નથી, તેથી આ પ્રશ્નનો જવાબ " +
    "આપવામાં આવ્યો નથી. કૃપા કરીને થોડી વારમાં ફરી પ્રયાસ કરો.",
};

// Coerce a model-returned field to text: the JSON contract asks for strings,
// but a model sometimes returns a list of lines (or null). Normalise at the
// untrusted-output boundary rather than crash.
function asText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(asText).join("\n");
  return String(value);
}

// POST a chat-completions request, with one retry on transport failure or a
// 5xx; a 4xx is the caller's bug and propagates immediately.
async function postChat(
  config: LLMConfig,
  payload: Record<string, unknown>,
): Promise<{ choices: Array<{ message: { content: string } }> }> {
  const url = `${config.baseUrl.replace(/\/+$/, "")}/chat/completions`;
  for (let attempt = 1; ; attempt++) {
    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${config.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      if (attempt === 2) throw error;
      continue;
    }
    if (response.status >= 500 && attempt === 1) continue;
    if (!response.ok) {
      throw new Error(
        `llm request failed: ${response.status} ${await response.text()}`,
      );
    }
    return (await response.json()) as {
      choices: Array<{ message: { content: string } }>;
    };
  }
}

// Incrementally extracts the "explanation" string from a growing JSON prefix,
// stopping cleanly before an incomplete escape sequence - so the explanation
// surfaces token by token while the citations are still on the wire. Port of
// _ExplanationScanner.
export class ExplanationScanner {
  private buffer = "";
  private valueStart: number | null = null;
  private static KEY = '"explanation"';

  feed(text: string): string | null {
    this.buffer += text;
    const start = this.findValueStart();
    if (start === null) return null;
    return this.decodeFrom(start);
  }

  private findValueStart(): number | null {
    if (this.valueStart !== null) return this.valueStart;
    const key = this.buffer.indexOf(ExplanationScanner.KEY);
    if (key < 0) return null;
    let i = key + ExplanationScanner.KEY.length;
    while (i < this.buffer.length && " \t\r\n:".includes(this.buffer[i])) i++;
    if (i >= this.buffer.length || this.buffer[i] !== '"') return null;
    this.valueStart = i + 1;
    return this.valueStart;
  }

  private decodeFrom(start: number): string {
    const out: string[] = [];
    let i = start;
    const buf = this.buffer;
    const simple: Record<string, string> = {
      n: "\n",
      t: "\t",
      r: "\r",
      b: "\b",
      f: "\f",
    };
    while (i < buf.length) {
      const ch = buf[i];
      if (ch === '"') return out.join("");
      if (ch !== "\\") {
        out.push(ch);
        i += 1;
        continue;
      }
      // An escape sequence: only consume it when it is complete.
      if (i + 1 >= buf.length) break;
      const esc = buf[i + 1];
      if (esc === "u") {
        if (i + 6 > buf.length) break;
        out.push(String.fromCharCode(parseInt(buf.slice(i + 2, i + 6), 16)));
        i += 6;
      } else {
        out.push(simple[esc] ?? esc);
        i += 2;
      }
    }
    return out.join("");
  }
}

function generationPayload(
  config: LLMConfig,
  query: string,
  sections: RetrievedSection[],
  language: string,
): Record<string, unknown> {
  const sources = sections.map((section) => {
    const provenance = sectionProvenance(section);
    return {
      act_id: section.actId,
      act_name: provenance.actName,
      act_year: provenance.actYear,
      section_number: section.sectionNumber,
      source_url: provenance.sourceUrl,
      verbatim_text: sectionVerbatimText(section),
    };
  });
  return {
    model: config.model,
    response_format: { type: "json_object" },
    // Explicit budget: gateway defaults can be tiny, and a reasoning model
    // spends tokens thinking before the JSON - a "length" cutoff mid-object
    // would otherwise kill every long grounded answer.
    max_tokens: 4096,
    messages: [
      { role: "system", content: GENERATION_SYSTEM_PROMPT },
      { role: "user", content: JSON.stringify({ query, language, sources }) },
    ],
  };
}

function draftFromContent(
  content: Record<string, unknown>,
  sections: RetrievedSection[],
): DraftAnswer {
  const bySection = new Map(
    sections.map((section) => [
      `${section.actId} ${section.sectionNumber}`,
      section,
    ]),
  );
  const citations: Citation[] = [];
  for (const item of (content.citations as Array<Record<string, unknown>>) ?? []) {
    const actId = String(item.act_id ?? "");
    const sectionNumber = String(item.section_number ?? "");
    const section = bySection.get(`${actId} ${sectionNumber}`);
    citations.push(
      section
        ? citationFromSection(section)
        : {
            actId,
            actName: "",
            actYear: 0,
            sectionNumber,
            verbatimText: "",
            sourceUrl: "",
          },
    );
  }
  return {
    explanation: asText(content.explanation),
    legalBasis: asText(content.legal_basis),
    nextStep: asText(content.next_step),
    citations,
    disclaimer: DISCLAIMER,
  };
}

// Generate a grounded draft. With `onExplanation` the provider's SSE stream
// is consumed and the growing explanation surfaced; the fully accumulated
// body is parsed at the end for the citations, so the streaming and
// non-streaming paths share one output contract.
export async function generateDraft(
  config: LLMConfig,
  query: string,
  sections: RetrievedSection[],
  language: string,
  onExplanation?: (textSoFar: string) => Promise<void>,
): Promise<DraftAnswer> {
  if (onExplanation === undefined) {
    const completion = await postChat(
      config,
      generationPayload(config, query, sections, language),
    );
    const content = JSON.parse(completion.choices[0].message.content);
    return draftFromContent(content, sections);
  }

  const payload = generationPayload(config, query, sections, language);
  payload.stream = true;
  const url = `${config.baseUrl.replace(/\/+$/, "")}/chat/completions`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok || response.body === null) {
    throw new Error(`llm stream failed: ${response.status}`);
  }

  const scanner = new ExplanationScanner();
  let body = "";
  let lastSent = "";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline !== -1) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
      // Some gateways signal failure as an SSE error event on a 200 stream.
      if (line.startsWith("event:") && line.includes("error")) {
        throw new Error(`llm stream error event: ${line}`);
      }
      if (!line.startsWith("data:")) continue;
      const data = line.slice("data:".length).trim();
      if (!data || data === "[DONE]") continue;
      let piece = "";
      try {
        const delta = JSON.parse(data).choices[0].delta;
        piece = delta.content ?? "";
      } catch {
        continue;
      }
      if (!piece) continue;
      body += piece;
      const explanation = scanner.feed(piece);
      if (explanation && explanation !== lastSent) {
        lastSent = explanation;
        await onExplanation(explanation);
      }
    }
  }
  if (!body) throw new Error("llm stream ended without any content");
  return draftFromContent(JSON.parse(body), sections);
}

// Normalise a query to English through the LLM, with the Bilingual Legal
// Glossary's terms injected as hard constraints - the curated glossary, not
// the model, fixes the terminology. A pure-English query never reaches the
// model; a response without a rewritten query is an error (ADR 0010).
export async function extractIntent(
  config: LLMConfig,
  glossary: BilingualGlossary,
  query: string,
): Promise<NormalizedQuery> {
  if (!hasForeignScript(query)) {
    return { language: ENGLISH, englishQuery: query };
  }
  const language = detectLanguage(query);
  const completion = await postChat(config, {
    model: config.model,
    response_format: { type: "json_object" },
    max_tokens: 4096,
    messages: [
      {
        role: "system",
        content:
          "Normalise a user's legal question for retrieval over an " +
          "English statute corpus. Detect the language, extract the " +
          "intent, and rewrite the question in English. Preserve " +
          "legal terms, map lay complaints to legal concepts, and " +
          "keep any Latin-script words already in English " +
          "(code-mixing). For each listed legal concept you must " +
          "use exactly the supplied English term. Return JSON with " +
          "language (an ISO 639-1 code) and english_query.",
      },
      {
        role: "user",
        content: JSON.stringify({
          query,
          term_constraints: glossary.constraintsFor(language),
        }),
      },
    ],
  });
  const content = JSON.parse(completion.choices[0].message.content);
  const englishQuery = content.english_query;
  if (!englishQuery) {
    throw new Error("intent extraction returned no english_query");
  }
  return { language: content.language || language, englishQuery };
}

// The wire form of an answer's citations, as persisted and streamed.
function wireCitations(result: GroundedAnswer) {
  return result.citations.map((c) => ({
    reference: citationReference(c),
    verbatim: c.verbatimText,
    url: c.sourceUrl,
  }));
}

// A GroundedAnswer as the stream document's fields - the port of
// rag/services/frames.py answer_frames.
function structuredFields(result: GroundedAnswer) {
  return {
    state: result.refused
      ? ("refusal" as const)
      : result.highStakes
        ? ("emergency" as const)
        : ("normal" as const),
    language: result.language,
    reason: result.refused ? result.refusalReason : undefined,
    highStakesNotice: result.highStakesNotice || undefined,
    explanation: result.explanation,
    citations: wireCitations(result),
    note: result.formerIpcNote || undefined,
    nextStep: result.nextStep || undefined,
    disclaimer: result.disclaimer || undefined,
  };
}

export function productionSeams(ctx: ActionCtx): AssistantSeams {
  const llm = validateLLMConfigured();
  const embedding = embeddingConfig();
  const glossary = BilingualGlossary.load();
  return {
    retrieve: async (query, domains) => {
      // Runtime embeds ONLY the query - never corpus text (see documents.ts).
      const queryVector = await embedQuery(query, embedding);
      return convexRetrieve(ctx, query, domains, queryVector);
    },
    sectionMembers: (actId, sectionNumber) =>
      convexSectionMembers(ctx, actId, sectionNumber),
    generator: (query, sections, language) =>
      generateDraft(llm, query, sections, language),
    intentExtractor: (query) => extractIntent(llm, glossary, query),
  };
}

// The pipeline behind one question: prepare (normalize, screen, retrieve,
// gate, expand) -> generate with streaming -> verify citations -> persist ->
// finish the stream document. Scheduled by the `ask` mutation, which already
// authenticated the user, checked consent, and resolved follow-up context.
export const runAnswer = internalAction({
  args: {
    streamId: v.id("streams"),
    userId: v.string(),
    conversationId: v.optional(v.id("conversations")),
    query: v.string(),
    resolved: v.string(),
    language: v.string(),
  },
  handler: async (ctx, args) => {
    const finish = (fields: StreamFields) =>
      ctx.runMutation(internal.chat.finishStream, {
        streamId: args.streamId,
        fields,
      });
    const serviceError = (language: string, error: unknown) => {
      const name = error instanceof Error ? error.constructor.name : "Error";
      const message = error instanceof Error ? error.message : String(error);
      return finish({
        state: "error",
        language,
        detail: `${name}: ${message}`.trim().replace(/:$/, ""),
        explanation: SERVICE_ERROR[language] ?? SERVICE_ERROR.en,
      });
    };

    let prepared;
    try {
      // Seam construction validates configuration (ADR 0010): a missing LLM
      // or embedding credential surfaces to the user as a service
      // configuration error here, never as silence or an ungrounded answer.
      const seams = productionSeams(ctx);
      prepared = await prepare(args.resolved, args.language, seams);
    } catch (error) {
      // Configuration, intent extraction, embedding, and retrieval failures
      // are service problems, surfaced as such - never a fake Refusal.
      await serviceError(args.language, error);
      return;
    }

    const persist = async (result: GroundedAnswer) => {
      result.query = args.query;
      if (args.conversationId !== undefined) {
        await ctx.runMutation(internal.chat.persistTurn, {
          userId: args.userId,
          conversationId: args.conversationId,
          query: args.query,
          resolved: args.resolved,
          answer: answerText(result),
          refused: result.refused,
          citations: wireCitations(result),
        });
      }
    };

    if (!("kind" in prepared)) {
      // A pre-generation decision (Confirmation, advice Refusal, ungrounded
      // Refusal) streams as the complete answer it already is.
      await persist(prepared);
      await finish(structuredFields(prepared));
      return;
    }

    // True streaming: the state is known before generation, so meta leads
    // immediately and the explanation grows as the model produces it.
    await ctx.runMutation(internal.chat.updateStream, {
      streamId: args.streamId,
      fields: {
        state: prepared.highStakes ? "emergency" : "normal",
        language: prepared.language,
        highStakesNotice: prepared.notice || undefined,
      },
    });

    const llm = validateLLMConfigured();
    // Throttled cumulative explanation updates: each write REPLACES the
    // explanation client-side, so a whole retry is invisible to the user.
    let lastWrite = 0;
    const onExplanation = async (textSoFar: string) => {
      const now = Date.now();
      if (now - lastWrite < 250) return;
      lastWrite = now;
      await ctx.runMutation(internal.chat.updateStream, {
        streamId: args.streamId,
        fields: { explanation: textSoFar },
      });
    };

    let draft: DraftAnswer | null = null;
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        draft = await generateDraft(
          llm,
          prepared.englishQuery,
          prepared.sections,
          prepared.language,
          onExplanation,
        );
        break;
      } catch (error) {
        if (attempt === 2) {
          await serviceError(prepared.language, error);
          return;
        }
      }
    }

    // Nothing past this point may leave the stream document unfinished: a
    // stuck done:false row would block the user's composer forever, so any
    // unexpected failure still finishes it as a service error.
    try {
      const result = finalize(prepared, draft!);
      await persist(result);
      // The authoritative post-softening, post-verification answer replaces
      // whatever streamed - including a late refusal when citation
      // verification stripped everything.
      await finish(structuredFields(result));
    } catch (error) {
      await serviceError(prepared.language, error);
    }
  },
});
