"""Typed Application Configuration using Pydantic Settings."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
_env_file = str(ROOT_ENV_PATH) if ROOT_ENV_PATH.exists() else ".env"


class Settings(BaseSettings):
    """Application settings with environment variable fallbacks."""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = Field(default="development", description="Application runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./test.db",
        description="Async database connection string"
    )

    RAZORPAY_KEY_ID: str = Field(
        default="rzp_test_placeholder_key_id",
        description="Razorpay API Key ID"
    )
    RAZORPAY_KEY_SECRET: str = Field(
        default="placeholder_key_secret",
        description="Razorpay API Key Secret"
    )
    RAZORPAY_WEBHOOK_SECRET: str = Field(
        default="placeholder_webhook_secret",
        description="Razorpay Webhook Shared Secret"
    )

    # Gnani AI Configuration (Prisma STT, Timbre TTS & Agent Builder)
    GNANI_API_KEY: str = Field(default="", description="Legacy alias for GNANI_SPEECH_API_KEY")
    GNANI_SPEECH_API_KEY: str = Field(default="", description="Gnani Speech API Key for Prisma STT & Timbre TTS (vach_...)")
    GNANI_PLATFORM_API_KEY: str = Field(default="", description="Gnani Agent Builder Platform API Key for api.inya.ai")
    GNANI_BASE_URL: str = Field(default="https://api.vachana.ai", description="Legacy alias for GNANI_SPEECH_BASE_URL")
    GNANI_SPEECH_BASE_URL: str = Field(default="https://api.vachana.ai", description="Gnani Speech API Base URL")
    GNANI_PLATFORM_BASE_URL: str = Field(default="https://api.inya.ai/platform", description="Gnani Agent Builder Platform API Base URL")
    GNANI_AGENT_ID: str = Field(default="7bd15e5ff5a7411db02665f468d3353a", description="Gnani Agent Builder Bot ID")
    GNANI_WEBHOOK_SECRET: str = Field(default="vyapar_mitra_gnani_secret_2026", description="Shared secret for authenticating inbound Gnani webhooks and actions")
    GNANI_STT_MODEL: str = Field(default="prisma-v3.0", description="Prisma STT Model")
    GNANI_TTS_MODEL: str = Field(default="timbre-v3.0", description="Timbre TTS Model")
    GNANI_STT_DEFAULT_LANG: str = Field(default="indic-auto", description="Default STT Language Code")
    GNANI_TTS_DEFAULT_LANG: str = Field(default="kn", description="Default TTS Language Code")
    GNANI_TTS_DEFAULT_VOICE: str = Field(default="Lakshmi", description="Default Timbre Voice")
    GNANI_USE_LOCAL_MOCK: bool = Field(default=False, description="Whether to bypass live Gnani API for testing")

    @property
    def effective_gnani_speech_key(self) -> str:
        """Resolve speech key with fallback to legacy GNANI_API_KEY."""
        return (self.GNANI_SPEECH_API_KEY or self.GNANI_API_KEY or "").strip()

    @property
    def effective_gnani_platform_key(self) -> str:
        """Resolve platform key strictly. Never fall back to speech key (avoids HTTP 401)."""
        return (self.GNANI_PLATFORM_API_KEY or "").strip()

    # LLM Provider Configuration (gemini | openrouter | gnani_evon)
    LLM_PROVIDER: str = Field(default="gemini", description="Active LLM Provider: gemini, openrouter, gnani_evon")

    # OpenRouter AI Configuration (Gemma 4 Free Candidates)
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API Key")
    OPENROUTER_MODEL: str = Field(default="google/gemma-4-31b-it:free", description="OpenRouter Primary Model")
    OPENROUTER_FALLBACK_MODELS: List[str] = Field(
        default=["google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"],
        description="OpenRouter Fallback Candidates"
    )

    # Google Gemini AI Configuration
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-flash-lite-latest", description="Gemini Model Identifier (e.g. gemini-flash-lite-latest, gemini-2.5-flash)")
    LLM_API_KEY: str = Field(default="", description="Legacy alias for GEMINI_API_KEY")
    LLM_MODEL: str = Field(default="gemini-flash-lite-latest", description="Legacy alias for GEMINI_MODEL")

    # Gnani Evon AI Configuration (Indic Foundation MoE)
    EVON_API_KEY: str = Field(default="", description="Gnani Evon API Key (or falls back to GNANI_API_KEY)")
    EVON_BASE_URL: str = Field(default="https://api.vachana.ai", description="Evon API Endpoint or vLLM Base URL")
    EVON_MODEL: str = Field(default="gnani/gnani-evon-v3.3-30B-A3B", description="Evon Model Identifier")

    # WhatsApp Business Platform / Cloud API Configuration
    WHATSAPP_ACCESS_TOKEN: str = Field(
        default="",
        description="Meta WhatsApp Cloud API Access Token"
    )
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        default="",
        description="Meta Sender Phone Number ID"
    )
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = Field(
        default="",
        description="Meta WhatsApp Business Account ID"
    )
    WHATSAPP_VERIFY_TOKEN: str = Field(
        default="vastram_growth_agent_verify_2026",
        description="Meta Webhook Verification Challenge Token"
    )
    WHATSAPP_APP_SECRET: str = Field(
        default="",
        description="Meta App Secret for X-Hub-Signature-256 HMAC validation"
    )
    WHATSAPP_TEST_MERCHANT_PHONE: str = Field(
        default="+919113960498",
        description="Configured test recipient phone number"
    )
    WHATSAPP_DEFAULT_MERCHANT_ID: str = Field(
        default="merch_atlas_travel",
        description="Default merchant tenant associated with test phone"
    )
    WHATSAPP_API_VERSION: str = Field(
        default="v21.0",
        description="Meta Graph API version"
    )

    # Twilio WhatsApp Sandbox Alternative Configuration
    TWILIO_ACCOUNT_SID: str = Field(
        default="",
        description="Twilio Account SID"
    )
    TWILIO_AUTH_TOKEN: str = Field(
        default="",
        description="Twilio Auth Token for webhook signature validation"
    )
    TWILIO_WHATSAPP_NUMBER: str = Field(
        default="whatsapp:+14155238886",
        description="Twilio Sandbox WhatsApp Number"
    )

    @field_validator("RAZORPAY_KEY_ID")
    @classmethod
    def validate_test_key_prefix(cls, v: str, info) -> str:
        """Ensure test credentials are used in non-production environments."""
        if v and not v.startswith("rzp_test_") and not v.startswith("test_"):
            # Allow mock prefixes for local tests, but warn/prevent live keys
            if "live" in v.lower():
                raise ValueError("Live Razorpay keys are prohibited in Test Mode environments.")
        return v

    def sanitized_dict(self) -> dict:
        """Return configuration dictionary with masked secrets for safe logging."""
        data = self.model_dump()
        for secret_key in (
            "RAZORPAY_KEY_SECRET",
            "RAZORPAY_WEBHOOK_SECRET",
            "WHATSAPP_ACCESS_TOKEN",
            "WHATSAPP_APP_SECRET",
            "TWILIO_AUTH_TOKEN",
            "GNANI_API_KEY",
            "GNANI_SPEECH_API_KEY",
            "GNANI_PLATFORM_API_KEY",
            "GNANI_WEBHOOK_SECRET",
            "GEMINI_API_KEY",
            "LLM_API_KEY",
            "OPENROUTER_API_KEY",
            "EVON_API_KEY"
        ):
            if secret_key in data and data[secret_key]:
                data[secret_key] = "******"
        return data


# Global singleton instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency helper returning global application settings."""
    return settings
