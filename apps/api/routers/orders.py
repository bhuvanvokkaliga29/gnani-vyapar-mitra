"""API Endpoints for Managing and Reconciling Orders."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from domain.models import Order, Payment
from services.order_service import OrderService
from services.razorpay.reconciliation import ReconciliationService
from services.razorpay.errors import RazorpayError

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


class PaymentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount_paise: int
    currency: str
    status: str
    method: Optional[str] = None
    captured_at: Optional[datetime] = None


class OrderCreateRequest(BaseModel):
    amount_paise: int = Field(gt=0, description="Order amount in integer minor units (paise)")
    currency: str = Field(default="INR", description="3-letter ISO currency code")
    notes: Optional[Dict[str, Any]] = Field(default=None, description="Metadata dictionary")
    decision_id: Optional[str] = Field(default=None, description="Internal decision or intent reference ID")


class OrderResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    decision_id: str
    razorpay_order_id: Optional[str] = None
    amount_paise: int
    currency: str
    receipt: str
    status: str
    created_at: datetime
    notes: Optional[Dict[str, Any]] = None
    payments: List[PaymentResponseSchema] = Field(default_factory=list)


def get_order_service() -> OrderService:
    return OrderService()


def get_reconciler() -> ReconciliationService:
    return ReconciliationService()


@router.post("", response_model=OrderResponseSchema, status_code=status.HTTP_200_OK)
async def create_order(
    request: OrderCreateRequest,
    db: AsyncSession = Depends(get_db),
    order_svc: OrderService = Depends(get_order_service)
):
    """Create a new order in Razorpay Test Mode with timeout protection and pre-allocation."""
    try:
        order = await order_svc.create_order(
            db=db,
            amount_paise=request.amount_paise,
            currency=request.currency,
            notes=request.notes,
            decision_id=request.decision_id
        )
        return order
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RazorpayError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Razorpay provider error: {exc.message}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order creation failed: {str(exc)}"
        )


@router.get("", response_model=List[OrderResponseSchema], status_code=status.HTTP_200_OK)
async def list_orders(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    order_svc: OrderService = Depends(get_order_service)
):
    """List recent orders with status and payment attempts."""
    return await order_svc.list_orders(db, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderResponseSchema, status_code=status.HTTP_200_OK)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    order_svc: OrderService = Depends(get_order_service)
):
    """Retrieve internal order status and payment attempts."""
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order '{order_id}' not found.")
    return order


@router.post("/{order_id}/reconcile", response_model=OrderResponseSchema, status_code=status.HTTP_200_OK)
async def reconcile_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    reconciler: ReconciliationService = Depends(get_reconciler)
):
    """Manually or diagnostically trigger state reconciliation against Razorpay."""
    try:
        order = await reconciler.reconcile_order(order_id, db)
        return order
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation error: {str(exc)}"
        )
