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
    # Per process. Sync routes run on a 40-thread pool, so with SQLAlchemy's default of 5 + 10
    # requests queue for a connection under load. Keep processes × (size + overflow) below
    # Postgres's max_connections (100), leaving room for workers and migrations.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # Fail fast when overloaded (503, retry) instead of holding a worker thread for 30 s.
    db_pool_timeout_seconds: float = 10.0
    redis_url: str = "redis://127.0.0.1:6379/0"
    # Empty: the browser only talks to the Next.js origin, which proxies the API, so no
    # cross-origin access is needed. List exact origins only if another site must call the API.
    cors_origins: list[str] = []
    # Shared with the frontend's proxy when it runs on Vercel (app/trusted_proxy.py). Unset in
    # Docker, where the proxies have fixed addresses instead.
    proxy_secret: SecretStr | None = None
    # Requests per minute per client IP across the whole API (route-specific limits are lower).
    global_rate_limit_per_minute: int = 600
    # Bot checks on sign-up and log-in (app/security/bot.py).
    bot_min_fill_seconds: float = 2.0
    turnstile_secret_key: SecretStr | None = None
    # Two-step sign-in: password, then a one-time code by email (app/security/otp.py).
    otp_required: bool = True
    smtp_host: str | None = None  # unset: codes are logged and shown on screen (local only)
    smtp_port: int = 587  # 587 STARTTLS, or 465 implicit TLS
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "NoteMind <no-reply@notemind.example>"

    upload_dir: Path = Path("data/uploads")
    max_upload_bytes: int = 200 * 1024 * 1024  # big course packs and image-heavy slide exports
    user_storage_quota_bytes: int = 1024 * 1024 * 1024
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

    llm_api_key: SecretStr | None = None  # the key for whichever vendor llm_answer_model is
    llm_answer_model: str = "claude-opus-5-5"  # or a "gemini-..." model with a Gemini API key
    # Grounded Q&A over six short passages needs little deliberation; low effort also keeps
    # time-to-first-token down (thinking is always on for this model).
    llm_answer_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    # Tried in order when the answer (or transcription) model is busy or out of quota, e.g.
    # LLM_FALLBACK_MODELS=["gemini-3.6-flash","gemini-flash-lite-latest"]. Same key and vendor.
    llm_fallback_models: list[str] = []
    llm_answer_max_tokens: int = 8000  # includes thinking; also the per-request budget hold
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2  # SDK retries 408/409/429/5xx/connection errors with backoff
    # Input + output tokens. A typical answer uses ~3-4k, so ~15-20 questions a day.
    llm_user_daily_token_budget: int = 60_000
    llm_global_daily_token_budget: int = 5_000_000  # caps total spend if many users pile on
    answer_cache_ttl_seconds: int = 24 * 3600

    # Handwriting, scans and photos: pages with no text layer are read by a vision model.
    ocr_model: str | None = None  # default: llm_answer_model (same vendor and key)
    ocr_pages_per_request: int = 4  # fewer requests: free tiers count requests, not tokens
    ocr_concurrency: int = 4
    ocr_max_pages: int = 300  # per document
    # ~2,000 tokens per page in and out, so ~500 handwritten pages per user per day.
    llm_user_daily_ocr_token_budget: int = 1_000_000

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

    @model_validator(mode="after")
    def _real_email_outside_local(self) -> "Settings":
        # Without SMTP, sign-in codes are shown on screen: fine on a laptop, never deployed.
        if self.environment in ("staging", "production") and self.otp_required:
            if not self.smtp_host:
                raise ValueError("Set SMTP_HOST (and credentials) or OTP_REQUIRED=false")
        return self

    @model_validator(mode="after")
    def _no_wildcard_cors(self) -> "Settings":
        # Credentials (auth cookies) with a wildcard origin would let any site act as the user.
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must list exact origins, not *")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def show_otp_on_screen(self) -> bool:
        """Local development without a mail server: the API returns the code itself."""
        return self.environment == "local" and not self.smtp_host


@lru_cache
def get_settings() -> Settings:
    return Settings()
