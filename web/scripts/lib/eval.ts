// The gold eval harness, ported from rag/services/eval.py. Each gold case is
// hand-verified against the bare-act text and asserts either that the correct
// section is cited or that a Refusal / Confirmation / High-Stakes behavior
// fires. Cases carry a language, so the same harness serves the per-language
// subsets; the final pass holds only when every Supported Language clears the
// accuracy bar on a non-empty subset.
import { readFileSync } from "node:fs";

import { dataPath } from "./repo";

import {
  answer,
  Conversation,
  type AssistantSeams,
  type GroundedAnswer,
} from "../../convex/lib/answer";

export const SUPPORTED_LANGUAGES = ["en", "hi", "ta", "gu"] as const;

// The curated subsets are hand-verified to hold completely, so the bar is
// total correctness; a single regression in any language fails the pass.
export const ACCURACY_BAR = 1.0;

const GOLD_PATH = dataPath("eval", "seam2_gold.json");

export type GoldCase = {
  id: string;
  query: string;
  language: string;
  expectedActId?: string;
  expectedSection?: string;
  expectRefusal: boolean;
  expectHighStakes: boolean;
  expectConfirmation: boolean;
  turns: string[];
};

export type CaseResult = {
  case: GoldCase;
  passed: boolean;
  detail: string;
};

export type EvalAnswer = {
  refused: boolean;
  needsConfirmation: boolean;
  highStakes: boolean;
  highStakesNotice: string;
  explanation: string;
  citations: Array<{ actId: string; sectionNumber: string }>;
};

export type EvalReport = {
  results: CaseResult[];
};

export function reportTotals(report: EvalReport) {
  const passed = report.results.filter((r) => r.passed).length;
  return {
    total: report.results.length,
    passed,
    failures: report.results.filter((r) => !r.passed).map((r) => r.case),
  };
}

type RawGoldCase = {
  id: string;
  query: string;
  language?: string;
  expected_act_id?: string;
  expected_section?: string;
  expect_refusal?: boolean;
  expect_high_stakes?: boolean;
  expect_confirmation?: boolean;
  turns?: string[];
};

export function loadGoldCases(
  language?: string,
  path: string = GOLD_PATH,
): GoldCase[] {
  const raw = JSON.parse(readFileSync(path, "utf8")) as { cases: RawGoldCase[] };
  const cases = raw.cases.map((entry) => ({
    id: entry.id,
    query: entry.query,
    language: entry.language ?? "en",
    expectedActId: entry.expected_act_id,
    expectedSection: entry.expected_section,
    expectRefusal: entry.expect_refusal ?? false,
    expectHighStakes: entry.expect_high_stakes ?? false,
    expectConfirmation: entry.expect_confirmation ?? false,
    turns: entry.turns ?? [],
  }));
  return language === undefined
    ? cases
    : cases.filter((c) => c.language === language);
}

// A multi-turn case runs through one Conversation - so a dependent follow-up
// resolves against the earlier turns - and is judged on its final turn.
async function answerCase(
  goldCase: GoldCase,
  seams: AssistantSeams,
): Promise<GroundedAnswer> {
  if (goldCase.turns.length > 0) {
    const conversation = new Conversation(seams);
    let result: GroundedAnswer | null = null;
    for (const turn of goldCase.turns) {
      result = await conversation.ask(turn, goldCase.language);
    }
    return result!;
  }
  return answer(goldCase.query, goldCase.language, seams);
}

export function judgeGoldCase(
  goldCase: GoldCase,
  result: EvalAnswer,
): CaseResult {
  if (goldCase.expectHighStakes) {
    const leads =
      result.highStakes &&
      result.highStakesNotice.includes("112");
    return {
      case: goldCase,
      passed: leads,
      detail: leads
        ? "led with emergency contacts as expected"
        : "expected High-Stakes Routing leading with emergency contacts",
    };
  }

  if (goldCase.expectConfirmation) {
    return {
      case: goldCase,
      passed: result.needsConfirmation,
      detail: result.needsConfirmation
        ? "posed a Confirmation Step as expected"
        : "expected a Confirmation Step, got a direct answer",
    };
  }

  if (goldCase.expectRefusal) {
    return {
      case: goldCase,
      passed: result.refused,
      detail: result.refused
        ? "refused as expected"
        : "expected a Refusal, got an answer",
    };
  }

  if (result.refused) {
    return {
      case: goldCase,
      passed: false,
      detail: "expected a cited answer, got a Refusal",
    };
  }

  const cited = result.citations.some(
    (c) =>
      c.sectionNumber === goldCase.expectedSection &&
      (goldCase.expectedActId === undefined || c.actId === goldCase.expectedActId),
  );
  return {
    case: goldCase,
    passed: cited,
    detail: cited
      ? `cited section ${goldCase.expectedSection}`
      : `expected section ${goldCase.expectedSection}, got ` +
        JSON.stringify(result.citations.map((c) => [c.actId, c.sectionNumber])),
  };
}

async function evaluate(
  goldCase: GoldCase,
  seams: AssistantSeams,
): Promise<CaseResult> {
  return judgeGoldCase(goldCase, await answerCase(goldCase, seams));
}

export async function runGoldEval(
  seams: AssistantSeams,
  cases: GoldCase[],
): Promise<EvalReport> {
  const results: CaseResult[] = [];
  for (const goldCase of cases) {
    results.push(await evaluate(goldCase, seams));
  }
  return { results };
}

export type LanguageEvalResult = {
  language: string;
  report: EvalReport;
  accuracy: number;
  meetsBar: boolean;
};

export type FinalEvalReport = {
  byLanguage: Record<string, LanguageEvalResult>;
  passed: boolean;
};

// Run the gold eval for every Supported Language and check the accuracy bar.
// The whole pass holds only when each language clears it on a non-empty set.
export async function runFinalEval(
  seams: AssistantSeams,
  bar: number = ACCURACY_BAR,
  casesByLanguage?: Record<string, GoldCase[]>,
): Promise<FinalEvalReport> {
  const byLanguage: Record<string, LanguageEvalResult> = {};
  for (const language of SUPPORTED_LANGUAGES) {
    const cases = casesByLanguage?.[language] ?? loadGoldCases(language);
    const report = await runGoldEval(seams, cases);
    const { total, passed } = reportTotals(report);
    const accuracy = total > 0 ? passed / total : 0;
    byLanguage[language] = {
      language,
      report,
      accuracy,
      meetsBar: total > 0 && accuracy >= bar,
    };
  }
  return {
    byLanguage,
    passed:
      Object.keys(byLanguage).length > 0 &&
      Object.values(byLanguage).every((r) => r.meetsBar),
  };
}
