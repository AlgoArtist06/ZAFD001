// Ports tests/test_multilingual.py and test_multilingual_tamil_gujarati.py:
// script detection, glossary normalisation, answering in the user's language
// with the Citation Anchor verbatim in English, and the Confirmation Step.
import { beforeAll, describe, expect, it } from "vitest";

import { answerText } from "../../convex/lib/answer";
import {
  BilingualGlossary,
  confirmationFor,
  detectLanguage,
  hasForeignScript,
} from "../../convex/lib/multilingual";
import { type Chunk } from "../../convex/lib/models";
import { buildCorpus } from "../helpers/corpus";
import { offlineAnswer } from "../helpers/doubles";

let corpus: Chunk[];
let glossary: BilingualGlossary;
beforeAll(() => {
  corpus = buildCorpus();
  glossary = BilingualGlossary.load();
});

describe("language detection", () => {
  it("distinguishes each supported script from English", () => {
    expect(detectLanguage("What happens if someone steals my phone?")).toBe("en");
    expect(detectLanguage("चोरी की सजा क्या है?")).toBe("hi");
    expect(detectLanguage("திருட்டுக்கான தண்டனை என்ன?")).toBe("ta");
    expect(detectLanguage("ચોરીની સજા શું છે?")).toBe("gu");
  });

  it("detects code-mixed queries by their script", () => {
    expect(detectLanguage("चोरी ho gayi, what is the punishment?")).toBe("hi");
    expect(hasForeignScript("pure English")).toBe(false);
  });
});

describe("glossary normalisation", () => {
  it("normalises a Hindi query to English preserving legal terms", () => {
    const english = glossary.toEnglish("चोरी की सजा क्या है?");
    expect(english).toContain("theft");
    expect(hasForeignScript(english)).toBe(false);
  });

  it("keeps Latin-script tokens in a code-mixed query", () => {
    const english = glossary.toEnglish("चोरी ho gayi, what is the punishment?");
    expect(english).toContain("theft");
    expect(english).toContain("punishment");
  });

  it("renders critical terms with English inline in brackets", () => {
    const rendered = glossary.render("theft", "hi");
    expect(rendered).toContain("(theft)");
  });
});

describe("multilingual answering", () => {
  const queries: Record<string, string> = {
    hi: "चोरी की सजा क्या है?",
    ta: "திருட்டுக்கான தண்டனை என்ன?",
    gu: "ચોરીની સજા શું છે?",
  };

  for (const [language, query] of Object.entries(queries)) {
    it(`answers a ${language} query over the English corpus in ${language}`, async () => {
      const result = await offlineAnswer(corpus, query);
      expect(result.refused).toBe(false);
      expect(result.language).toBe(language);
      expect(result.citations.some((c) => c.sectionNumber === "303")).toBe(true);
      // The Citation Anchor stays verbatim English inside the answer.
      expect(answerText(result)).toContain(
        "intending to take dishonestly any movable property",
      );
      // The disclaimer keeps the Legal-Aid Pointer recognisable.
      expect(answerText(result)).toContain("NALSA / DLSA");
    });
  }

  it("refuses in the user's language for an unsupported query", async () => {
    const result = await offlineAnswer(corpus, "मंगल ग्रह पर जमीन कैसे खरीदें?");
    expect(result.refused).toBe(true);
    expect(result.language).toBe("hi");
    expect(result.explanation).toContain("स्रोत");
  });
});

describe("the Confirmation Step", () => {
  it("fires for an ambiguous rights query", async () => {
    const result = await offlineAnswer(corpus, "What are my rights?");
    expect(result.needsConfirmation).toBe(true);
    expect(result.confirmation).toContain("fundamental rights");
    expect(result.confirmation).toContain("consumer rights");
    expect(result.refused).toBe(false);
  });

  it("only triggers on ambiguous-only queries", () => {
    expect(confirmationFor("What are my rights?")).not.toBeNull();
    expect(confirmationFor("What are my consumer rights on refunds?")).toBeNull();
    expect(confirmationFor("what is theft")).toBeNull();
  });

  it("asks the clarifying question in the user's language", () => {
    const hindi = confirmationFor("rights", "hi");
    expect(hindi).toContain("मौलिक अधिकार");
  });
});
