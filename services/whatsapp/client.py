"""Official Meta WhatsApp Cloud API Outbound Messaging Client.

Handles:
- Outbound text message delivery to Meta Graph API
- Contextual replies (reply-to-message)
- Rate limit, network error, and timeout handling
- Realistic mock mode fallback when Meta credentials are not configured
"""

import uuid
import httpx
import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger()


class WhatsAppClient:
    """Production-grade Meta WhatsApp Cloud API client."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: str = "v21.0",
        timeout: float = 8.0
    ):
        self.access_token = (access_token or "").strip()
        self.phone_number_id = (phone_number_id or "").strip()
        self.api_version = api_version
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Return True only if real, non-placeholder credentials are provided."""
        return (
            bool(self.access_token)
            and bool(self.phone_number_id)
            and not self.access_token.startswith("your_")
            and not self.access_token.startswith("placeholder_")
            and not self.phone_number_id.startswith("your_")
        )

    def get_api_url(self) -> str:
        """Return Meta Cloud API messages endpoint."""
        return f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    async def send_text_message(
        self,
        to_phone: str,
        text: str = "",
        reply_to_message_id: Optional[str] = None,
        message_text: Optional[str] = None,
        reply_to_wamid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a WhatsApp text message via Meta Cloud API or mock fallback."""
        body_text = message_text if message_text is not None else text
        reply_id = reply_to_wamid if reply_to_wamid is not None else reply_to_message_id
        clean_phone = to_phone.replace("+", "").replace(" ", "").replace("-", "")

        # 1. Mock Mode (when credentials not yet supplied)
        if not self.is_configured:
            mock_id = f"mock_wamid_{uuid.uuid4().hex[:16]}"
            logger.info(
                "whatsapp_mock_outbound_dispatched",
                to_phone=clean_phone,
                message_length=len(body_text),
                message_snippet=body_text[:120],
                mock_message_id=mock_id
            )
            return {
                "messaging_product": "whatsapp",
                "contacts": [{"input": clean_phone, "wa_id": clean_phone}],
                "messages": [{"id": mock_id}],
                "status": "mock_sent",
                "is_mock": True
            }

        # 2. Live Meta Cloud API Dispatch
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body_text
            }
        }
        if reply_id and not reply_id.startswith("mock_"):
            payload["context"] = {"message_id": reply_id}

        url = self.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response_data = response.json()

                if response.status_code == 200:
                    logger.info(
                        "whatsapp_message_dispatched_success",
                        to_phone=clean_phone,
                        status_code=response.status_code,
                        response_data=response_data
                    )
                    return response_data
                else:
                    logger.error(
                        "whatsapp_message_dispatch_meta_error",
                        status_code=response.status_code,
                        to_phone=clean_phone,
                        response=response.text
                    )
                    return {
                        "error": response_data.get("error", {}),
                        "status_code": response.status_code,
                        "status": "failed",
                        "is_mock": False
                    }
        except httpx.RequestError as exc:
            logger.error("whatsapp_dispatch_network_exception", error=str(exc), to_phone=clean_phone)
            return {
                "error": {"message": f"Network exception communicating with Meta API: {str(exc)}"},
                "status": "network_error",
                "is_mock": False
            }
