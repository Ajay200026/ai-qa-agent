"""System metadata endpoints (LLM config, privacy flags)."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.deps import CurrentUser

router = APIRouter()


_LOCAL_PROVIDERS = {"none", "local", "ollama", "lmstudio"}


@router.get("/config/llm")
async def get_llm_config(current_user: CurrentUser):
    settings = get_settings()
    provider = (settings.llm_provider or "none").lower().strip()
    routing = (settings.llm_routing_mode or "hybrid").lower().strip()
    is_local = provider in _LOCAL_PROVIDERS or routing == "hybrid"
    has_key = bool(
        provider == "lmstudio"
        or (routing in {"hybrid", "cloud"} and settings.nvidia_api_key)
        or (provider == "nvidia" and settings.nvidia_api_key)
        or (provider == "openai" and settings.openai_api_key)
    )
    enabled = has_key
    chat_model = (
        settings.nvidia_chat_model
        if routing in {"hybrid", "cloud"}
        else settings.lmstudio_model
        if provider == "lmstudio"
        else settings.nvidia_model
        if provider == "nvidia"
        else settings.openai_model
        if provider == "openai"
        else None
    )
    return {
        "provider": provider,
        "routing_mode": routing,
        "is_local": is_local,
        "enabled": enabled,
        "llm_field_fallback": settings.llm_field_fallback,
        "api_base": settings.lmstudio_api_base if provider == "lmstudio" or routing == "hybrid" else None,
        "model": chat_model,
        "scan_model": settings.nvidia_scan_model if routing in {"hybrid", "cloud"} else None,
        "chat_model": settings.nvidia_chat_model if routing in {"hybrid", "cloud"} else chat_model,
        "analysis_model": settings.nvidia_analysis_model if routing in {"hybrid", "cloud"} else None,
        "embedding_model": settings.lmstudio_embedding_model,
    }
