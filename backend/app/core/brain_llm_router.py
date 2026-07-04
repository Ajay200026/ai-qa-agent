"""Task-based LLM routing: local scan/embeddings + NVIDIA chat/analysis in hybrid mode."""

from __future__ import annotations

import logging
import time
from enum import Enum

import httpx
from langchain_openai import ChatOpenAI

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_agent_mode_cache: tuple[str, float] | None = None
_CACHE_TTL = 5.0

NVIDIA_TIMEOUT_S = 120
LMSTUDIO_TIMEOUT_S = 30


class BrainAgentMode(str, Enum):
    SINGLE = "single"
    MULTI = "multi"


class LlmRoutingMode(str, Enum):
    HYBRID = "hybrid"
    LOCAL = "local"
    CLOUD = "cloud"


def invalidate_agent_mode_cache() -> None:
    global _agent_mode_cache
    _agent_mode_cache = None


def set_agent_mode_cache(mode: str) -> None:
    global _agent_mode_cache
    _agent_mode_cache = (mode, time.time())


def get_agent_mode_sync() -> str:
    global _agent_mode_cache
    settings = get_settings()
    if _agent_mode_cache:
        mode, ts = _agent_mode_cache
        if time.time() - ts < _CACHE_TTL:
            return mode
    return settings.brain_agent_mode


def get_routing_mode() -> str:
    return get_settings().llm_routing_mode.lower().strip()


def uses_hybrid_routing() -> bool:
    return get_routing_mode() == LlmRoutingMode.HYBRID.value


def uses_cloud_routing() -> bool:
    mode = get_routing_mode()
    return mode in {LlmRoutingMode.HYBRID.value, LlmRoutingMode.CLOUD.value}


def _lmstudio_chat(
    settings: Settings,
    *,
    base_url: str,
    model: str,
    temperature: float,
    timeout: int = LMSTUDIO_TIMEOUT_S,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=settings.lmstudio_api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=settings.lmstudio_max_tokens,
        timeout=timeout,
        max_retries=1,
    )


def _nvidia_chat(
    settings: Settings,
    *,
    model: str,
    temperature: float,
    thinking: bool = False,
) -> ChatOpenAI | None:
    if not settings.nvidia_api_key:
        return None
    model_kwargs: dict = {}
    if thinking and settings.nvidia_enable_thinking:
        model_kwargs["chat_template_kwargs"] = {"enable_thinking": True}
    kwargs: dict = {
        "model": model,
        "api_key": settings.nvidia_api_key,
        "base_url": settings.nvidia_api_base,
        "temperature": temperature,
        "max_tokens": settings.nvidia_max_tokens,
        "timeout": NVIDIA_TIMEOUT_S,
        "max_retries": 1,
    }
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs
    return ChatOpenAI(**kwargs)


def _scan_base_url(settings: Settings) -> str:
    return settings.lmstudio_brain_api_base or settings.lmstudio_api_base


def _scan_model(settings: Settings) -> str:
    return settings.lmstudio_brain_model or settings.lmstudio_model


def _brain_model(settings: Settings) -> str:
    return settings.nvidia_scan_model or settings.nvidia_analysis_model


def _redact_secrets(message: str) -> str:
    """Strip API key fragments from log/error text."""
    import re

    return re.sub(r"nvapi-[A-Za-z0-9_-]+", "nvapi-***", message)


def get_brain_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """NVIDIA Gemma — repo scan, summarization, brain enrichment, and graph prep."""
    settings = get_settings()
    if uses_cloud_routing() and settings.nvidia_api_key:
        temp = temperature if temperature is not None else settings.nvidia_scan_temperature
        return _nvidia_chat(
            settings,
            model=_brain_model(settings),
            temperature=temp,
            thinking=True,
        )
    if settings.scan_llm_provider == "lmstudio" or settings.lmstudio_api_base:
        temp = temperature if temperature is not None else settings.lmstudio_temperature
        return _lmstudio_chat(
            settings,
            base_url=_scan_base_url(settings),
            model=_scan_model(settings),
            temperature=temp,
        )
    return None


