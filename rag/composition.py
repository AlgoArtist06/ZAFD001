"""The composition root: the one place adapters are selected and wired.

The answering pipeline is live-only (ADR 0010): generation and intent
extraction REQUIRE ``LLM_API_KEY`` (the app refuses to start without it), and
embeddings are always FastEmbed (local, CPU, keyless). There is no offline
answering mode - a missing or failing dependency surfaces as an error, never as
a silent template answer. The remaining seams select here from credential
presence in :class:`~config.AppConfig`:

- ``QDRANT_URL``   -> Qdrant vector store (else in-memory over real embeddings)
- Clerk key pair   -> Clerk session verification (else the in-memory verifier)
- ``DATABASE_URL`` -> Postgres persistence for conversations and consent

The test suite never uses this module's defaults; it injects its own doubles
from ``tests/doubles.py``.

Run the demo app with::

    uvicorn rag.composition:build_demo_app --factory
"""
from __future__ import annotations

import glob
import logging
import os
from typing import List, Optional, Sequence

from fastapi import FastAPI

from config import AppConfig, ConfigError, load_config, load_dotenv
from ingestion.chunker import chunk_act
from ingestion.models import Chunk
from ingestion.parser import parse_act
from ingestion.schemes import load_scheme_chunks
from ingestion.vectorstore import VectorStore, create_embedder, create_vector_store
from rag.api.app import create_app
from rag.domain.answer import LegalAssistant
from rag.domain.generation import Generator
from rag.domain.multilingual import BilingualGlossary, IntentExtractor
from rag.infrastructure.clerk import ClerkSessionVerifier
from rag.infrastructure.consistency import check_corpus_consistency
from rag.infrastructure.llm import LLMIntentExtractor, OpenAICompatibleGenerator
from rag.infrastructure.observability import configure_logging
from rag.infrastructure.persistence import (
    DurableConsentLedger,
    FernetCipher,
    PostgresConversationStore,
)

_ROOT = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_ROOT, "data")

_LOG = logging.getLogger(__name__)


