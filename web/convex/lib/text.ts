// Tiny lexical helpers shared by the domain router and the keyword retriever,
// ported verbatim from rag/domain/text.py. Deliberately dependency-free: a
// light stemmer and stopword filter are enough to ground retrieval on this
// small statutory corpus. The ingest script precomputes each chunk's stems
// with this exact function, so it must never drift from the query-side copy.

const TOKEN_RE = /[a-z0-9]+/g;

// Common function words that carry no legal signal; dropped before matching so
// a query's content words are what drive routing and keyword retrieval.
const STOPWORDS = new Set([
  "a", "an", "the", "of", "for", "to", "is", "are", "am", "was", "were", "be",
  "been", "being", "what", "which", "who", "whom", "how", "do", "does", "did",
  "i", "me", "my", "mine", "we", "us", "our", "you", "your", "it", "its",
  "in", "on", "at", "by", "with", "from", "about", "into", "over", "under",
  "that", "this", "these", "those", "and", "or", "not", "no", "can", "could",
  "should", "would", "will", "shall", "may", "might", "if", "then", "so",
  "any", "some", "all", "such", "as", "out", "up", "down", "there", "here",
  "have", "has", "had", "get", "got", "want", "need", "know",
]);

// Crude suffix-stripping stemmer (ing/ied/ed/ies/es/s) for lexical overlap.
function stem(token: string): string {
  for (const suffix of ["ing", "ied", "ed", "ies", "es", "s"]) {
    if (token.endsWith(suffix) && token.length - suffix.length >= 3) {
      const base = token.slice(0, -suffix.length);
      return suffix === "ies" ? base + "y" : base;
    }
  }
  return token;
}

// Lowercased, stopword-filtered, stemmed content tokens of `text`.
export function contentStems(text: string): string[] {
  const tokens = text.toLowerCase().match(TOKEN_RE) ?? [];
  return tokens.filter((t) => !STOPWORDS.has(t)).map(stem);
}
