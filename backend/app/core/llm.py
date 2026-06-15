import logging

from langchain_openai import ChatOpenAI

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"


def get_automation_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """LLM for UI automation fallback (Nemotron by default)."""
    settings = get_settings()
    if settings.llm_provider == "nvidia":
        if not settings.nvidia_api_key:
            return None
        temp = temperature if temperature is not None else 0.1
        model = settings.nvidia_automation_model or settings.nvidia_model
        logger.debug("Using NVIDIA automation model %s", model)
        return ChatOpenAI(
            model=model,
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_api_base,
            temperature=temp,
            max_tokens=settings.nvidia_max_tokens,
        )
    if settings.openai_api_key:
        temp = temperature if temperature is not None else 0.1
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temp,
        )
    return None


def get_chat_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """Return a chat LLM client (NVIDIA NIM or OpenAI-compatible)."""
    settings = get_settings()

    if settings.llm_provider == "nvidia":
        if not settings.nvidia_api_key:
            logger.warning("NVIDIA API key not configured")
            return None
        temp = temperature if temperature is not None else settings.nvidia_temperature
        logger.debug("Using NVIDIA model %s", settings.nvidia_model)
        return ChatOpenAI(
            model=settings.nvidia_model,
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_api_base,
            temperature=temp,
            max_tokens=settings.nvidia_max_tokens,
        )

    if settings.openai_api_key:
        temp = temperature if temperature is not None else 0
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temp,
        )

    return None


def is_llm_configured() -> bool:
    settings = get_settings()
    if settings.llm_provider == "nvidia":
        return bool(settings.nvidia_api_key)
    return bool(settings.openai_api_key)
