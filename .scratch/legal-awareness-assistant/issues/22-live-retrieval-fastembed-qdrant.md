# Live retrieval stack: FastEmbed embeddings + Qdrant vector store

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Move retrieval from the in-memory deterministic stand-in onto the real stack the PRD specifies: local FastEmbed embeddings and a Qdrant vector store holding the legal documents.
Implement the real `Embedder` (a local FastEmbed BGE model, running on CPU with no API key, as the PRD requires for English-only retrieval) behind the existing `Embedder` protocol, and a Qdrant-backed vector store behind the existing retrieval seam, configured from the Qdrant settings on the config seam (URL, optional API key, collection).
Wire the ingestion pipeline's load step to embed validated chunks and load them into Qdrant, so the corpus produced in Phase 0 lands in a queryable index rather than living only in memory.

Retrieval keeps its current shape: hybrid keyword-plus-vector search, metadata-filtered and domain-routed, returning the same hit records, with parent expansion and everything above it unchanged.
Prove it with the Phase-0 retrieval smoke test - a set of known queries returns the correct section as the top hit against a live Qdrant instance.
Selection is keyless-safe per the config seam: with Qdrant configured, retrieval runs against the live index; with no Qdrant configured, the existing in-memory deterministic retrieval serves, so the suite stays offline and keyless.

## Acceptance criteria

- [ ] A FastEmbed (BGE) `Embedder` implements the existing `Embedder` protocol and runs locally with no API key
- [ ] A Qdrant-backed vector store implements the existing retrieval seam, configured from the config seam (URL, API key, collection)
- [ ] The ingestion load step embeds validated chunks and loads them into Qdrant with their provenance metadata intact
- [ ] Hybrid keyword-plus-vector search, domain/metadata filtering, and parent expansion behave the same as before, only against the live index
- [ ] The Phase-0 retrieval smoke test passes against live Qdrant: known queries return the correct section as top hit
- [ ] With no Qdrant configured, the in-memory deterministic retrieval serves and the full suite passes offline
- [ ] Local Qdrant setup (Docker) and the embedding model choice are documented

## Blocked by

- `20-config-seam-and-secret-hygiene.md`

## Comments

Implemented local CPU FastEmbed BGE embeddings, Qdrant ingestion and hybrid retrieval with complete Provenance Records, config-driven live/offline selection, Docker documentation, and offline plus live Phase-0 smoke coverage.
