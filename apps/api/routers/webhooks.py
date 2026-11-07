"""Inbound Webhook Receiver for Razorpay Events."""

from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.core.database import get_db
from services.webhook_service import WebhookService
from services.razorpay.errors import RazorpaySignatureVerificationError

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def get_webhook_service() -> WebhookService:
    return WebhookService()


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def handle_razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    webhook_svc: WebhookService = Depends(get_webhook_service)
):
    """Receive raw webhook bytes, verify HMAC SHA-256 signature, deduplicate, and persist outcome."""
    # 1. Mandatory Raw Body Consumption (Never use parsed request.json())
    raw_body = await request.body()

    # 2. Extract verification headers
    signature = request.headers.get("X-Razorpay-Signature") or request.headers.get("x-razorpay-signature")
    event_id = request.headers.get("X-Razorpay-Event-Id") or request.headers.get("x-razorpay-event-id")

    try:
        result = await webhook_svc.process_webhook(
            raw_body=raw_body,
            signature=signature,
            event_id=event_id,
            db=db
        )
        return result
    except RazorpaySignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay webhook signature."
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing error: {str(exc)}"
        )
