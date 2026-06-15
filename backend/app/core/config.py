from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    database_url: str = "postgresql+asyncpg://aiqa:aiqa_secret@localhost:5432/aiqa_db"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_secret"

    cors_origins: str = "http://localhost:3000"

    upload_dir: Path = Path("./uploads")
    artifacts_dir: Path = Path("./artifacts")

    playwright_headless: bool = True
    playwright_timeout_ms: int = 20000
    playwright_viewport_width: int = 1366
    playwright_viewport_height: int = 768
    playwright_browsers_path: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
