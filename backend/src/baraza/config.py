"""Configuration read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BARAZA_", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://baraza:baraza@localhost:5432/baraza"
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI-compatible LLM gateway (LiteLLM, Ollama, vLLM, hosted provider...).
    llm_base_url: str = "http://localhost:4000/v1"
    llm_api_key: str = Field(default="changeme", repr=False)
    llm_model: str = "ollama/mistral"
    # True when the gateway routes to an external provider: shown to administrators.
    llm_is_external: bool = False

    # Optional Vexa capture service; disabled until explicitly configured.
    vexa_enabled: bool = False
    vexa_base_url: str = "http://vexa:8056"
    vexa_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    vexa_bot_name: str = Field(
        default="Baraza – note taker (transcribing)",  # noqa: RUF001 - required display name
        min_length=1,
    )
    vexa_timeout_seconds: float = Field(default=15, gt=0, le=120)
    vexa_retries: int = Field(default=2, ge=0, le=5)

    # Retention period for transcripts and minutes, in days (0 = unlimited).
    retention_days: int = 0
    delete_audio_after_transcription: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
