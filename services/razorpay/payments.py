"""Payments API Operations for Razorpay Adapter."""

from typing import Optional, Dict, Any
from services.razorpay.client import RazorpayClient
from services.razorpay.models import RazorpayPaymentItem


class RazorpayPaymentService:
    """Encapsulates all Razorpay Payments API interactions."""

    def __init__(self, client: Optional[RazorpayClient] = None):
        self.client = client or RazorpayClient()

    async def get_payment(self, payment_id: str) -> RazorpayPaymentItem:
        """Fetch details for a specific payment ID from Razorpay."""
        data = await self.client.request(
            method="GET",
            path=f"payments/{payment_id}"
        )
        return RazorpayPaymentItem.model_validate(data)

    async def capture_payment(
        self,
        payment_id: str,
        amount_paise: int,
        currency: str = "INR"
    ) -> RazorpayPaymentItem:
        """Capture an authorized payment."""
        data = await self.client.request(
            method="POST",
            path=f"payments/{payment_id}/capture",
            json_data={
                "amount": amount_paise,
                "currency": currency
            }
        )
        return RazorpayPaymentItem.model_validate(data)
