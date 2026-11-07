"""LLM Provider Factory & Resilience Fallback Router for Vyapar Mitra.

Allows zero-downtime provider switching via environment configuration:
LLM_PROVIDER=openrouter | gemini | gnani_evon

Features:
- Configurable provider resolution
- Graceful multi-tier fallback orchestration (e.g. OpenRouter Free -> Gemini Flash)
- Structured execution telemetry and failure provenance
"""

from typing import Optional, List, Dict, Any
import structlog

from domain.llm_schemas import (
    LLMMessage,
    LLMToolDefinition,
    LLMResponse,
    LLMProviderError,
    LLMAuthenticationError,
    LLMScopeNotAllowedError,
    LLMQuotaExceededError,
    LLMModelUnavailableError
)
from services.llm.base import LLMProvider
from services.llm.openrouter_provider import OpenRouterProvider
from services.llm.gemini_provider import GeminiProvider
from services.llm.evon_provider import GnaniEvonProvider

logger = structlog.get_logger()


class LLMFallbackRouter(LLMProvider):
    """Composite provider executing with primary-to-secondary fallback resilience."""

    def __init__(self, primary: LLMProvider, secondary: Optional[LLMProvider] = None):
        self.primary = primary
        self.secondary = secondary

    @property
    def provider_name(self) -> str:
        return f"{self.primary.provider_name}_with_fallback"

    @property
    def is_configured(self) -> bool:
        return self.primary.is_configured or (self.secondary is not None and self.secondary.is_configured)

    @property
    def active_model(self) -> str:
        return self.primary.active_model

    async def chat_complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float = 15.0
    ) -> LLMResponse:
        return await self._dispatch_with_fallback(
            lambda p: p.chat_complete(messages, temperature, max_tokens, timeout)
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
        return await self._dispatch_with_fallback(
            lambda p: p.chat_with_tools(messages, tools, tool_choice, temperature, max_tokens, timeout)
        )

    async def _dispatch_with_fallback(self, method_callable) -> LLMResponse:
        """Attempt primary provider; fall back to secondary on quota or scope issues."""
        try:
            if self.primary.is_configured:
                return await method_callable(self.primary)
            else:
                logger.info(
                    "primary_llm_unconfigured_attempting_secondary",
                    primary=self.primary.provider_name
                )
        except (LLMQuotaExceededError, LLMScopeNotAllowedError, LLMModelUnavailableError, LLMAuthenticationError) as exc:
            logger.warning(
                "primary_llm_failed_falling_back",
                primary=self.primary.provider_name,
                error=str(exc)
            )
            if not self.secondary or not self.secondary.is_configured:
                raise

        if self.secondary and self.secondary.is_configured:
            logger.info("dispatching_to_secondary_llm", secondary=self.secondary.provider_name)
            res = await method_callable(self.secondary)
            # Annotate finish reason to record provenance
            res.finish_reason = f"{res.finish_reason} (fallback_from_{self.primary.provider_name})"
            return res

        raise LLMProviderError(
            f"Primary LLM '{self.primary.provider_name}' failed and no secondary fallback is configured.",
            provider=self.primary.provider_name
        )


class LLMProviderFactory:
    """Factory creating configured LLM provider instances."""

    @classmethod
    def get_provider(
        cls,
        provider_name: Optional[str] = None,
        enable_fallback: bool = True
    ) -> LLMProvider:
        """Resolve and instantiate the active LLM provider.
        
        Args:
            provider_name: 'openrouter', 'gemini', 'gnani_evon', or None (uses config).
            enable_fallback: Whether to wrap with fallback router to secondary provider.
        """
        from apps.api.core.config import settings
        target = (provider_name or getattr(settings, "LLM_PROVIDER", "openrouter")).lower().strip()

        if target in ("openrouter", "open_router"):
            primary = OpenRouterProvider()
            if enable_fallback:
                # Fallback to Gemini if Gemini is configured
                secondary = GeminiProvider() if getattr(settings, "GEMINI_API_KEY", "") else None
                return LLMFallbackRouter(primary, secondary)
            return primary

        elif target in ("gemini", "google_gemini", "google"):
            primary = GeminiProvider()
            if enable_fallback:
                secondary = OpenRouterProvider() if getattr(settings, "OPENROUTER_API_KEY", "") else None
                return LLMFallbackRouter(primary, secondary)
            return primary

        elif target in ("gnani_evon", "evon"):
            primary = GnaniEvonProvider()
            if enable_fallback:
                # If Evon key lacks scope, fallback to OpenRouter or Gemini
                secondary = (
                    OpenRouterProvider()
                    if getattr(settings, "OPENROUTER_API_KEY", "")
                    else (GeminiProvider() if getattr(settings, "GEMINI_API_KEY", "") else None)
                )
                return LLMFallbackRouter(primary, secondary)
            return primary

        else:
            logger.warning("unrecognized_llm_provider_defaulting_openrouter", provider=target)
            return OpenRouterProvider()

