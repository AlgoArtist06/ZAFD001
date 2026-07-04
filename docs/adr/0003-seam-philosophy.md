# ADR 0003: Every external dependency sits behind a seam with an offline default

- Status: accepted (records a philosophy the codebase already practiced)
- Date: 2026-07-02

## Context

The product depends on several external services: an LLM, an embedding model, a vector database, an identity provider, and a relational database.
The test suite must stay runnable, deterministic, and fast with none of them present.

## Decision

Every external dependency is reached through a narrow seam (a Protocol or duck-typed interface) with exactly two implementations:

| Seam | Offline default (domain) | Real adapter (infrastructure) | Selected by |
|---|---|---|---|
| Generator | `DeterministicGenerator` | `OpenAICompatibleGenerator` | `LLM_API_KEY` |
| IntentExtractor | `DeterministicIntentExtractor` | `LLMIntentExtractor` | `LLM_API_KEY` |
| Embedder | `DeterministicEmbedder` | `FastEmbedEmbedder` | `QDRANT_URL` |
| VectorStore | `InMemoryVectorStore` | `QdrantVectorStore` | `QDRANT_URL` |
| SessionVerifier | `SessionVerifier` | `ClerkSessionVerifier` | Clerk key pair |
| ConversationStore | `InMemoryConversationStore` | `PostgresConversationStore` | `DATABASE_URL` |

Selection happens only in the composition root (ADR 0002), from credential presence.
The offline default is not a mock: it is a real, correct implementation whose behavior the suite pins.

## Consequences

The whole suite runs with no services and no keys.
Adding a third implementation of any seam (a different LLM provider, a different vector store) touches the composition root and nothing else.
The offline defaults must stay behaviorally honest: when a live adapter gains a capability (for example token streaming), the seam grows an optional method and callers must degrade gracefully when the default lacks it.
