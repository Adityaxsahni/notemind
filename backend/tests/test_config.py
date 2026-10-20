import pytest
from pydantic import ValidationError

from app.config import Settings

SHORT_SECRET = "too-short"  # pragma: allowlist secret
FAKE_SECRET = "super-secret-value-123"  # pragma: allowlist secret


def test_production_rejects_default_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", secret_key=SHORT_SECRET)


def test_production_accepts_strong_secret():
    settings = Settings(_env_file=None, environment="production", secret_key="x" * 48)
    assert settings.is_production


def test_secret_not_leaked_in_repr():
    settings = Settings(_env_file=None, secret_key=FAKE_SECRET)
    assert FAKE_SECRET not in repr(settings)
