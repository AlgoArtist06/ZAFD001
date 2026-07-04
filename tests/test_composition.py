"""The composition root's environment loading and auth guard."""
from __future__ import annotations

import os

import pytest

from config import ConfigError, load_config
from rag.composition import (
    _require_production_auth,
    _require_production_encryption,
    load_dotenv,
)
from rag.infrastructure.persistence import FernetCipher

_BASE_ENV = {"LLM_API_KEY": "k", "EMBEDDING_PROVIDER": "fastembed"}


def _config(**overrides):
    return load_config({**_BASE_ENV, **overrides})


def test_load_dotenv_sets_missing_and_skips_noise(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n"
        "\n"
        "LLM_MODEL=qwen/qwen3\n"
        "export CLERK_SECRET_KEY=sk_test_abc\n"
        'QDRANT_COLLECTION="legal_documents"\n'
        "NOT_A_PAIR\n"
    )
    for key in ("LLM_MODEL", "CLERK_SECRET_KEY", "QDRANT_COLLECTION", "NOT_A_PAIR"):
        monkeypatch.delenv(key, raising=False)

    load_dotenv(str(env_file))

    assert os.environ["LLM_MODEL"] == "qwen/qwen3"
    assert os.environ["CLERK_SECRET_KEY"] == "sk_test_abc"  # export prefix stripped
    assert os.environ["QDRANT_COLLECTION"] == "legal_documents"  # quotes stripped
    assert "NOT_A_PAIR" not in os.environ  # a line with no '=' is skipped


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=from-file\n")
    monkeypatch.setenv("LLM_MODEL", "from-deployment")

    load_dotenv(str(env_file))

    # Env injected by the deployment always wins over the file.
    assert os.environ["LLM_MODEL"] == "from-deployment"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    load_dotenv(str(tmp_path / "does-not-exist.env"))  # must not raise


def test_production_without_clerk_fails_fast():
    config = _config(APP_ENV="production")
    with pytest.raises(ConfigError, match="Clerk is not configured"):
        _require_production_auth(config)


def test_production_with_clerk_is_allowed():
    config = _config(
        APP_ENV="production",
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_live_x",
        CLERK_SECRET_KEY="sk_live_x",
    )
    _require_production_auth(config)  # must not raise


def test_development_without_clerk_is_allowed():
    _require_production_auth(_config(APP_ENV="development"))  # must not raise


_DSN = "postgresql://user:pass@localhost:5432/legal"


def test_production_with_db_but_no_encryption_key_fails_fast():
    config = _config(APP_ENV="production", DATABASE_URL=_DSN)
    with pytest.raises(ConfigError, match="CONVERSATION_ENCRYPTION_KEY"):
        _require_production_encryption(config)


def test_production_with_encryption_key_is_allowed():
    from cryptography.fernet import Fernet

    config = _config(
        APP_ENV="production",
        DATABASE_URL=_DSN,
        CONVERSATION_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    )
    _require_production_encryption(config)  # must not raise


def test_development_with_db_but_no_encryption_key_fails_fast():
    # H2: the guard keys off "durable DB configured", not APP_ENV, so the XOR
    # stand-in can never silently back a real database - even in development.
    config = _config(APP_ENV="development", DATABASE_URL=_DSN)
    with pytest.raises(ConfigError, match="CONVERSATION_ENCRYPTION_KEY"):
        _require_production_encryption(config)


def test_no_database_needs_no_encryption_key():
    # The in-memory store never persists, so no key is required regardless of env.
    _require_production_encryption(_config(APP_ENV="development"))
    _require_production_encryption(_config(APP_ENV="production"))


def test_fernet_cipher_round_trips_and_hides_plaintext():
    from cryptography.fernet import Fernet

    cipher = FernetCipher(Fernet.generate_key().decode())
    secret = "Someone cheated me by fraud"
    stored = cipher.encrypt(secret)
    assert secret not in stored  # content is not at rest in the clear
    assert cipher.decrypt(stored) == secret
