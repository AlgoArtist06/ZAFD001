// Ports tests/test_eval.py: the gold evaluation set is the test suite at the
// answer seam. Every case in every Supported Language must hold against the
// offline fixture corpus - the accuracy bar is total correctness.
import { beforeAll, describe, expect, it } from "vitest";

import { type Chunk } from "../../convex/lib/models";
import {
  ACCURACY_BAR,
  judgeGoldCase,
  loadGoldCases,
  reportTotals,
  runFinalEval,
  runGoldEval,
  SUPPORTED_LANGUAGES,
} from "../../scripts/lib/eval";
import { buildCorpus } from "../helpers/corpus";
import { offlineSeams } from "../helpers/doubles";

let corpus: Chunk[];
beforeAll(() => {
  corpus = buildCorpus();
});

describe("the gold evaluation set", () => {
  it("judges a deployed answer using the same citation contract", () => {
    const goldCase = loadGoldCases("en").find((item) => item.expectedSection)!;
    expect(judgeGoldCase(goldCase, {
      refused: false,
      needsConfirmation: false,
      highStakes: false,
      highStakesNotice: "",
      explanation: "grounded",
      citations: [{ actId: goldCase.expectedActId ?? "bns", sectionNumber: goldCase.expectedSection! }],
    }).passed).toBe(true);
  });
  it("has a non-empty English subset covering citations and refusals", () => {
    const cases = loadGoldCases("en");
    expect(cases.length).toBeGreaterThan(0);
    expect(cases.some((c) => c.expectedSection)).toBe(true);
    expect(cases.some((c) => c.expectRefusal)).toBe(true);
  });

  it("holds on every English case", async () => {
    const report = await runGoldEval(offlineSeams(corpus), loadGoldCases("en"));
    const { total, passed, failures } = reportTotals(report);
    expect(failures).toEqual([]);
    expect(passed).toBe(total);
  });

  it("resolves the old-IPC-number gold case to the current BNS", async () => {
    const cases = loadGoldCases("en").filter((c) =>
      c.query.toLowerCase().includes("ipc"),
    );
    expect(cases.length).toBeGreaterThan(0);
    const report = await runGoldEval(offlineSeams(corpus), cases);
    expect(reportTotals(report).failures).toEqual([]);
  });

  it("covers every supported language with a non-empty subset", async () => {
    const report = await runFinalEval(offlineSeams(corpus));
    expect(Object.keys(report.byLanguage).sort()).toEqual(
      [...SUPPORTED_LANGUAGES].sort(),
    );
    for (const language of SUPPORTED_LANGUAGES) {
      expect(report.byLanguage[language].report.results.length).toBeGreaterThan(0);
    }
  });

  it("meets the accuracy bar for each language", async () => {
    const report = await runFinalEval(offlineSeams(corpus));
    for (const language of SUPPORTED_LANGUAGES) {
      const result = report.byLanguage[language];
      expect(
        result.meetsBar,
        `${language} accuracy ${result.accuracy}: ` +
          JSON.stringify(
            result.report.results.filter((r) => !r.passed).map((r) => r.detail),
          ),
      ).toBe(true);
    }
    expect(report.passed).toBe(true);
    expect(ACCURACY_BAR).toBe(1.0);
  });

  it("fails the whole pass when any language regresses", async () => {
    const bogus = [
      {
        id: "bogus",
        query: "मंगल ग्रह पर जमीन कैसे खरीदें?",
        language: "ta",
        expectedSection: "1",
        expectRefusal: false,
        expectHighStakes: false,
        expectConfirmation: false,
        turns: [],
      },
    ];
    const report = await runFinalEval(offlineSeams(corpus), 1.0, { ta: bogus });
    expect(report.byLanguage["ta"].meetsBar).toBe(false);
    expect(report.passed).toBe(false);
  });
});
