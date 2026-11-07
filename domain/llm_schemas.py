"""Provider-Agnostic LLM Request and Response Schemas for Vyapar Mitra.

Contract: llm-agent/v1
Adheres to strict typing, structured tool definitions, and token/cost accounting.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class LLMRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMToolCall(BaseModel):
    """Normalized tool call issued by an LLM."""
    id: str = Field(..., description="Unique tool call invocation identifier")
    name: str = Field(..., description="Name of the tool/function to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Parsed tool input arguments")
    thought_signature: Optional[str] = Field(default=None, description="Thought signature returned by reasoning models like Gemini")


class LLMMessage(BaseModel):
    """Unified conversational message schema across all providers."""
    role: LLMRole = Field(..., description="Message author role")
    content: Optional[str] = Field(default=None, description="Textual message content")
    name: Optional[str] = Field(default=None, description="Optional name for tool results or specific speakers")
    tool_calls: Optional[List[LLMToolCall]] = Field(default=None, description="List of tool calls issued by assistant")
    tool_call_id: Optional[str] = Field(default=None, description="Correlation ID matching the tool invocation")


class LLMFunctionDeclaration(BaseModel):
    """Specification of an invokable business function/tool."""
    name: str = Field(..., description="Function name (e.g. get_daily_sales)")
    description: str = Field(..., description="Purpose of function for LLM reasoning")
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema dictionary defining argument types and constraints"
    )


class LLMToolDefinition(BaseModel):
    """Wrapper matching standard function tool specifications."""
    type: str = Field(default="function", description="Tool type; strictly 'function'")
    function: LLMFunctionDeclaration = Field(..., description="Function declaration details")


class LLMUsage(BaseModel):
    """Token consumption and estimated compute expenditure."""
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    estimated_cost_inr: float = Field(default=0.0, description="Estimated cost in Indian Rupees")


class LLMResponse(BaseModel):
    """Normalized completion response returned by any LLM provider."""
    content: Optional[str] = Field(default=None, description="Primary textual response")
    tool_calls: List[LLMToolCall] = Field(default_factory=list, description="Tool calls requested by model")
    provider: str = Field(..., description="Provider identifier (openrouter, gemini, gnani_evon)")
    model: str = Field(..., description="Exact model version string that processed the query")
    usage: LLMUsage = Field(default_factory=LLMUsage)
    latency_seconds: float = Field(default=0.0, description="Round-trip latency in seconds")
    finish_reason: str = Field(default="stop", description="Finish reason: stop, tool_calls, length, error")
    raw_response: Optional[Dict[str, Any]] = Field(default=None, exclude=True, description="Raw provider payload for debugging")


# =============================================================================
# Custom Provider Exception Hierarchy
# =============================================================================

class LLMProviderError(Exception):
    """Base exception for all LLM provider failures."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(f"[{provider.upper()}] {message}")
        self.message = message
        self.provider = provider
        self.status_code = status_code


class LLMAuthenticationError(LLMProviderError):
    """Invalid, revoked, or unconfigured API credentials."""
    pass


class LLMScopeNotAllowedError(LLMProviderError):
    """API key exists but lacks permission/scope for LLM inference (e.g. Gnani Evon)."""
    pass


class LLMQuotaExceededError(LLMProviderError):
    """Rate limit reached (HTTP 429) or token balance exhausted."""
    pass


class LLMModelUnavailableError(LLMProviderError):
    """Requested model not found (HTTP 404) or endpoint currently out of capacity (HTTP 503)."""
    pass

