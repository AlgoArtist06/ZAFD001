// Rewriting a dependent follow-up into a self-contained query, ported from
// rag/domain/followup.py. A referential pronoun ("what is the punishment for
// *it*?") or elliptical connector carries no statutory content of its own and
// would be refused; folding in the bounded recent Conversation context first
// lets retrieval see the subject it refers back to. Deliberately
// deterministic and dependency-free.

// Words that mark a query as leaning on earlier context.
const FOLLOWUP_MARKERS = new Set([
  "it", "its", "that", "this", "them", "they", "those", "these",
  "one", "ones", "also", "else",
]);

const WORD_RE = /[a-z]+/g;

// Whether `query` reads as a follow-up that depends on prior context.
export function isFollowup(query: string): boolean {
  const words = query.toLowerCase().match(WORD_RE) ?? [];
  return words.some((word) => FOLLOWUP_MARKERS.has(word));
}

// Rewrite a dependent follow-up into a standalone query using recent context
// (the bounded list of recent standalone queries, oldest first). A
// self-contained query, or one with no context yet, is returned unchanged.
export function rewriteFollowup(
  query: string,
  recentContext: string[],
): string {
  if (recentContext.length === 0 || !isFollowup(query)) {
    return query;
  }
  return [...recentContext, query].join(" ");
}

// How many recent standalone turns seed follow-up rewriting, everywhere a
// Conversation's memory is rebuilt (mirrors Conversation._CONTEXT_TURNS).
export const CONTEXT_TURNS = 4;
