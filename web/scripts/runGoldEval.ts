import { ConvexHttpClient } from "convex/browser";

import { api } from "../convex/_generated/api";
import { loadEnvLocal } from "./lib/env";
import {
  judgeGoldCase,
  loadGoldCases,
  reportTotals,
  SUPPORTED_LANGUAGES,
  type EvalAnswer,
  type GoldCase,
} from "./lib/eval";

async function answerCase(client: ConvexHttpClient, evalKey: string, goldCase: GoldCase): Promise<EvalAnswer> {
  const context: string[] = [];
  let result: EvalAnswer & { resolved: string } | undefined;
  for (const query of goldCase.turns.length ? goldCase.turns : [goldCase.query]) {
    result = await client.action(api.eval.answerGoldCase, {
      evalKey,
      query,
      language: goldCase.language,
      context,
    });
    context.push(result.resolved);
  }
  return result!;
}

async function main(): Promise<void> {
  loadEnvLocal(new URL("..", import.meta.url).pathname);
  const url = process.env.CONVEX_URL ?? process.env.NEXT_PUBLIC_CONVEX_URL;
  const evalKey = process.env.EVAL_KEY;
  if (!url || !evalKey) throw new Error("CONVEX_URL/NEXT_PUBLIC_CONVEX_URL and EVAL_KEY are required");
  const client = new ConvexHttpClient(url);
  let failed = false;
  for (const language of SUPPORTED_LANGUAGES) {
    const results = [];
    for (const goldCase of loadGoldCases(language)) {
      results.push(judgeGoldCase(goldCase, await answerCase(client, evalKey, goldCase)));
    }
    const totals = reportTotals({ results });
    const passed = totals.total > 0 && totals.passed === totals.total;
    failed ||= !passed;
    console.log(`${language}: ${totals.passed}/${totals.total}${passed ? " PASS" : " FAIL"}`);
    for (const result of results.filter((item) => !item.passed)) console.log(`  ${result.case.id}: ${result.detail}`);
  }
  if (failed) process.exitCode = 1;
}

await main();
