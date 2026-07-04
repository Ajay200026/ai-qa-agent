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

    # LLM: "nvidia" | "openai" | "lmstudio" (local LM Studio OpenAI-compatible API)
    llm_provider: str = "nvidia"
    # hybrid = local scan/embeddings + NVIDIA chat/analysis/automation
    llm_routing_mode: str = "hybrid"
    scan_llm_provider: str = "nvidia"
    nvidia_api_key: str = ""
    nvidia_api_base: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "minimaxai/minimax-m3"
    nvidia_chat_model: str = "z-ai/glm-5.2"
    nvidia_scan_model: str = "google/gemma-4-31b-it"
    nvidia_analysis_model: str = "google/gemma-4-31b-it"
    nvidia_automation_model: str = "z-ai/glm-5.2"
    nvidia_max_tokens: int = 16384
    nvidia_temperature: float = 0.3
    nvidia_chat_temperature: float = 1.0
    nvidia_scan_temperature: float = 0.2
    nvidia_analysis_temperature: float = 1.0
    nvidia_enable_thinking: bool = True
    llm_field_fallback: bool = False

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # LM Studio (local OpenAI-compatible endpoint)
    lmstudio_api_base: str = "http://127.0.0.1:1234/v1"
    lmstudio_api_key: str = "lm-studio"
    lmstudio_model: str = "mistralai/devstral-small-2505"
    lmstudio_embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    lmstudio_max_tokens: int = 8192
    lmstudio_temperature: float = 0.3

    # Code Brain agent routing: single (Devstral for all) | multi (Devstral + Qwen + Gemma)
    brain_agent_mode: str = "single"
    lmstudio_brain_api_base: str = "http://127.0.0.1:1234/v1"
    lmstudio_brain_model: str = "mistralai/devstral-small-2505"
    lmstudio_rca_api_base: str = ""
    lmstudio_rca_model: str = "qwen/qwen3.6-35b-a3b"
    lmstudio_vision_api_base: str = ""
    lmstudio_vision_model: str = "google/gemma-4-26b-a4b-qat"

    # Knowledge Engine
    chroma_dir: Path = Path("./data/chroma")
    azure_devops_workspace_dir: Path = Path("./data/azure_workspaces")
    local_workspace_dir: Path = Path("./data/local_workspaces")
    max_upload_bytes: int = 500 * 1024 * 1024
    upload_batch_max_files: int = 200

    firebase_project_id: str = "code-automation-tool"
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
