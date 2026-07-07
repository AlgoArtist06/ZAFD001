"use node";
// The gold-eval surface: run one gold-case turn through the REAL deployed
// pipeline (live LLM, live embeddings, the stored corpus). An operator tool
// for scripts/runGoldEval.ts, gated by the deployment's EVAL_KEY - not a
// user surface; persists nothing. Multi-turn cases are driven by the client,
// which threads each turn's `resolved` back in as `context`.
import { ConvexError, v } from "convex/values";

import { action } from "./_generated/server";
import { answer } from "./lib/answer";
import { rewriteFollowup } from "./lib/followup";
import { productionSeams } from "./llm";

export const answerGoldCase = action({
  args: {
    evalKey: v.string(),
    query: v.string(),
    language: v.string(),
    context: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    if (!process.env.EVAL_KEY || args.evalKey !== process.env.EVAL_KEY) {
      throw new ConvexError("Gold evaluation requires EVAL_KEY.");
    }
    const resolved = rewriteFollowup(args.query, args.context.slice(-4));
    const result = await answer(resolved, args.language, productionSeams(ctx));
    return {
      resolved,
      refused: result.refused,
      needsConfirmation: result.needsConfirmation,
      highStakes: result.highStakes,
      highStakesNotice: result.highStakesNotice,
      explanation: result.explanation,
      citations: result.citations.map(({ actId, sectionNumber }) => ({ actId, sectionNumber })),
    };
  },
});
