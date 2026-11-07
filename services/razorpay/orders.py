"""Orders API Operations for Razorpay Adapter."""

from typing import Optional, Dict, Any, List
from services.razorpay.client import RazorpayClient
from services.razorpay.models import (
    RazorpayOrderCreateRequest,
    RazorpayOrderResponse,
    RazorpayPaymentCollection
)


class RazorpayOrderService:
    """Encapsulates all Razorpay Orders API interactions."""

    def __init__(self, client: Optional[RazorpayClient] = None):
        self.client = client or RazorpayClient()

    async def create_order(
        self,
        amount_paise: int,
        receipt: str,
        currency: str = "INR",
        notes: Optional[Dict[str, Any]] = None,
        payment_capture: int = 1
    ) -> RazorpayOrderResponse:
        """Create a new order in Razorpay Test Mode."""
        # Validate request via Pydantic model
        request_model = RazorpayOrderCreateRequest(
            amount=amount_paise,
            currency=currency,
            receipt=receipt,
            notes=notes,
            payment_capture=payment_capture
        )

        data = await self.client.request(
            method="POST",
            path="orders",
            json_data=request_model.model_dump(exclude_none=True)
        )
        return RazorpayOrderResponse.model_validate(data)

    async def get_order(self, order_id: str) -> RazorpayOrderResponse:
        """Retrieve existing order state from Razorpay."""
        data = await self.client.request(
            method="GET",
            path=f"orders/{order_id}"
        )
        return RazorpayOrderResponse.model_validate(data)

    async def get_order_payments(self, order_id: str) -> RazorpayPaymentCollection:
        """Retrieve all payment attempts and captures associated with an order."""
        data = await self.client.request(
            method="GET",
            path=f"orders/{order_id}/payments"
        )
        return RazorpayPaymentCollection.model_validate(data)

    async def find_order_by_receipt(self, receipt: str) -> Optional[RazorpayOrderResponse]:
        """Search recent orders to reconcile an uncertain state by receipt ID."""
        try:
            # Query recent orders collection (up to 50 items)
            data = await self.client.request(
                method="GET",
                path="orders",
                params={"count": 50}
            )
            items = data.get("items", [])
            for item in items:
                if item.get("receipt") == receipt:
                    return RazorpayOrderResponse.model_validate(item)
            return None
        except Exception:
            return None
