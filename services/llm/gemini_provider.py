"""Google Gemini LLM Provider for Vyapar Mitra.

Connects to Google AI Studio Gemini API via direct REST:
Models supported:
- gemini-2.0-flash (Recommended default)
- gemini-1.5-flash
- Custom configured model strings
Features:
- Native function declarations & structured tool calls
- Direct Indic language comprehension (Kannada, Hindi, English)
- Free tier and low-cost quota optimization
"""

import time
import uuid
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

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
GEMINI_FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview"
]

_SHARED_HTTP_CLIENT: Optional[httpx.AsyncClient] = None

def get_shared_gemini_client() -> httpx.AsyncClient:
    global _SHARED_HTTP_CLIENT
    if _SHARED_HTTP_CLIENT is None or _SHARED_HTTP_CLIENT.is_closed:
        _SHARED_HTTP_CLIENT = httpx.AsyncClient(
            timeout=12.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=60.0)
        )
    return _SHARED_HTTP_CLIENT


class GeminiProvider(LLMProvider):
    """Direct Google Gemini REST API client with structured function calling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        from apps.api.core.config import settings
        self.api_key = api_key if api_key is not None else (getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "LLM_API_KEY", ""))
        self.model = model or getattr(settings, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.base_url_template = base_url or GEMINI_API_BASE
        self._external_client = http_client

    @property
    def provider_name(self) -> str:
        return "gemini"

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
        timeout: float = 8.0
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
        timeout: float = 8.0
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
                "GEMINI_API_KEY is not configured.",
                provider=self.provider_name,
                status_code=401
            )

        client = self._external_client or get_shared_gemini_client()
        # Ultra-low latency priority: Prioritize production flash-lite for sub-second responses
        preferred_order = ["gemini-flash-lite-latest", "gemini-2.5-flash", self.model] + GEMINI_FALLBACK_MODELS
        seen = set()
        candidate_models = []
        for m in preferred_order:
            if m and m not in seen:
                seen.add(m)
                candidate_models.append(m)

        last_error = None
        for cand_model in candidate_models:
            url = f"{self.base_url_template.format(model=cand_model)}?key={self.api_key}"
            body = self._format_gemini_request(messages, tools, temperature, max_tokens)

            t0 = time.perf_counter()
            try:
                res = await client.post(url, json=body, timeout=timeout)
                latency = round(time.perf_counter() - t0, 3)

                if res.status_code == 200:
                    data = res.json()
                    return self._parse_gemini_response(data, latency)

                if res.status_code in (429, 404, 503):
                    # Try next fallback model immediately
                    last_error = f"Model {cand_model} returned HTTP {res.status_code}"
                    continue

                if res.status_code in (400, 401, 403):
                    err_text = res.text[:250]
                    if "API_KEY_INVALID" in err_text or "expired" in err_text.lower():
                        raise LLMAuthenticationError(f"Gemini authentication failed: {err_text}", provider=self.provider_name, status_code=res.status_code)
                    raise LLMProviderError(f"Gemini API request error (HTTP {res.status_code}): {err_text}", provider=self.provider_name, status_code=res.status_code)
                else:
                    raise LLMProviderError(f"Gemini server error (HTTP {res.status_code}): {res.text[:200]}", provider=self.provider_name, status_code=res.status_code)

            except httpx.TimeoutException:
                last_error = f"Model {cand_model} timed out after {timeout}s"
                continue

        raise LLMQuotaExceededError(f"All Gemini models exhausted. Last error: {last_error}", provider=self.provider_name, status_code=429)

    def _format_gemini_request(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolDefinition]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Convert standard LLMMessages and LLMTools to Gemini wire JSON format."""
        system_instructions: List[str] = []
        contents: List[Dict[str, Any]] = []

        for m in messages:
            if m.role == LLMRole.SYSTEM:
                if m.content:
                    system_instructions.append(m.content)
            elif m.role == LLMRole.ASSISTANT:
                parts: List[Dict[str, Any]] = []
                if m.content:
                    parts.append({"text": m.content})
                if m.tool_calls:
                    for tc in m.tool_calls:
                        fc_dict = {
                            "name": tc.name,
                            "args": tc.arguments
                        }
                        if tc.id and not tc.id.startswith("call_gemini_"):
                            fc_dict["id"] = tc.id
                        part_dict: Dict[str, Any] = {"functionCall": fc_dict}
                        if getattr(tc, "thought_signature", None):
                            part_dict["thoughtSignature"] = tc.thought_signature
                        parts.append(part_dict)
                contents.append({"role": "model", "parts": parts or [{"text": ""}]})
            elif m.role == LLMRole.TOOL:
                # Return tool output to Gemini as functionResponse
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": m.name or "tool_result",
                            "response": {"output": m.content}
                        }
                    }]
                })
            else:
                contents.append({
                    "role": "user",
                    "parts": [{"text": m.content or ""}]
                })

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        if system_instructions:
            body["system_instruction"] = {
                "parts": [{"text": "\n\n".join(system_instructions)}]
            }

        if tools:
            declarations = []
            for t in tools:
                fn = t.function
                declarations.append({
                    "name": fn.name,
                    "description": fn.description,
                    "parameters": fn.parameters
                })
            body["tools"] = [{"function_declarations": declarations}]

        return body

    def _parse_gemini_response(self, data: Dict[str, Any], latency: float) -> LLMResponse:
        """Parse Gemini candidates payload into normalized LLMResponse."""
        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMProviderError("Gemini returned empty candidates list.", provider=self.provider_name)

        first_cand = candidates[0]
        content_obj = first_cand.get("content", {})
        parts = content_obj.get("parts", [])

        text_pieces: List[str] = []
        tool_calls: List[LLMToolCall] = []

        for part in parts:
            if "text" in part:
                text_pieces.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                ts = part.get("thoughtSignature") or part.get("thought_signature")
                tool_calls.append(
                    LLMToolCall(
                        id=fc.get("id") or f"call_gemini_{uuid.uuid4().hex[:8]}",
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                        thought_signature=ts
                    )
                )

        combined_text = "".join(text_pieces).strip() if text_pieces else None
        usage_metadata = data.get("usageMetadata", {})

        p_tokens = usage_metadata.get("promptTokenCount", 0)
        c_tokens = usage_metadata.get("candidatesTokenCount", 0)
        tot_tokens = usage_metadata.get("totalTokenCount", p_tokens + c_tokens)

        # Estimate cost in INR (Flash ~₹0.06 per 1K tokens)
        cost_inr = round(((p_tokens * 0.075 + c_tokens * 0.30) / 1_000_000) * 87.0, 4)

        return LLMResponse(
            content=combined_text,
            tool_calls=tool_calls,
            provider=self.provider_name,
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=tot_tokens,
                estimated_cost_inr=cost_inr
            ),
            latency_seconds=latency,
            finish_reason=first_cand.get("finishReason", "stop"),
            raw_response=data
        )