def get_scan_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """Alias for get_brain_llm() — scan pipeline and graph preparation."""
    return get_brain_llm(temperature=temperature)


def get_chat_agent_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """Streaming chat / Ask AI — NVIDIA GLM in hybrid/cloud, LM Studio in local mode."""
    settings = get_settings()
    if uses_cloud_routing() and settings.nvidia_api_key:
        temp = temperature if temperature is not None else settings.nvidia_chat_temperature
        llm = _nvidia_chat(
            settings,
            model=settings.nvidia_chat_model,
            temperature=temp,
            thinking=False,
        )
        if llm is not None:
            return llm
    if get_routing_mode() == LlmRoutingMode.CLOUD.value:
        return None
    temp = temperature if temperature is not None else settings.lmstudio_temperature
    return _lmstudio_chat(
        settings,
        base_url=_scan_base_url(settings),
        model=_scan_model(settings),
        temperature=temp,
    )


def get_analysis_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """RCA, validation, reports, code analysis — NVIDIA Gemma with thinking in hybrid/cloud."""
    settings = get_settings()
    mode = get_agent_mode_sync()

    if uses_cloud_routing() and settings.nvidia_api_key:
        if mode == BrainAgentMode.MULTI.value:
            temp = temperature if temperature is not None else settings.nvidia_analysis_temperature
            llm = _nvidia_chat(
                settings,
                model=settings.nvidia_analysis_model,
                temperature=temp,
                thinking=True,
            )
            if llm is not None:
                return llm
        else:
            return get_chat_agent_llm(temperature=temperature)

    if mode == BrainAgentMode.MULTI.value and settings.lmstudio_rca_api_base:
        temp = temperature if temperature is not None else 0.2
        return _lmstudio_chat(
            settings,
            base_url=settings.lmstudio_rca_api_base,
            model=settings.lmstudio_rca_model,
            temperature=temp,
        )
    return get_brain_llm(temperature=temperature)


def get_rca_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    return get_analysis_llm(temperature=temperature)


def get_vision_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    settings = get_settings()
    mode = get_agent_mode_sync()
    temp = temperature if temperature is not None else 0.2

    if uses_cloud_routing() and settings.nvidia_api_key and mode == BrainAgentMode.MULTI.value:
        return get_analysis_llm(temperature=temp)

    if mode == BrainAgentMode.MULTI.value and settings.lmstudio_vision_api_base:
        return _lmstudio_chat(
            settings,
            base_url=settings.lmstudio_vision_api_base,
            model=settings.lmstudio_vision_model,
            temperature=temp,
        )
    return get_scan_llm(temperature=temp)


def get_automation_agent_llm(*, temperature: float | None = None) -> ChatOpenAI | None:
    """Playwright automation fallback — NVIDIA in hybrid/cloud."""
    settings = get_settings()
    if uses_cloud_routing() and settings.nvidia_api_key:
        temp = temperature if temperature is not None else 0.1
        model = settings.nvidia_automation_model or settings.nvidia_chat_model
        return _nvidia_chat(settings, model=model, temperature=temp, thinking=False)
    if settings.llm_provider == "lmstudio":
        temp = temperature if temperature is not None else 0.1
        return _lmstudio_chat(
            settings,
            base_url=settings.lmstudio_api_base,
            model=settings.lmstudio_model,
            temperature=temp,
        )
    if settings.llm_provider == "nvidia" and settings.nvidia_api_key:
        temp = temperature if temperature is not None else 0.1
        model = settings.nvidia_automation_model or settings.nvidia_model
        return _nvidia_chat(settings, model=model, temperature=temp, thinking=False)
    if settings.openai_api_key:
        temp = temperature if temperature is not None else 0.1
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temp,
        )
    return None


async def _check_lmstudio(base_url: str) -> bool:
    try:
        url = base_url.rstrip("/") + "/models"
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


async def _check_nvidia(settings: Settings) -> bool:
    if not settings.nvidia_api_key:
        return False
    try:
        url = settings.nvidia_api_base.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {settings.nvidia_api_key}"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
            return resp.status_code == 200
    except Exception:
        return False


