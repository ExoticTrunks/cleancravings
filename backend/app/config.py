from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./cleancravings.db"
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    dev_auth: bool = True
    data_gov_api_key: str = ""
    cors_origins: str = "http://localhost:5173"

    # A source counts as stale if its last successful sync is older than this (NFR-2, NFR-9)
    stale_after_hours: int = 48
    # How far ahead to warn favourites about closures (FR-3.4)
    closure_alert_days: int = 7

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
