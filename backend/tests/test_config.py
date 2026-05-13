from core.config import Settings


def test_database_connect_timeout_defaults_to_30_seconds(monkeypatch):
    monkeypatch.delenv("DATABASE_CONNECT_TIMEOUT_SECONDS", raising=False)
    settings = Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key",
        DATABASE_URL="postgresql://loanlens:loanlens@localhost:5432/loanlens_test",
    )

    assert settings.DATABASE_CONNECT_TIMEOUT_SECONDS == 30
