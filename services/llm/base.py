"""Abstract Base Class for LLM Providers.

Contract: llm-provider/v1
Guarantees clean separation of concern, uniform typing, and vendor independence.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import structlog

from domain.llm_schemas import (
    LLMMessage,
    LLMToolDefinition,
    LLMResponse,
    LLMProviderError
)

logger = structlog.get_logger()


class LLMProvider(ABC):
    """Abstract interface that all LLM providers must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Normalized provider identifier (e.g. 'openrouter', 'gemini', 'gnani_evon')."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether valid credentials and endpoints are configured."""
        pass

    @property
    @abstractmethod
    def active_model(self) -> str:
        """Active model identifier."""
        pass

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float = 15.0
    ) -> LLMResponse:
        """Generate conversational completion without external tool access."""
        pass

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        tool_choice: str = "auto",
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float = 15.0
    ) -> LLMResponse:
        """Generate completion with structured tool declarations and function calling."""
        pass

