import sys
from types import SimpleNamespace

import pytest

from config import ConfigError, load_config
from ingestion.vectorstore import (
    FastEmbedEmbedder,
    QdrantVectorStore,
    create_embedder,
    create_vector_store,
)
from rag.composition import create_generator
from rag.infrastructure.llm import OpenAICompatibleGenerator


def test_load_config_applies_documented_defaults_and_typed_overrides():
    defaults = load_config({})

    assert defaults.llm_provider == "gemini"
    assert defaults.llm_api_key is None
    assert defaults.llm_model == "gemini-2.5-flash"
    assert defaults.embedding_dim == 768
    assert defaults.qdrant_url is None
    assert defaults.retrieval_top_k == 8
    assert defaults.hybrid_alpha == 0.5
    assert defaults.supported_languages == ("en", "hi", "ta", "gu")

    configured = load_config(
        {
            "LLM_API_KEY": "test-key",
            "QDRANT_URL": "http://localhost:6333",
            "EMBEDDING_DIM": "384",
            "RETRIEVAL_TOP_K": "4",
            "HYBRID_ALPHA": "0.25",
            "SUPPORTED_LANGUAGES": "en,hi",
        }
    )

    assert configured.llm_api_key == "test-key"
    assert configured.qdrant_url == "http://localhost:6333"
    assert configured.embedding_dim == 384
    assert configured.retrieval_top_k == 4
    assert configured.hybrid_alpha == 0.25
    assert configured.supported_languages == ("en", "hi")


def test_load_config_rejects_malformed_typed_values_with_the_variable_name():
    with pytest.raises(ConfigError, match="EMBEDDING_DIM"):
        load_config({"EMBEDDING_DIM": "many"})


@pytest.mark.parametrize(
    ("environ", "setting"),
    [
        ({"EMBEDDING_DIM": "0"}, "EMBEDDING_DIM"),
        ({"CHUNK_TOKEN_THRESHOLD": "-1"}, "CHUNK_TOKEN_THRESHOLD"),
        ({"RETRIEVAL_TOP_K": "0"}, "RETRIEVAL_TOP_K"),
        ({"HYBRID_ALPHA": "1.1"}, "HYBRID_ALPHA"),
        ({"SUPPORTED_LANGUAGES": "en,xx"}, "SUPPORTED_LANGUAGES"),
        ({"LLM_BASE_URL": "not-a-url"}, "LLM_BASE_URL"),
        ({"QDRANT_URL": "localhost:6333"}, "QDRANT_URL"),
        ({"QDRANT_API_KEY": "key-without-url"}, "QDRANT_API_KEY"),
        ({"QDRANT_URL": "https://remote.example.com:6333"}, "unauthenticated"),
        ({"CLERK_SECRET_KEY": "secret-without-public-key"}, "CLERK"),
    ],
)
def test_load_config_rejects_invalid_configuration(environ, setting):
    with pytest.raises(ConfigError, match=setting):
        load_config(environ)


def test_keyless_config_refuses_to_build_a_generator():
    # Live-only answering (ADR 0010): without LLM_API_KEY there is no
    # generator and no app - never a deterministic stand-in.
    config = load_config({})

    assert config.generator_backend == "unconfigured"
    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        create_generator(config)


def test_service_configuration_selects_live_adapter_names_for_later_adapters():
    config = load_config(
        {"LLM_API_KEY": "test-key", "QDRANT_URL": "http://localhost:6333"}
    )

    assert config.generator_backend == "openai"
    assert config.embedder_backend == "fastembed"
    assert config.vector_store_backend == "qdrant"


def test_fastembed_is_the_only_embedder():
    # FastEmbed is local and keyless, so it needs no vector server; the
    # in-memory store over real embeddings serves when Qdrant is absent.
    local = load_config({})
    assert local.embedder_backend == "fastembed"
    assert local.vector_store_backend == "memory"
    with pytest.raises(ConfigError, match="EMBEDDING_PROVIDER"):
        load_config({"EMBEDDING_PROVIDER": "hash"})


def test_example_secret_placeholders_do_not_activate_live_adapters():
    config = load_config(
        {
            "LLM_API_KEY": "replace-with-gemini-api-key",
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "replace-with-clerk-publishable-key",
            "CLERK_SECRET_KEY": "replace-with-clerk-secret-key",
        }
    )

    assert config.llm_api_key is None
    assert config.clerk_publishable_key is None
    assert config.clerk_secret_key is None
    assert config.generator_backend == "unconfigured"


def test_composition_points_resolve_adapters_through_config(monkeypatch):
    configured = load_config({"LLM_API_KEY": "test-key"})
    assert isinstance(create_generator(configured), OpenAICompatibleGenerator)

    monkeypatch.setitem(
        sys.modules,
        "fastembed",
        SimpleNamespace(TextEmbedding=lambda **kwargs: SimpleNamespace()),
    )
    live = load_config({"QDRANT_URL": "http://localhost:6333"})
    embedder = create_embedder(live)
    store = create_vector_store(live, embedder)

    assert isinstance(embedder, FastEmbedEmbedder)
    assert isinstance(store, QdrantVectorStore)
