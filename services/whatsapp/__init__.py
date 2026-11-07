"""WhatsApp Business Platform Integration Module for Merchant Growth Agent."""

from services.whatsapp.service import WhatsAppService
from services.whatsapp.client import WhatsAppClient
from services.whatsapp.intent import WhatsAppIntentParser, WhatsAppIntent, IntentType
from services.whatsapp.policy_guard import PolicyGuard, PolicyValidationResult
from services.whatsapp.confirmation import ConfirmationManager
from services.whatsapp.security import normalize_phone_number, verify_webhook_signature

__all__ = [
    "WhatsAppService",
    "WhatsAppClient",
    "WhatsAppIntentParser",
    "WhatsAppIntent",
    "IntentType",
    "PolicyGuard",
    "PolicyValidationResult",
    "ConfirmationManager",
    "normalize_phone_number",
    "verify_webhook_signature",
]
