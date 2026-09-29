"""Configuration read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic import Field
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

    # Retention period for transcripts and minutes, in days (0 = unlimited).
    retention_days: int = 0
    delete_audio_after_transcription: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
