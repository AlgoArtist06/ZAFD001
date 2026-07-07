/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as chat from "../chat.js";
import type * as citations from "../citations.js";
import type * as config from "../config.js";
import type * as documents from "../documents.js";
import type * as embeddings from "../embeddings.js";
import type * as eval from "../eval.js";
import type * as guardrails from "../guardrails.js";
import type * as lib_answer from "../lib/answer.js";
import type * as lib_expansion from "../lib/expansion.js";
import type * as lib_followup from "../lib/followup.js";
import type * as lib_generation from "../lib/generation.js";
import type * as lib_hybrid from "../lib/hybrid.js";
import type * as lib_mapping from "../lib/mapping.js";
import type * as lib_models from "../lib/models.js";
import type * as lib_multilingual from "../lib/multilingual.js";
import type * as lib_privacy from "../lib/privacy.js";
import type * as lib_recognition from "../lib/recognition.js";
import type * as lib_routing from "../lib/routing.js";
import type * as lib_text from "../lib/text.js";
import type * as llm from "../llm.js";
import type * as retrieval from "../retrieval.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  chat: typeof chat;
  citations: typeof citations;
  config: typeof config;
  documents: typeof documents;
  embeddings: typeof embeddings;
  eval: typeof eval;
  guardrails: typeof guardrails;
  "lib/answer": typeof lib_answer;
  "lib/expansion": typeof lib_expansion;
  "lib/followup": typeof lib_followup;
  "lib/generation": typeof lib_generation;
  "lib/hybrid": typeof lib_hybrid;
  "lib/mapping": typeof lib_mapping;
  "lib/models": typeof lib_models;
  "lib/multilingual": typeof lib_multilingual;
  "lib/privacy": typeof lib_privacy;
  "lib/recognition": typeof lib_recognition;
  "lib/routing": typeof lib_routing;
  "lib/text": typeof lib_text;
  llm: typeof llm;
  retrieval: typeof retrieval;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
