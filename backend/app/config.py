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

    # MiniLM-L6 reranks 30 candidates in ~1 s on CPU; bge-reranker-base took ~7 s (Phase 7
    # compares their quality).
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    reranker_model_revision: str = (
        "233902d25c440f23af6f7d6e94d2946bac0bee0a"  # pragma: allowlist secret
    )
    retrieval_candidates: int = 30  # per search method, and how many fused results get reranked
    retrieval_top_k: int = 6
    # Raw reranker logit. On a 13-question smoke set, answerable questions scored >= -3.9 and
    # off-topic ones <= -10.2. Calibrated on the full eval set in Phase 7.
    retrieval_min_score: float = -6.0

    llm_api_key: SecretStr | None = None
    llm_answer_model: str = "claude-opus-5-5"
    # Grounded Q&A over six short passages needs little deliberation; low effort also keeps
    # time-to-first-token down (thinking is always on for this model).
    llm_answer_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    llm_answer_max_tokens: int = 8000  # includes thinking; also the per-request budget hold
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2  # SDK retries 408/409/429/5xx/connection errors with backoff
    # Input + output tokens. A typical answer uses ~3-4k, so ~15-20 questions a day.
    llm_user_daily_token_budget: int = 60_000
    llm_global_daily_token_budget: int = 5_000_000  # caps total spend if many users pile on
    answer_cache_ttl_seconds: int = 24 * 3600

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
