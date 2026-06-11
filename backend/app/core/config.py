from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "causAI API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://causai:causai@127.0.0.1:55432/causai"
    jwt_secret: str = Field(default="change-this-development-secret")
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 30
    jwt_refresh_token_days: int = 7
    access_cookie_name: str = "causai_access"
    refresh_cookie_name: str = "causai_refresh"

    storage_root: Path = Path("backend/storage")
    max_upload_bytes: int = 16 * 1024 * 1024
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.storage_root.is_absolute():
        settings.storage_root = (REPO_ROOT / settings.storage_root).resolve()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    return settings
