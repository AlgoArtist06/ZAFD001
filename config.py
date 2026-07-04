"""Typed application configuration.

Settings and their validation only. Which adapter runs behind each seam is
decided from these values in the composition roots: :mod:`rag.composition` for
the RAG application and :mod:`ingestion.vectorstore` for the ingestion-owned
embedding and vector-store seams.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple
from urllib.parse import urlparse


class ConfigError(ValueError):
    """A malformed environment setting."""


@dataclass(frozen=True)
class AppConfig:
    llm_provider: str
    llm_api_key: Optional[str]
    llm_base_url: str
    llm_model: str
    embedding_provider: str
    embedding_model: str
    embedding_dim: int
    qdrant_url: Optional[str]
    qdrant_api_key: Optional[str]
    qdrant_collection: str
    database_url: Optional[str]
    clerk_publishable_key: Optional[str]
    clerk_secret_key: Optional[str]
    clerk_sign_in_url: str
    clerk_sign_up_url: str
    app_env: str
    backend_url: str
    public_api_url: str
    web_origin: Optional[str]
    conversation_encryption_key: Optional[str]
    chunk_token_threshold: int
    retrieval_top_k: int
    hybrid_alpha: float
    supported_languages: Tuple[str, ...]

    @property
    def generator_backend(self) -> str:
        # There is no offline generator (ADR 0010): without a key the app
        # refuses to start rather than serving template answers.
        return "openai" if self.llm_api_key else "unconfigured"

    @property
    def embedder_backend(self) -> str:
        # FastEmbed is local, CPU, and keyless - and it is the only embedder.
        return "fastembed"

    @property
    def vector_store_backend(self) -> str:
        return "qdrant" if self.qdrant_url else "memory"


def _optional(env: Mapping[str, str], name: str) -> Optional[str]:
    value = env.get(name, "").strip()
    return None if not value or value.startswith("replace-with-") else value


def _text(env: Mapping[str, str], name: str, default: str) -> str:
    return env.get(name, "").strip() or default


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(_text(env, name, str(default)))
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _number(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(_text(env, name, str(default)))
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


def _validate_url(name: str, value: Optional[str], schemes: Tuple[str, ...]) -> None:
    if value is None:
        return
    parsed = urlparse(value)
    if parsed.scheme not in schemes or not parsed.netloc:
        raise ConfigError(f"{name} must be a valid {'/'.join(schemes)} URL")


def _validate(config: AppConfig) -> AppConfig:
    positive = {
        "EMBEDDING_DIM": config.embedding_dim,
        "CHUNK_TOKEN_THRESHOLD": config.chunk_token_threshold,
        "RETRIEVAL_TOP_K": config.retrieval_top_k,
    }
    for name, value in positive.items():
        if value <= 0:
            raise ConfigError(f"{name} must be greater than zero")
    if not 0 <= config.hybrid_alpha <= 1:
        raise ConfigError("HYBRID_ALPHA must be between 0 and 1")
    if not config.supported_languages or not set(config.supported_languages) <= {
        "en",
        "hi",
        "ta",
        "gu",
    }:
        raise ConfigError("SUPPORTED_LANGUAGES must contain only en, hi, ta, gu")
    if config.embedding_provider != "fastembed":
        raise ConfigError(
            "EMBEDDING_PROVIDER must be fastembed - it is the only embedder; "
            "the product has no offline stand-in"
        )
    _validate_url("LLM_BASE_URL", config.llm_base_url, ("http", "https"))
    _validate_url("QDRANT_URL", config.qdrant_url, ("http", "https"))
    _validate_url("BACKEND_URL", config.backend_url, ("http", "https"))
    _validate_url("NEXT_PUBLIC_API_URL", config.public_api_url, ("http", "https"))
    _validate_url("WEB_ORIGIN", config.web_origin, ("http", "https"))
    _validate_url("DATABASE_URL", config.database_url, ("postgres", "postgresql"))
    if config.qdrant_api_key and not config.qdrant_url:
        raise ConfigError("QDRANT_API_KEY requires QDRANT_URL")
    if (
        config.qdrant_url
        and not config.qdrant_api_key
        and urlparse(config.qdrant_url).hostname
        not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ConfigError(
            "QDRANT_URL points at a remote host but QDRANT_API_KEY is not set: "
            "refusing to talk to an unauthenticated remote vector store"
        )
    if bool(config.clerk_publishable_key) != bool(config.clerk_secret_key):
        raise ConfigError("CLERK publishable and secret keys must be configured together")
    if not config.clerk_sign_in_url.startswith("/"):
        raise ConfigError("NEXT_PUBLIC_CLERK_SIGN_IN_URL must be an absolute path")
    if not config.clerk_sign_up_url.startswith("/"):
        raise ConfigError("NEXT_PUBLIC_CLERK_SIGN_UP_URL must be an absolute path")
    return config


def load_dotenv(path: str) -> None:
    """Load ``KEY=VALUE`` lines from a ``.env`` file into the process environment.

    The single place both entry points - the RAG backend
    (:func:`rag.composition.build_demo_app`) and the ingestion CLI
    (``python -m ingestion``) - pick up ``.env`` the way Next.js picks up
    ``.env.local``, rather than silently running on defaults when the operator
    forgets ``set -a; source .env``. A variable already present in the
    environment always wins, so config the deployment injects (Docker, systemd, a
    secret manager) is never overridden by the file. A missing file is a no-op;
    malformed lines are skipped, not fatal.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def load_config(environ: Optional[Mapping[str, str]] = None) -> AppConfig:
    """Load the documented settings from a supplied mapping or the process environment."""
    env = os.environ if environ is None else environ
    return _validate(
        AppConfig(
            llm_provider=_text(env, "LLM_PROVIDER", "gemini"),
            llm_api_key=_optional(env, "LLM_API_KEY"),
            llm_base_url=_text(
                env,
                "LLM_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            llm_model=_text(env, "LLM_MODEL", "gemini-2.5-flash"),
            embedding_provider=_text(env, "EMBEDDING_PROVIDER", "fastembed"),
            embedding_model=_text(env, "EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"),
            embedding_dim=_integer(env, "EMBEDDING_DIM", 768),
            qdrant_url=_optional(env, "QDRANT_URL"),
            qdrant_api_key=_optional(env, "QDRANT_API_KEY"),
            qdrant_collection=_text(env, "QDRANT_COLLECTION", "legal_documents"),
            database_url=_optional(env, "DATABASE_URL"),
            clerk_publishable_key=_optional(
                env, "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
            ),
            clerk_secret_key=_optional(env, "CLERK_SECRET_KEY"),
            clerk_sign_in_url=_text(
                env, "NEXT_PUBLIC_CLERK_SIGN_IN_URL", "/sign-in"
            ),
            clerk_sign_up_url=_text(
                env, "NEXT_PUBLIC_CLERK_SIGN_UP_URL", "/sign-up"
            ),
            app_env=_text(env, "APP_ENV", "development"),
            backend_url=_text(env, "BACKEND_URL", "http://localhost:8000"),
            public_api_url=_text(
                env, "NEXT_PUBLIC_API_URL", "http://localhost:8000"
            ),
            web_origin=_optional(env, "WEB_ORIGIN"),
            conversation_encryption_key=_optional(
                env, "CONVERSATION_ENCRYPTION_KEY"
            ),
            chunk_token_threshold=_integer(env, "CHUNK_TOKEN_THRESHOLD", 512),
            retrieval_top_k=_integer(env, "RETRIEVAL_TOP_K", 8),
            hybrid_alpha=_number(env, "HYBRID_ALPHA", 0.5),
            supported_languages=tuple(
                item.strip()
                for item in _text(
                    env, "SUPPORTED_LANGUAGES", "en,hi,ta,gu"
                ).split(",")
                if item.strip()
            ),
        )
    )