async def is_scan_llm_available() -> bool:
    settings = get_settings()
    if uses_cloud_routing() and settings.scan_llm_provider == "nvidia":
        return await _check_nvidia(settings)
    if settings.scan_llm_provider == "lmstudio" or (
        uses_cloud_routing() and not settings.nvidia_api_key
    ):
        return await _check_lmstudio(_scan_base_url(settings))
    return False


async def is_cloud_llm_available() -> bool:
    settings = get_settings()
    if not uses_cloud_routing():
        return False
    return await _check_nvidia(settings)


async def is_brain_llm_available() -> bool:
    """Brain/scan LLM (NVIDIA Gemma in hybrid, or local LM Studio fallback)."""
    return await is_scan_llm_available()


async def check_brain_llm_health() -> dict:
    settings = get_settings()
    mode = get_agent_mode_sync()
    routing = get_routing_mode()
    hybrid = routing == LlmRoutingMode.HYBRID.value

    scan_base = _scan_base_url(settings)
    embed_ok = await _check_lmstudio(settings.lmstudio_api_base)
    nvidia_ok = await _check_nvidia(settings) if uses_cloud_routing() else False
    scan_ok = (
        nvidia_ok
        if hybrid and settings.scan_llm_provider == "nvidia"
        else await _check_lmstudio(scan_base)
    )

    if hybrid:
        chat_ok = nvidia_ok
        analysis_ok = nvidia_ok
        automation_ok = nvidia_ok
        scan_model = _brain_model(settings)
        chat_model = settings.nvidia_chat_model
        analysis_model = settings.nvidia_analysis_model
        automation_model = settings.nvidia_automation_model or settings.nvidia_chat_model
        degraded = not nvidia_ok or not embed_ok
    elif routing == LlmRoutingMode.CLOUD.value:
        chat_ok = analysis_ok = automation_ok = nvidia_ok
        scan_ok = nvidia_ok
        scan_model = _brain_model(settings)
        chat_model = settings.nvidia_chat_model
        analysis_model = settings.nvidia_analysis_model
        automation_model = settings.nvidia_automation_model or settings.nvidia_chat_model
        degraded = not nvidia_ok
    else:
        chat_ok = scan_ok
        analysis_ok = scan_ok
        automation_ok = scan_ok
        scan_model = _scan_model(settings)
        chat_model = scan_model
        analysis_model = (
            settings.lmstudio_rca_model
            if mode == BrainAgentMode.MULTI.value
            else scan_model
        )
        automation_model = settings.lmstudio_model
        rca_local = False
        vision_local = False
        if mode == BrainAgentMode.MULTI.value:
            if settings.lmstudio_rca_api_base:
                rca_local = await _check_lmstudio(settings.lmstudio_rca_api_base)
            if settings.lmstudio_vision_api_base:
                vision_local = await _check_lmstudio(settings.lmstudio_vision_api_base)
            analysis_ok = rca_local if settings.lmstudio_rca_api_base else scan_ok
            degraded = not scan_ok or (
                bool(settings.lmstudio_rca_api_base) and not rca_local
            ) or (
                bool(settings.lmstudio_vision_api_base) and not vision_local
            )
        else:
            degraded = not scan_ok

    return {
        "agent_mode": mode,
        "routing_mode": routing,
        "models": {
            "scan": scan_model,
            "chat": chat_model,
            "analysis": analysis_model,
            "automation": automation_model,
            "brain": scan_model,
            "rca": analysis_model,
            "vision": analysis_model,
        },
        "scan_available": scan_ok,
        "chat_available": chat_ok,
        "analysis_available": analysis_ok,
        "automation_available": automation_ok,
        "brain_available": scan_ok,
        "rca_available": analysis_ok,
        "vision_available": analysis_ok,
        "degraded": degraded,
    }


def is_multi_agent_mode() -> bool:
    return get_agent_mode_sync() == BrainAgentMode.MULTI.value
