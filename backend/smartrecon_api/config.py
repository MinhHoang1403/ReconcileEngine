"""Environment-backed application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = "postgresql+psycopg://smartrecon:smartrecon@db:5432/smartrecon"
    artifacts_path: Path = Path("storage")
    cors_origins: str = "http://localhost:5173"
    demo_mode: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured browser origins from a comma-separated env value."""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
