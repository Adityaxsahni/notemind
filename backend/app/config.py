from functools import lru_cache
from pathlib import Path
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
        "postgresql+psycopg://notemind:notemind@127.0.0.1:5432/notemind"  # pragma: allowlist secret
    )
    redis_url: str = "redis://127.0.0.1:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]

    upload_dir: Path = Path("data/uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    user_storage_quota_bytes: int = 200 * 1024 * 1024
    max_documents_per_collection: int = 200

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Pinned Hub commit: a re-pushed branch can't silently swap the weights we run.
    embedding_model_revision: str = (
        "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"  # pragma: allowlist secret
    )
    embedding_batch_size: int = 64
    # Tunable for the Phase 7 chunking experiments. bge-small reads at most 512 tokens.
    chunk_target_tokens: int = 400
    chunk_overlap_tokens: int = 60

    @model_validator(mode="after")
    def _check_chunking(self) -> "Settings":
        if not 50 <= self.chunk_target_tokens <= 480:
            raise ValueError("CHUNK_TARGET_TOKENS must be between 50 and 480")
        if not 0 <= self.chunk_overlap_tokens < self.chunk_target_tokens // 2:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be under half of CHUNK_TARGET_TOKENS")
        return self

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
