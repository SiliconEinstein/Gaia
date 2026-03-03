from libs.storage.config import StorageConfig


def test_default_config():
    config = StorageConfig()
    assert config.deployment_mode == "local"
    assert config.lancedb_path == "/data/lancedb/gaia"
    assert config.neo4j_uri == "bolt://localhost:7687"
    assert config.neo4j_database == "neo4j"


def test_production_config():
    config = StorageConfig(
        deployment_mode="production",
        bytehouse_host="bh.example.com",
        bytehouse_api_key="key123",
    )
    assert config.deployment_mode == "production"
    assert config.bytehouse_host == "bh.example.com"


def test_local_config_override():
    config = StorageConfig(
        lancedb_path="/tmp/test/lance",
        neo4j_password="secret",
    )
    assert config.lancedb_path == "/tmp/test/lance"
    assert config.neo4j_password == "secret"
