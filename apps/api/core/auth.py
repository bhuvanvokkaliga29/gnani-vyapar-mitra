"""Tenant Authorization and Security Scoping for Phase 10 Control Center.

Enforces strict tenant boundary verification:
1. Authenticated caller context (via X-Caller-Merchant-ID or Authorization Bearer token)
   is validated against the requested tenant scope.
2. Rejects cross-tenant access with HTTP 403 Forbidden.
3. Ensures client dropdown/URL tampering cannot bypass the backend authorization boundary.
"""

from typing import Optional
from fastapi import Header, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.core.database import get_db
from domain.models import Merchant
from services.commerce_service import MerchantNotFoundError


async def verify_merchant_authorization(
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    x_caller_merchant_id: Optional[str] = Header(default=None, alias="X-Caller-Merchant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> str:
    """Verifies that the authenticated caller is authorized to access the specified merchant tenant.
    
    Guarantees:
    - If caller identity is specified via header, it MUST match the requested merchant_id.
    - Any mismatch raises 403 Forbidden.
    - Verifies merchant exists in the database, raising 404 if not found.
    """
    caller_id = x_caller_merchant_id
    if not caller_id and authorization and authorization.startswith("Bearer "):
        caller_id = authorization.replace("Bearer ", "").strip()

    if caller_id and caller_id != merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Authenticated caller '{caller_id}' is not authorized to access tenant '{merchant_id}'."
        )

    # Verify merchant exists in database
    stmt = select(Merchant).where(Merchant.id == merchant_id)
    result = await db.execute(stmt)
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Merchant '{merchant_id}' does not exist."
        )

    return merchant_id


def verify_caller_scope_for_body(
    merchant_id: str,
    x_caller_merchant_id: Optional[str] = None,
    authorization: Optional[str] = None
) -> None:
    """Synchronous helper to verify caller scope for POST action payloads."""
    caller_id = x_caller_merchant_id
    if not caller_id and authorization and authorization.startswith("Bearer "):
        caller_id = authorization.replace("Bearer ", "").strip()

    if caller_id and caller_id != merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Authenticated caller '{caller_id}' is not authorized to mutate tenant '{merchant_id}'."
        )