def _require_production_auth(config: AppConfig) -> None:
    """Outside development, refuse to serve with the offline in-memory verifier.

    The browser carries real Clerk session tokens; without the Clerk key pair the
    backend falls back to the in-memory :class:`SessionVerifier`, which rejects
    every real token and 401s the whole app. Failing fast here turns a silent,
    total outage into a clear configuration error at boot.
    """
    if config.app_env != "development" and not (
        config.clerk_publishable_key and config.clerk_secret_key
    ):
        raise ConfigError(
            "APP_ENV is not 'development' but Clerk is not configured. The backend "
            "must verify the Clerk session tokens the browser sends; set "
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY (see "
            ".env.example) and restart."
        )


def _require_production_encryption(config: AppConfig) -> None:
    """With a durable store configured, refuse the XOR stand-in cipher.

    The privacy notice promises Conversation content is encrypted at rest. With a
    database configured but no ``CONVERSATION_ENCRYPTION_KEY``, the store would
    fall back to the offline XOR :class:`Cipher`, which is not real encryption.
    The guard keys off "a durable DB is configured", not ``APP_ENV`` (whose
    default is ``development``), so the fallback can never be reached silently.
    Fail fast rather than quietly break that promise.
    """
    if config.database_url and not config.conversation_encryption_key:
        raise ConfigError(
            "DATABASE_URL is set but CONVERSATION_ENCRYPTION_KEY is missing: "
            "persisted Conversation content would use the offline stand-in "
            "cipher, not real encryption at rest. Generate a key with `python -c "
            "\"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and set it."
        )


def _require_llm(config: AppConfig) -> None:
    """The one gate on serving: no key, no assistant - never a silent fallback."""
    if not config.llm_api_key:
        raise ConfigError(
            "LLM_API_KEY is not set. Legal Saathi answers only through a live "
            "model - there is no offline mode (ADR 0010). Set LLM_API_KEY (see "
            ".env.example) and restart."
        )


def create_generator(
    config: AppConfig, glossary: Optional[BilingualGlossary] = None
) -> Generator:
    """The generation seam: the live LLM, or a refusal to start."""
    _require_llm(config)
    return OpenAICompatibleGenerator(
        config.llm_api_key, config.llm_base_url, config.llm_model
    )


def create_intent_extractor(
    config: AppConfig, glossary: BilingualGlossary
) -> IntentExtractor:
    """The intent seam: live LLM normalisation, or a refusal to start."""
    _require_llm(config)
    return LLMIntentExtractor(
        config.llm_api_key, config.llm_base_url, config.llm_model, glossary
    )


def build_assistant(
    chunks: Sequence[Chunk],
    config: AppConfig,
    vector_store: Optional[VectorStore] = None,
) -> LegalAssistant:
    """Wire a :class:`LegalAssistant` with every adapter the config selects."""
    glossary = BilingualGlossary.load()
    embedder = create_embedder(config)
    if vector_store is None and config.vector_store_backend == "qdrant":
        vector_store = create_vector_store(config, embedder)
    return LegalAssistant(
        chunks,
        embedder=embedder,
        vector_store=vector_store,
        generator=create_generator(config, glossary),
        intent_extractor=create_intent_extractor(config, glossary),
        glossary=glossary,
        app_config=config,
    )


def load_demo_corpus(config: Optional[AppConfig] = None) -> List[Chunk]:
    """Load the real Source of Truth slice the demo answers from.

    Reads the ingested statute sources and scheme facts from ``data/``; the
    LegalAssistant then keeps only chunks with complete provenance. Chunking
    uses the same ``CHUNK_TOKEN_THRESHOLD`` as the ingestion pipeline, so the
    chunk ids here match the ids in the vector store.
    """
    settings = config or load_config()
    chunks: List[Chunk] = []
    for path in sorted(glob.glob(os.path.join(_DATA_DIR, "sources", "*.txt"))):
        with open(path, "r", encoding="utf-8") as handle:
            chunks.extend(
                chunk_act(
                    parse_act(handle.read()),
                    token_threshold=settings.chunk_token_threshold,
                )
            )
    chunks.extend(load_scheme_chunks(os.path.join(_DATA_DIR, "schemes.json")))
    return chunks


def build_demo_app() -> FastAPI:
    """The demo entry point: a FastAPI app over the real corpus.

    Run with ``uvicorn rag.composition:build_demo_app --factory``.
    """
    # Pick up .env for local runs before anything reads the environment; a
    # deployment that injects real env vars is unaffected (those always win).
    load_dotenv(os.path.join(_ROOT, ".env"))
    configure_logging()
    config = load_config()
    # Fail fast, before any work: no live model, no app (ADR 0010).
    _require_llm(config)
    # And no half-configured auth in production: the browser sends Clerk tokens.
    _require_production_auth(config)
    # Nor a broken "encrypted at rest" promise: real key or no durable store.
    _require_production_encryption(config)
    if not (config.clerk_publishable_key and config.clerk_secret_key):
        _LOG.warning(
            "Clerk is not configured: the in-memory verifier will reject the real "
            "Clerk tokens the browser sends, so every request 401s. Set the Clerk "
            "key pair in the backend environment for a working signed-in flow."
        )
    if config.vector_store_backend == "memory" and config.app_env != "development":
        _LOG.warning(
            "No QDRANT_URL: the in-memory vector store re-embeds the entire corpus "
            "on every boot (slow and memory-heavy at production corpus size). Point "
            "QDRANT_URL at a Qdrant instance for production."
        )
    corpus = load_demo_corpus(config)
    # Real authenticated encryption for persisted content when a key is set; the
    # store's offline XOR stand-in only ever backs local development.
    cipher = (
        FernetCipher(config.conversation_encryption_key)
        if config.conversation_encryption_key
        else None
    )
    store = (
        PostgresConversationStore.from_dsn(config.database_url, cipher=cipher)
        if config.database_url
        else None
    )
    # Consent is a legal fact, so it persists wherever conversations do; with no
    # database the offline in-memory ledger serves (and create_app supplies it).
    consent = (
        DurableConsentLedger.from_dsn(config.database_url)
        if config.database_url
        else None
    )
    # When Clerk is configured the browser carries real Clerk session tokens, so
    # the backend verifies them against the instance's JWKS; otherwise it falls
    # back to the offline in-memory session seam.
    verifier = (
        ClerkSessionVerifier(config.clerk_publishable_key, config.clerk_secret_key)
        if config.clerk_publishable_key and config.clerk_secret_key
        else None
    )
    vector_store = None
    if config.vector_store_backend == "qdrant":
        vector_store = create_vector_store(config, create_embedder(config))
        # Fail fast when Qdrant diverges from the corpus this process serves;
        # in development, warn and keep running for offline work.
        check_corpus_consistency(
            vector_store, corpus, strict=config.app_env != "development"
        )
    # Pin CORS to the deployed web origin; only local development, which sets no
    # WEB_ORIGIN, falls back to the permissive wildcard inside create_app.
    allowed_origins = [config.web_origin] if config.web_origin else None
    return create_app(
        build_assistant(corpus, config, vector_store=vector_store),
        verifier=verifier,
        consent=consent,
        store=store,
        allowed_origins=allowed_origins,
    )
