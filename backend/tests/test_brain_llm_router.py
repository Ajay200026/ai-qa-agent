"""Tests for hybrid NVIDIA + local LLM routing."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.brain_llm_router import (
    _redact_secrets,
    get_analysis_llm,
    get_brain_llm,
    get_chat_agent_llm,
    get_scan_llm,
    uses_cloud_routing,
    uses_hybrid_routing,
)


@pytest.fixture
def hybrid_settings():
    settings = MagicMock()
    settings.llm_routing_mode = "hybrid"
    settings.scan_llm_provider = "nvidia"
    settings.llm_provider = "lmstudio"
    settings.lmstudio_api_key = "lm-studio"
    settings.lmstudio_api_base = "http://127.0.0.1:1234/v1"
    settings.lmstudio_brain_api_base = "http://127.0.0.1:1234/v1"
    settings.lmstudio_brain_model = "mistralai/devstral-small-2505"
    settings.lmstudio_model = "mistralai/devstral-small-2505"
    settings.lmstudio_temperature = 0.3
    settings.lmstudio_max_tokens = 8192
    settings.lmstudio_rca_api_base = ""
    settings.lmstudio_vision_api_base = ""
    settings.lmstudio_rca_model = "qwen/qwen3.6-35b-a3b"
    settings.lmstudio_vision_model = "google/gemma-4-26b-a4b-qat"
    settings.nvidia_api_key = "nvapi-test-key"
    settings.nvidia_api_base = "https://integrate.api.nvidia.com/v1"
    settings.nvidia_chat_model = "z-ai/glm-5.2"
    settings.nvidia_scan_model = "google/gemma-4-31b-it"
    settings.nvidia_analysis_model = "google/gemma-4-31b-it"
    settings.nvidia_automation_model = "z-ai/glm-5.2"
    settings.nvidia_max_tokens = 16384
    settings.nvidia_chat_temperature = 1.0
    settings.nvidia_scan_temperature = 0.2
    settings.nvidia_analysis_temperature = 1.0
    settings.nvidia_enable_thinking = True
    settings.brain_agent_mode = "multi"
    settings.openai_api_key = ""
    settings.openai_model = "gpt-4o"
    settings.nvidia_model = "minimaxai/minimax-m3"
    return settings


def test_redact_secrets_strips_nvapi_keys():
    msg = "Auth failed: Bearer nvapi-secretKey123_abc"
    assert "nvapi-secretKey123_abc" not in _redact_secrets(msg)
    assert "nvapi-***" in _redact_secrets(msg)


@patch("app.core.brain_llm_router.get_settings")
@patch("app.core.brain_llm_router.ChatOpenAI")
def test_get_brain_llm_uses_nvidia_gemma(mock_chat, mock_settings, hybrid_settings):
    mock_settings.return_value = hybrid_settings
    get_brain_llm(temperature=0.2)
    mock_chat.assert_called_once()
    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["model"] == "google/gemma-4-31b-it"
    assert call_kwargs["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert call_kwargs.get("model_kwargs") == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


@patch("app.core.brain_llm_router.get_settings")
@patch("app.core.brain_llm_router.ChatOpenAI")
def test_get_scan_llm_aliases_brain(mock_chat, mock_settings, hybrid_settings):
    mock_settings.return_value = hybrid_settings
    get_scan_llm()
    mock_chat.assert_called_once()
    assert mock_chat.call_args.kwargs["model"] == "google/gemma-4-31b-it"


@patch("app.core.brain_llm_router.get_settings")
@patch("app.core.brain_llm_router.ChatOpenAI")
def test_get_chat_agent_llm_uses_nvidia_glm(mock_chat, mock_settings, hybrid_settings):
    mock_settings.return_value = hybrid_settings
    get_chat_agent_llm()
    mock_chat.assert_called_once()
    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["model"] == "z-ai/glm-5.2"
    assert "model_kwargs" not in call_kwargs or call_kwargs.get("model_kwargs") is None


@patch("app.core.brain_llm_router.get_agent_mode_sync", return_value="multi")
@patch("app.core.brain_llm_router.get_settings")
@patch("app.core.brain_llm_router.ChatOpenAI")
def test_get_analysis_llm_enables_thinking(mock_chat, mock_settings, mock_mode, hybrid_settings):
    mock_settings.return_value = hybrid_settings
    get_analysis_llm()
    mock_chat.assert_called_once()
    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["model"] == "google/gemma-4-31b-it"
    assert call_kwargs.get("model_kwargs") == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


@patch("app.core.brain_llm_router.get_settings")
def test_hybrid_routing_flags(mock_settings, hybrid_settings):
    mock_settings.return_value = hybrid_settings
    assert uses_hybrid_routing() is True
    assert uses_cloud_routing() is True


@patch("app.core.brain_llm_router.get_settings")
@patch("app.core.brain_llm_router.ChatOpenAI")
def test_brain_llm_falls_back_to_lmstudio_when_no_nvidia_key(mock_chat, mock_settings, hybrid_settings):
    hybrid_settings.nvidia_api_key = ""
    mock_settings.return_value = hybrid_settings
    llm = get_brain_llm()
    assert llm is not None
    mock_chat.assert_called_once()
    assert mock_chat.call_args.kwargs["base_url"] == "http://127.0.0.1:1234/v1"
