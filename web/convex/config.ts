// ADR 0010, carried over from the FastAPI system: the product answers only
// through a live LLM. No offline templates, no mock fallback, no cached or
// rule-based answers - a missing provider is a configuration error surfaced
// to the user as "service unavailable", never an ungrounded legal response.
//
// Every action that generates (answerQuestion, intent extraction, query
// embedding) must call validateLLMConfigured() before doing any work.
// Tests may inject deterministic fakes; production never switches silently.

export class ConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigurationError";
  }
}

export type LLMConfig = {
  apiKey: string;
  baseUrl: string;
  model: string;
};

// Mirrors the Python config's placeholder rule: a value still carrying the
// .env.example placeholder prefix counts as unset. Shared by every module
// that reads provider configuration.
export function optionalEnv(name: string): string | null {
  const value = (process.env[name] ?? "").trim();
  return !value || value.startsWith("replace-with-") ? null : value;
}

export function validateLLMConfigured(): LLMConfig {
  const apiKey = optionalEnv("LLM_API_KEY");
  const model = optionalEnv("LLM_MODEL");
  if (!apiKey || !model) {
    throw new ConfigurationError(
      "The assistant is not configured to answer: LLM_API_KEY and LLM_MODEL " +
        "must be set on the Convex deployment (npx convex env set ...). " +
        "Legal Saathi answers only through a live model - there is no " +
        "offline mode (ADR 0010).",
    );
  }
  return {
    apiKey,
    model,
    baseUrl:
      optionalEnv("LLM_BASE_URL") ??
      "https://generativelanguage.googleapis.com/v1beta/openai/",
  };
}
