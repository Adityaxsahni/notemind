from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-insecure-secret"  # noqa: S105  # pragma: allowlist secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "NoteMind"
    environment: Literal["local", "test", "staging", "production"] = "local"
    secret_key: SecretStr = SecretStr(_DEV_SECRET)
    database_url: str = (
        "postgresql+psycopg://notemind:notemind@localhost:5432/notemind"  # pragma: allowlist secret
    )
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def _require_real_secret_outside_local(self) -> "Settings":
        if self.environment in ("staging", "production"):
            key = self.secret_key.get_secret_value()
            if key == _DEV_SECRET or len(key) < 32:
                raise ValueError("SECRET_KEY must be set to a random value of 32+ chars")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
