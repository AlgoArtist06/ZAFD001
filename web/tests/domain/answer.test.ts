// Ports tests/test_answer.py: the grounded answer seam end to end over the
// offline fixture corpus and deterministic doubles.
import { beforeAll, describe, expect, it } from "vitest";

import { answerText, REFUSAL_TEXT } from "../../convex/lib/answer";
import { citationReference } from "../../convex/citations";
import { type Chunk } from "../../convex/lib/models";
import { buildCorpus } from "../helpers/corpus";
import { offlineAnswer } from "../helpers/doubles";

let corpus: Chunk[];
beforeAll(() => {
  corpus = buildCorpus();
});

describe("the grounded answer seam", () => {
  it("answers a supported English citizen query with citations", async () => {
    const result = await offlineAnswer(corpus, "What is the punishment for theft of movable property?");
    expect(result.refused).toBe(false);
    expect(result.citations.length).toBeGreaterThan(0);
    expect(result.citations.some((c) => c.sectionNumber === "303")).toBe(true);
  });

  it("refuses an unsupported query instead of guessing", async () => {
    const result = await offlineAnswer(
      corpus,
      "What is the best recipe for biryani?",
    );
    expect(result.refused).toBe(true);
    expect(result.citations).toEqual([]);
    expect(result.explanation).toBe(REFUSAL_TEXT);
  });

  it("backs every citation with a provenance record", async () => {
    const result = await offlineAnswer(corpus, "theft of property");
    expect(result.citations.length).toBeGreaterThan(0);
    for (const citation of result.citations) {
      expect(citation.actName).toBeTruthy();
      expect(citation.actYear).toBeTruthy();
      expect(citation.sectionNumber).toBeTruthy();
      expect(citation.sourceUrl).toBeTruthy();
      expect(citation.verbatimText).toBeTruthy();
    }
  });

  it("shows the citation anchor verbatim in English", async () => {
    const result = await offlineAnswer(corpus, "theft of property");
    const citation = result.citations[0];
    expect(citation.verbatimText).toContain(
      "intending to take dishonestly any movable property",
    );
    expect(answerText(result)).toContain(citation.verbatimText);
  });

  it("normalises an old IPC number and grounds in the current BNS", async () => {
    const result = await offlineAnswer(corpus, "What is the punishment under IPC 420?");
    expect(result.refused).toBe(false);
    expect(
      result.citations.some((c) => c.actId === "bns" && c.sectionNumber === "318"),
    ).toBe(true);
  });

  it("annotates the old IPC number but never cites it as a source", async () => {
    const result = await offlineAnswer(corpus, "What is the punishment under IPC 420?");
    const text = answerText(result);
    expect(text).toContain("formerly IPC 420");
    expect(result.citations.every((c) => c.actId === "bns")).toBe(true);
    expect(result.citations.every((c) => c.sectionNumber !== "420")).toBe(true);
  });

  it("carries no annotation without an IPC reference", async () => {
    const result = await offlineAnswer(corpus, "theft of property");
    expect(answerText(result)).not.toContain("formerly IPC");
  });

  it("uses the structured format in order", async () => {
    const result = await offlineAnswer(corpus, "theft of property");
    const text = answerText(result);
    expect(result.explanation).toContain("In plain language");
    expect(result.legalBasis).toContain("Legal basis");
    expect(result.legalBasis).toContain(citationReference(result.citations[0]));
    expect(result.nextStep).toContain("Practical next step");
    expect(text.indexOf(result.explanation)).toBeLessThan(
      text.indexOf(result.legalBasis),
    );
    expect(text.indexOf(result.legalBasis)).toBeLessThan(
      text.indexOf(result.nextStep),
    );
  });
});
