// The embedding seam: an OpenAI-compatible /embeddings API (replacing local
// FastEmbed). Two callers only:
//   - scripts/ingestLegalCorpus.ts, embedding corpus chunks at ingest time;
//   - the answer pipeline, embedding the user's query (one text per request).
// Corpus text is NEVER embedded at runtime (see documents.ts).
//
// ADR 0010 applies here too: retrieval quality is part of the product's
// correctness, so a missing embedding credential is a configuration error,
// never a silent hashing stand-in. Tests inject their own doubles.
import { ConfigurationError, optionalEnv } from "./config";

export type EmbeddingConfig = {
  apiKey: string;
  baseUrl: string;
  model: string;
  dimensions: number;
};

// Must match the vector index dimensions in schema.ts.
export const EMBEDDING_DIMENSIONS = 768;

// The embedding provider defaults to the LLM provider's OpenAI-compatible
// endpoint and credential (Gemini serves both), overridable separately.
export function embeddingConfig(): EmbeddingConfig {
  const apiKey = optionalEnv("EMBEDDING_API_KEY") ?? optionalEnv("LLM_API_KEY");
  if (!apiKey) {
    throw new ConfigurationError(
      "No embedding credential: set EMBEDDING_API_KEY or LLM_API_KEY on the " +
        "Convex deployment. Retrieval requires a live embedding API " +
        "(ADR 0010: no offline stand-in).",
    );
  }
  return {
    apiKey,
    baseUrl:
      optionalEnv("EMBEDDING_BASE_URL") ??
      optionalEnv("LLM_BASE_URL") ??
      "https://generativelanguage.googleapis.com/v1beta/openai/",
    model: optionalEnv("EMBEDDING_MODEL") ?? "gemini-embedding-001",
    dimensions: EMBEDDING_DIMENSIONS,
  };
}

// L2-normalise so cosine similarity behaves identically across providers
// (Gemini recommends normalising truncated-dimension embeddings).
export function normalise(vector: number[]): number[] {
  const norm = Math.sqrt(vector.reduce((sum, v) => sum + v * v, 0));
  return norm > 0 ? vector.map((v) => v / norm) : vector;
}

// Embed a batch of texts. One retry on transport failure or 5xx, mirroring
// the Python adapters; a 4xx is the caller's bug and propagates immediately.
export async function embedTexts(
  texts: string[],
  config: EmbeddingConfig,
): Promise<number[][]> {
  const url = `${config.baseUrl.replace(/\/+$/, "")}/embeddings`;
  const MAX_RETRIES = 5;
  for (let attempt = 1; ; attempt++) {
    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${config.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: config.model,
          input: texts,
          dimensions: config.dimensions,
        }),
      });
    } catch (error) {
      if (attempt >= MAX_RETRIES) throw error;
      continue;
    }
    if (response.status >= 500 && attempt < MAX_RETRIES) continue;
    if (!response.ok) {
      const detail = await response.text();
      if (response.status === 429) {
        // Prefer server-specified delay; fall back to exponential backoff.
        const retry = detail.match(/retryDelay"\s*:\s*"([\d.]+)s"/i);
        const seconds = retry
          ? Number(retry[1]) + 1
          : Math.min(30 * Math.pow(2, attempt - 1), 480);
        if (attempt < MAX_RETRIES) {
          console.log(
            `429 rate-limited (attempt ${attempt}/${MAX_RETRIES}), ` +
              `waiting ${seconds}s before retry…`,
          );
          await new Promise((resolve) =>
            setTimeout(resolve, seconds * 1000),
          );
          continue;
        }
      }
      throw new Error(
        `embedding request failed: ${response.status} ${detail}`,
      );
    }
    const body = (await response.json()) as {
      data: Array<{ index?: number; embedding: number[] }>;
    };
    // The API may reorder; index restores input order.
    const vectors = new Array<number[]>(texts.length);
    for (const [position, item] of body.data.entries()) {
      vectors[item.index ?? position] = normalise(item.embedding);
    }
    if (
      vectors.some(
        (vector) => vector === undefined || vector.length !== config.dimensions,
      )
    ) {
      throw new Error("embedding response was incomplete or had wrong dimensions");
    }
    return vectors;
  }
}

export async function embedQuery(
  text: string,
  config: EmbeddingConfig,
): Promise<number[]> {
  const [vector] = await embedTexts([text], config);
  return vector;
}
