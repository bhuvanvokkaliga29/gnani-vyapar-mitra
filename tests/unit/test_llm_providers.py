"""Unit Tests for Stage C Provider-Agnostic LLM Architecture.

Validates:
1. LLM Schemas & Tool Definitions
2. OpenRouterProvider (Gemma-4 Free support, tool calling, model fallback)
3. GeminiProvider (Gemini 2.0/1.5 Flash, function declarations, token costing)
4. GnaniEvonProvider (SCOPE_NOT_ALLOWED handling, vLLM / OpenAI spec)
5. LLMProviderFactory & LLMFallbackRouter resilience
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
import httpx

from domain.llm_schemas import (
    LLMRole,
    LLMMessage,
    LLMToolDefinition,
    LLMFunctionDeclaration,
    LLMToolCall,
    LLMResponse,
    LLMAuthenticationError,
    LLMScopeNotAllowedError,
    LLMQuotaExceededError,
    LLMModelUnavailableError
)
from services.llm.openrouter_provider import OpenRouterProvider
from services.llm.gemini_provider import GeminiProvider
from services.llm.evon_provider import GnaniEvonProvider
from services.llm.factory import LLMProviderFactory, LLMFallbackRouter


# =============================================================================
# 1. LLM Schema Validation Tests
# =============================================================================

def test_llm_message_and_tool_call_schemas():
    tc = LLMToolCall(id="call_123", name="get_daily_sales", arguments={"target_date": "2026-11-06"})
    assert tc.name == "get_daily_sales"
    assert tc.arguments["target_date"] == "2026-11-06"

    msg = LLMMessage(role=LLMRole.ASSISTANT, content="Checking sales...", tool_calls=[tc])
    assert msg.role == LLMRole.ASSISTANT
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].name == "get_daily_sales"


def test_llm_tool_definition_schema():
    decl = LLMFunctionDeclaration(
        name="get_inventory_health",
        description="Check stock levels and dead inventory",
        parameters={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Apparel category"}
            }
        }
    )
    tool = LLMToolDefinition(function=decl)
    assert tool.type == "function"
    assert tool.function.name == "get_inventory_health"
    d = tool.model_dump(mode="json")
    assert d["function"]["name"] == "get_inventory_health"


# =============================================================================
# 2. OpenRouter Provider Tests
# =============================================================================

@pytest.mark.asyncio
async def test_openrouter_provider_unconfigured():
    provider = OpenRouterProvider(api_key="")
    assert provider.is_configured is False
    with pytest.raises(LLMAuthenticationError) as exc:
        await provider.chat_complete([LLMMessage(role=LLMRole.USER, content="Hello")])
    assert "not configured" in str(exc.value)


@pytest.mark.asyncio
async def test_openrouter_provider_success_with_tools():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "gen-12345",
        "model": "google/gemma-4-31b-it:free",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "I am checking your daily sales.",
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "get_daily_sales",
                                "arguments": '{"target_date": "2026-11-06"}'
                            }
                        }
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60}
    }
    mock_http.post.return_value = mock_resp

    provider = OpenRouterProvider(api_key="sk-or-test-key", model="google/gemma-4-31b-it:free", http_client=mock_http)
    assert provider.is_configured is True
    assert provider.active_model == "google/gemma-4-31b-it:free"

    tool = LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_daily_sales",
            description="Retrieve daily sales numbers"
        )
    )

    res = await provider.chat_with_tools(
        messages=[LLMMessage(role=LLMRole.USER, content="How are sales today?")],
        tools=[tool]
    )

    assert res.provider == "openrouter"
    assert res.content == "I am checking your daily sales."
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "get_daily_sales"
    assert res.tool_calls[0].arguments == {"target_date": "2026-11-06"}
    assert res.usage.total_tokens == 60


@pytest.mark.asyncio
async def test_openrouter_fallback_on_rate_limit():
    mock_http = AsyncMock()
    # First call (primary gemma-4-31b) -> 429 Rate Limit
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Rate limit exceeded"

    # Second call (fallback gemma-4-26b) -> 200 OK
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "model": "google/gemma-4-26b-a4b-it:free",
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "Fallback answer in Kannada: ಮಾರಾಟ ಉತ್ತಮವಾಗಿದೆ"}}]
    }
    mock_http.post.side_effect = [resp_429, resp_200]

    provider = OpenRouterProvider(
        api_key="sk-or-test-key",
        model="google/gemma-4-31b-it:free",
        fallback_models=["google/gemma-4-26b-a4b-it:free"],
        http_client=mock_http
    )

    res = await provider.chat_complete([LLMMessage(role=LLMRole.USER, content="ಮಾರಾಟ ಹೇಗಿದೆ?")])
    assert res.content == "Fallback answer in Kannada: ಮಾರಾಟ ಉತ್ತಮವಾಗಿದೆ"
    assert res.model == "google/gemma-4-26b-a4b-it:free"
    assert mock_http.post.call_count == 2


# =============================================================================
# 3. Gemini Provider Tests
# =============================================================================

@pytest.mark.asyncio
async def test_gemini_provider_unconfigured():
    provider = GeminiProvider(api_key="")
    assert provider.is_configured is False
    with pytest.raises(LLMAuthenticationError):
        await provider.chat_complete([LLMMessage(role=LLMRole.USER, content="Hi")])


@pytest.mark.asyncio
async def test_gemini_provider_function_call_parsing():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "get_profit_summary",
                                "args": {"days": 30}
                            }
                        }
                    ],
                    "role": "model"
                },
                "finishReason": "STOP"
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 120,
            "candidatesTokenCount": 25,
            "totalTokenCount": 145
        }
    }
    mock_http.post.return_value = mock_resp

    provider = GeminiProvider(api_key="AIzaSyTestKey", model="gemini-2.0-flash", http_client=mock_http)
    assert provider.is_configured is True

    tool = LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_profit_summary",
            description="Retrieve gross margins and profits"
        )
    )

    res = await provider.chat_with_tools(
        messages=[LLMMessage(role=LLMRole.USER, content="ಲಾಭ ಎಷ್ಟು ಬಂದಿದೆ?")],
        tools=[tool]
    )

    assert res.provider == "gemini"
    assert res.model == "gemini-2.0-flash"
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "get_profit_summary"
    assert res.tool_calls[0].arguments == {"days": 30}
    assert res.usage.total_tokens == 145
    assert res.usage.estimated_cost_inr > 0.0


# =============================================================================
# 4. Gnani Evon Adapter Tests
# =============================================================================

@pytest.mark.asyncio
async def test_gnani_evon_scope_not_allowed_detection():
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = '{"detail":{"error_code":"SCOPE_NOT_ALLOWED","message":"Service \'None\' not in allowed scopes"}}'
    mock_http.post.return_value = mock_resp

    provider = GnaniEvonProvider(api_key="gnani_vachana_key", http_client=mock_http)
    assert provider.is_configured is True

    with pytest.raises(LLMScopeNotAllowedError) as exc:
        await provider.chat_complete([LLMMessage(role=LLMRole.USER, content="Hello Evon")])

    assert "lacks 'LLM/Evon' hosted scope" in str(exc.value)


# =============================================================================
# 5. Factory & Fallback Router Tests
# =============================================================================

@pytest.mark.asyncio
async def test_llm_fallback_router_switches_to_secondary():
    primary = OpenRouterProvider(api_key="fake_key")
    secondary = GeminiProvider(api_key="fake_key")

    # Primary throws QuotaExceeded
    primary.chat_complete = AsyncMock(side_effect=LLMQuotaExceededError("Rate limit", provider="openrouter", status_code=429))
    
    # Secondary succeeds
    mock_res = LLMResponse(
        content="Secondary Gemini Response",
        provider="gemini",
        model="gemini-2.0-flash"
    )
    secondary.chat_complete = AsyncMock(return_value=mock_res)

    router = LLMFallbackRouter(primary=primary, secondary=secondary)
    res = await router.chat_complete([LLMMessage(role=LLMRole.USER, content="Test")])

    assert res.content == "Secondary Gemini Response"
    assert "fallback_from_openrouter" in res.finish_reason
    assert primary.chat_complete.call_count == 1
    assert secondary.chat_complete.call_count == 1


def test_llm_provider_factory_resolution(monkeypatch):
    monkeypatch.setattr("apps.api.core.config.settings.LLM_PROVIDER", "gemini")
    monkeypatch.setattr("apps.api.core.config.settings.GEMINI_API_KEY", "test_gemini_key")
    provider = LLMProviderFactory.get_provider("gemini", enable_fallback=False)
    assert isinstance(provider, GeminiProvider)
    assert provider.provider_name == "gemini"

    evon_provider = LLMProviderFactory.get_provider("gnani_evon", enable_fallback=False)
    assert isinstance(evon_provider, GnaniEvonProvider)
    assert evon_provider.provider_name == "gnani_evon"

