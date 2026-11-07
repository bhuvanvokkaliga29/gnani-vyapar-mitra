"""OpenRouter LLM Provider for Vyapar Mitra.

Connects to OpenRouter.ai REST API (OpenAI-compatible) with native support for:
- Free models: google/gemma-4-31b-it:free, google/gemma-4-26b-a4b-it:free
- Dynamic tool/function calling
- Automatic candidate fallback on rate-limit (429) or endpoint unavailability (404/503)
"""

import json
import time
from typing import List, Optional, Dict, Any
import httpx
import structlog

from domain.llm_schemas import (
    LLMRole,
    LLMMessage,
    LLMToolDefinition,
    LLMToolCall,
    LLMResponse,
    LLMUsage,
    LLMProviderError,
    LLMAuthenticationError,
    LLMQuotaExceededError,
    LLMModelUnavailableError
)
from services.llm.base import LLMProvider

logger = structlog.get_logger()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_PRIMARY_MODEL = "google/gemma-4-31b-it:free"
DEFAULT_FALLBACK_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
]


class OpenRouterProvider(LLMProvider):
    """OpenRouter API client supporting free and open-source models with tool use."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        from apps.api.core.config import settings
        self.api_key = api_key if api_key is not None else getattr(settings, "OPENROUTER_API_KEY", "")
        self.model = model or getattr(settings, "OPENROUTER_MODEL", DEFAULT_PRIMARY_MODEL)
        self.fallback_models = (
            fallback_models
            if fallback_models is not None
            else getattr(settings, "OPENROUTER_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS)
        )
        self.base_url = (base_url or OPENROUTER_API_URL).rstrip("/")
        self._external_client = http_client

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("mock_"))

    @property
    def active_model(self) -> str:
        return self.model

    async def chat_complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float = 15.0
    ) -> LLMResponse:
        return await self._execute_chat(
            messages=messages,
            tools=None,
            tool_choice=None,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )

    async def chat_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        tool_choice: str = "auto",
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float = 15.0
    ) -> LLMResponse:
        return await self._execute_chat(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )

    async def _execute_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolDefinition]],
        tool_choice: Optional[str],
        temperature: float,
        max_tokens: int,
        timeout: float
    ) -> LLMResponse:
        """Execute chat completion with automatic model fallback."""
        if not self.is_configured:
            raise LLMAuthenticationError(
                "OPENROUTER_API_KEY is not configured.",
                provider=self.provider_name,
                status_code=401
            )

        candidate_models = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_error = None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://vyaparmitra.in",
            "X-Title": "Vyapar Mitra AI Business Agent",
            "Content-Type": "application/json"
        }

        formatted_messages = self._format_messages(messages)
        tools_payload = [t.model_dump(mode="json") for t in tools] if tools else None

        for target_model in candidate_models:
            body: Dict[str, Any] = {
                "model": target_model,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if tools_payload:
                body["tools"] = tools_payload
                if tool_choice:
                    body["tool_choice"] = tool_choice

            t0 = time.perf_counter()
            try:
                if self._external_client:
                    res = await self._external_client.post(self.base_url, headers=headers, json=body, timeout=timeout)
                else:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        res = await client.post(self.base_url, headers=headers, json=body)

                latency = round(time.perf_counter() - t0, 3)

                if res.status_code == 200:
                    data = res.json()
                    return self._parse_success_response(data, target_model, latency)

                # Error categorization
                if res.status_code == 401:
                    raise LLMAuthenticationError(
                        "Invalid OpenRouter API Key.",
                        provider=self.provider_name,
                        status_code=401
                    )
                elif res.status_code == 429:
                    logger.warning("openrouter_rate_limit_exceeded", model=target_model, status_code=429)
                    last_error = LLMQuotaExceededError(
                        f"Rate limit exceeded for model '{target_model}'.",
                        provider=self.provider_name,
                        status_code=429
                    )
                    # Try next fallback model
                    continue
                elif res.status_code in (404, 503):
                    logger.warning("openrouter_model_unavailable", model=target_model, status_code=res.status_code)
                    last_error = LLMModelUnavailableError(
                        f"Model '{target_model}' unavailable on OpenRouter (Status {res.status_code}).",
                        provider=self.provider_name,
                        status_code=res.status_code
                    )
                    continue
                else:
                    err_msg = res.text[:200]
                    raise LLMProviderError(
                        f"OpenRouter API returned HTTP {res.status_code}: {err_msg}",
                        provider=self.provider_name,
                        status_code=res.status_code
                    )

            except httpx.TimeoutException:
                logger.warning("openrouter_timeout_attempting_fallback", model=target_model, timeout=timeout)
                last_error = LLMProviderError(
                    f"Request to '{target_model}' timed out after {timeout}s.",
                    provider=self.provider_name,
                    status_code=504
                )
                continue
            except (LLMAuthenticationError, LLMProviderError) as e:
                # Re-raise explicit authentication or fatal provider errors immediately
                if isinstance(e, LLMAuthenticationError):
                    raise
                last_error = e

        if last_error:
            raise last_error
        raise LLMModelUnavailableError(
            "All OpenRouter candidate models failed or exhausted quotas.",
            provider=self.provider_name
        )

    def _format_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert internal LLMMessage to OpenAI/OpenRouter message wire format."""
        formatted = []
        for m in messages:
            item: Dict[str, Any] = {
                "role": m.role.value if isinstance(m.role, LLMRole) else str(m.role),
                "content": m.content or ""
            }
            if m.name:
                item["name"] = m.name
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)
                        }
                    }
                    for tc in m.tool_calls
                ]
            formatted.append(item)
        return formatted

    def _parse_success_response(self, data: Dict[str, Any], model: str, latency: float) -> LLMResponse:
        """Parse raw OpenRouter response dictionary into normalized LLMResponse."""
        choices = data.get("choices", [])
        if not choices:
            raise LLMProviderError("Empty choices array in OpenRouter response.", provider=self.provider_name)

        first_choice = choices[0]
        msg = first_choice.get("message", {})
        content = msg.get("content")
        raw_tool_calls = msg.get("tool_calls", [])
        parsed_tool_calls: List[LLMToolCall] = []

        if raw_tool_calls:
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {"raw_arguments": raw_args}

                parsed_tool_calls.append(
                    LLMToolCall(
                        id=tc.get("id", f"call_{len(parsed_tool_calls)}"),
                        name=fn.get("name", ""),
                        arguments=args
                    )
                )

        usage_dict = data.get("usage", {})
        usage = LLMUsage(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
            estimated_cost_inr=0.0  # Free tier default
        )

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            provider=self.provider_name,
            model=data.get("model", model),
            usage=usage,
            latency_seconds=latency,
            finish_reason=first_choice.get("finish_reason", "stop"),
            raw_response=data
        )

