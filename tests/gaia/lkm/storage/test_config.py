"""Unit tests for StorageConfig ByteHouse and embedding fields."""

from gaia.lkm.storage.config import StorageConfig


def test_bytehouse_defaults():
    """ByteHouse fields have expected default values."""
    config = StorageConfig()
    assert config.bytehouse_host == ""
    assert config.bytehouse_user == ""
    assert config.bytehouse_password == ""
    assert config.bytehouse_database == "paper_data"
    assert config.embedding_access_key == ""


def test_bytehouse_from_env(monkeypatch):
    """ByteHouse and embedding fields fall back to BYTEHOUSE_* / ACCESS_KEY env vars."""
    monkeypatch.setenv("BYTEHOUSE_HOST", "bh.example.com")
    monkeypatch.setenv("BYTEHOUSE_USER", "testuser")
    monkeypatch.setenv("BYTEHOUSE_PASSWORD", "secret")
    monkeypatch.setenv("BYTEHOUSE_DATABASE", "custom_db")
    monkeypatch.setenv("ACCESS_KEY", "emb_key_123")

    config = StorageConfig()

    assert config.bytehouse_host == "bh.example.com"
    assert config.bytehouse_user == "testuser"
    assert config.bytehouse_password == "secret"
    assert config.bytehouse_database == "custom_db"
    assert config.embedding_access_key == "emb_key_123"


def test_bytehouse_explicit_overrides_env(monkeypatch):
    """Explicitly passed values take precedence over env var fallbacks."""
    monkeypatch.setenv("BYTEHOUSE_HOST", "env_host.example.com")
    monkeypatch.setenv("ACCESS_KEY", "env_key")

    config = StorageConfig(
        bytehouse_host="explicit_host.example.com", embedding_access_key="explicit_key"
    )

    assert config.bytehouse_host == "explicit_host.example.com"
    assert config.embedding_access_key == "explicit_key"


def test_bytehouse_database_default_not_overridden_by_empty_env(monkeypatch):
    """Default database name is preserved when BYTEHOUSE_DATABASE env var is not set."""
    monkeypatch.delenv("BYTEHOUSE_DATABASE", raising=False)

    config = StorageConfig()

    assert config.bytehouse_database == "paper_data"
