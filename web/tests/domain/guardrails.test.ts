// Ports tests/test_guardrails.py: the input-side scope contract, the
// output-side softener, High-Stakes Routing, and the always-present
// disclaimer with its Legal-Aid Pointer.
import { beforeAll, describe, expect, it } from "vitest";

import {
  ADVICE_REFUSAL_TEXT,
  HIGH_STAKES_NOTICE,
  screenRequest,
  softenAdvice,
} from "../../convex/guardrails";
import { answerText } from "../../convex/lib/answer";
import { type Chunk } from "../../convex/lib/models";
import { buildCorpus } from "../helpers/corpus";
import { offlineAnswer, templateGenerator } from "../helpers/doubles";
import { BilingualGlossary } from "../../convex/lib/multilingual";

let corpus: Chunk[];
beforeAll(() => {
  corpus = buildCorpus();
});

describe("input-side scope contract", () => {
  it("refuses an outcome-prediction request and redirects", async () => {
    const result = await offlineAnswer(corpus, "Will I win my theft case?");
    expect(result.refused).toBe(true);
    expect(result.refusalReason).toBe("advice");
    expect(result.explanation).toBe(ADVICE_REFUSAL_TEXT);
    expect(result.nextStep).toContain("NALSA / DLSA");
    expect(result.citations).toEqual([]);
  });

  it("refuses a personalised action request and redirects", async () => {
    const result = await offlineAnswer(corpus, "Should I sue my landlord?");
    expect(result.refused).toBe(true);
    expect(result.refusalReason).toBe("advice");
    expect(result.nextStep).toContain("NALSA / DLSA");
  });

  it("classifies markers case-insensitively", () => {
    expect(screenRequest("WILL I WIN my case?").kind).toBe("advice");
    expect(screenRequest("what is theft").kind).toBe("answerable");
  });
});

describe("output-side softener", () => {
  it("softens advice phrasing", () => {
    const softened = softenAdvice(
      "You should sue them immediately and you will win in court.",
    );
    expect(softened.toLowerCase()).not.toContain("you should sue");
    expect(softened.toLowerCase()).not.toContain("you will win");
    expect(softened).toContain("decided by the court");
  });

  it("softens advice phrasing that slips into a draft", async () => {
    const glossary = BilingualGlossary.load();
    const base = templateGenerator(glossary);
    const result = await offlineAnswer(
      corpus,
      "theft of movable property",
      "en",
      {
        generator: async (query, sections, language) => {
          const draft = await base(query, sections, language);
          return {
            ...draft,
            explanation: "You should sue the thief immediately. " + draft.explanation,
          };
        },
      },
    );
    expect(result.refused).toBe(false);
    expect(result.explanation.toLowerCase()).not.toContain("you should sue");
  });
});

describe("High-Stakes Routing", () => {
  it("leads with emergency and legal-aid contacts", async () => {
    const result = await offlineAnswer(
      corpus,
      "My husband is beating me right now, this is domestic violence, what can the police do?",
    );
    expect(result.highStakes).toBe(true);
    expect(result.highStakesNotice).toBe(HIGH_STAKES_NOTICE);
    const text = answerText(result);
    expect(text.indexOf("112")).toBeLessThan(text.indexOf(result.explanation));
    expect(text).toContain("NALSA / DLSA");
  });

  it("does not flag an ordinary query", async () => {
    const result = await offlineAnswer(corpus, "theft of property");
    expect(result.highStakes).toBe(false);
    expect(result.highStakesNotice).toBe("");
  });
});

describe("the disclaimer", () => {
  it("carries a Legal-Aid Pointer on every answer path", async () => {
    for (const query of [
      "theft of property", // grounded answer
      "What is the best recipe for biryani?", // refusal
      "Will I win my theft case?", // advice refusal
    ]) {
      const result = await offlineAnswer(corpus, query);
      expect(answerText(result)).toContain("NALSA / DLSA");
    }
  });
});
