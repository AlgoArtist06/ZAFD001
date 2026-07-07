// Privacy constants and helpers, ported from rag/domain/privacy.py.
//
// Encryption at rest: the Python system encrypted turn content app-side
// (Fernet) before writing Postgres. Convex encrypts all stored data at rest
// platform-side, so the privacy notice's promise holds without an app-layer
// cipher; the trust boundary moved from an app-managed key to the platform.

// Bumping this when the notice text changes lets a fresh consent be required.
export const NOTICE_VERSION = "2026-06-29";

export const PRIVACY_NOTICE =
  "Privacy notice\n" +
  "\n" +
  "What we store and why: when you are signed in, we store your " +
  "Conversations - the questions you ask and the answers you receive - so " +
  "your history follows you across devices. We also store the fact and date " +
  "of your consent to this notice. Conversation content is encrypted at rest.\n" +
  "\n" +
  "Third-party LLM: to understand your question and compose an answer, the " +
  "text of your query is sent to a third-party large language model (LLM) " +
  "provider. The trade-off: this gives you fluent, multilingual answers " +
  "without us running our own model, but it means your query text leaves our " +
  "systems, and on a free tier the provider may use inputs to train their " +
  "model. Do not include information you would not want shared.\n" +
  "\n" +
  "Your control: you can delete any single Conversation, or delete your " +
  "account and all stored data at any time (your right to erasure).";

// A non-reversible placeholder so sensitive content never reaches a log.
// Logs may record that a message of some length was handled, never its words.
export function redact(text: string): string {
  return `<redacted ${text.length} chars>`;
}
