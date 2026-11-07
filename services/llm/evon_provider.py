"""Gnani Evon v3.3 Adapter for Vyapar Mitra.

Adapter for Gnani Evon v3.3 foundation model (hybrid Mamba2-Transformer MoE).
Supports:
- Self-hosted vLLM or llama.cpp OpenAI-compatible server
- Enterprise hosted Vachana LLM endpoint (when permitted by API key scopes)

Gracefully detects and reports SCOPE_NOT_ALLOWED without crashing or masking errors.
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
    LLMScopeNotAllowedError,
    LLMQuotaExceededError,
    LLMModelUnavailableError
)
from services.llm.base import LLMProvider

logger = structlog.get_logger()

DEFAULT_EVON_BASE = "https://api.vachana.ai"
DEFAULT_EVON_MODEL = "gnani/gnani-evon-v3.3-30B-A3B"


class GnaniEvonProvider(LLMProvider):
    """Gnani Evon v3.3 adapter supporting Vachana and vLLM inference."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        from apps.api.core.config import settings
        self.api_key = (
            api_key
            or getattr(settings, "EVON_API_KEY", "")
            or getattr(settings, "GNANI_API_KEY", "")
        )
        self.base_url = (
            base_url
            or getattr(settings, "EVON_BASE_URL", "")
            or DEFAULT_EVON_BASE
        ).rstrip("/")
        self.model = (
            model
            or getattr(settings, "EVON_MODEL", "")
            or DEFAULT_EVON_MODEL
        )
        self._external_client = http_client

    @property
    def provider_name(self) -> str:
        return "gnani_evon"

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
        return await self._execute(
            messages=messages,
            tools=None,
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
        return await self._execute(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )

    async def _execute(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolDefinition]],
        temperature: float,
        max_tokens: int,
        timeout: float
    ) -> LLMResponse:
        if not self.is_configured:
            raise LLMAuthenticationError(
                "Neither EVON_API_KEY nor GNANI_API_KEY is configured.",
                provider=self.provider_name,
                status_code=401
            )

        # Standard OpenAI / vLLM endpoint path
        endpoint_url = f"{self.base_url}/v1/chat/completions"
        if "api.vachana.ai" in self.base_url and not self.base_url.endswith("/v1"):
            # Vachana standard auth header
            headers = {
                "X-API-Key-ID": self.api_key,
                "Content-Type": "application/json"
            }
        else:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

        formatted_messages = []
        for m in messages:
            if isinstance(m, dict):
                r = m.get("role", "user")
                c = m.get("content", "")
            else:
                r = m.role.value if isinstance(m.role, LLMRole) else str(m.role)
                c = m.content or ""
            formatted_messages.append({"role": r, "content": c})

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            body["tools"] = [t.model_dump(mode="json") for t in tools]

        t0 = time.perf_counter()
        try:
            if self._external_client:
                res = await self._external_client.post(endpoint_url, headers=headers, json=body, timeout=timeout)
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    res = await client.post(endpoint_url, headers=headers, json=body)

            latency = round(time.perf_counter() - t0, 3)

            if res.status_code == 200:
                data = res.json()
                return self._parse_openai_response(data, latency)

            # Detect Scope Not Allowed
            err_text = res.text[:300]
            if res.status_code == 403 and "SCOPE_NOT_ALLOWED" in err_text:
                raise LLMScopeNotAllowedError(
                    "Gnani account API key is valid for Prisma/Timbre but lacks 'LLM/Evon' hosted scope.",
                    provider=self.provider_name,
                    status_code=403
                )
            elif res.status_code == 401:
                raise LLMAuthenticationError(f"Evon authentication failed: {err_text}", provider=self.provider_name, status_code=401)
            elif res.status_code == 429:
                raise LLMQuotaExceededError("Evon rate limit reached.", provider=self.provider_name, status_code=429)
            elif res.status_code in (404, 502, 503):
                raise LLMModelUnavailableError(f"Evon endpoint unavailable (HTTP {res.status_code}): {err_text}", provider=self.provider_name, status_code=res.status_code)
            else:
                raise LLMProviderError(f"Evon API error (HTTP {res.status_code}): {err_text}", provider=self.provider_name, status_code=res.status_code)

        except httpx.TimeoutException:
            raise LLMProviderError(f"Evon request timed out after {timeout}s.", provider=self.provider_name, status_code=504)

    def _parse_openai_response(self, data: Dict[str, Any], latency: float) -> LLMResponse:
        choices = data.get("choices", [])
        if not choices:
            raise LLMProviderError("Empty choices in Evon response.", provider=self.provider_name)

        msg = choices[0].get("message", {})
        content = msg.get("content")

        tool_calls = []
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            tool_calls.append(LLMToolCall(id=tc.get("id", "call_evon"), name=fn.get("name", ""), arguments=args))

        u = data.get("usage", {})
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            provider=self.provider_name,
            model=data.get("model", self.model),
            usage=LLMUsage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
                estimated_cost_inr=0.0
            ),
            latency_seconds=latency,
            finish_reason=choices[0].get("finish_reason", "stop"),
            raw_response=data
        )

