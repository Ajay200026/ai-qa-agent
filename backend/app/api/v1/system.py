"""System metadata endpoints (LLM config, privacy flags)."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.deps import CurrentUser

router = APIRouter()


_LOCAL_PROVIDERS = {"none", "local", "ollama"}


@router.get("/config/llm")
async def get_llm_config(current_user: CurrentUser):
    settings = get_settings()
    provider = (settings.llm_provider or "none").lower().strip()
    is_local = provider in _LOCAL_PROVIDERS
    has_key = bool(
        (provider == "nvidia" and settings.nvidia_api_key)
        or (provider == "openai" and settings.openai_api_key)
    )
    enabled = (not is_local) and has_key
    return {
        "provider": provider,
        "is_local": is_local,
        "enabled": enabled,
        "llm_field_fallback": settings.llm_field_fallback,
    }
