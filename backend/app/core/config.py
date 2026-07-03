import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.automation.playwright_paths import resolve_playwright_browsers_path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI QA Agent"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    fernet_key: str = Field(..., min_length=32)

    # LLM: "nvidia" (NVIDIA NIM) or "openai"
    llm_provider: str = "nvidia"
    nvidia_api_key: str = ""
    nvidia_api_base: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "minimaxai/minimax-m3"
    nvidia_automation_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_max_tokens: int = 8192
    nvidia_temperature: float = 0.3
    llm_field_fallback: bool = False

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    firebase_project_id: str = "automation-tool-29a9c"
    firebase_credentials_path: str | None = None
    # Tolerate small client/server clock drift when validating Firebase ID tokens.
    firebase_token_clock_skew_seconds: int = 60

    database_url: str = "postgresql+asyncpg://aiqa:aiqa_secret@localhost:5432/aiqa_db"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_secret"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    upload_dir: Path = Path("./uploads")
    artifacts_dir: Path = Path("./artifacts")

    playwright_headless: bool = True
    playwright_timeout_ms: int = 20000
    playwright_viewport_width: int = 1366
    playwright_viewport_height: int = 768
    playwright_browsers_path: str | None = None

    # Defaults match Salesforce CLI / VS Code (PlatformCLI + localhost:1717).
    salesforce_oauth_client_id: str = "PlatformCLI"
    salesforce_oauth_client_secret: str = ""
    salesforce_oauth_redirect_uri: str = "http://localhost:1717/OauthRedirect"

    @field_validator("playwright_browsers_path", mode="before")
    @classmethod
    def sanitize_playwright_browsers_path(cls, value: str | None) -> str | None:
        env_value = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        configured = value if value is not None else env_value
        return resolve_playwright_browsers_path(configured)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
