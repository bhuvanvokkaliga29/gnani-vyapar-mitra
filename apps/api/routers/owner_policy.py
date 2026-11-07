"""FastAPI Router for Owner Policy Formulation, Confirmation & Approvals."""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.owner_policy.service import OwnerPolicyService

router = APIRouter(prefix="/api/v1/owner", tags=["Owner Policy & Approvals"])


class ParsePolicyRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    text: str


class ConfirmPolicyRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    proposal_id: str


class ResolveApprovalRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    decision: str  # APPROVED, REJECTED


@router.post("/policy/parse")
async def parse_owner_policy(
    req: ParsePolicyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Parse natural language commercial policy into structured proposal awaiting confirmation."""
    try:
        proposal = await OwnerPolicyService.create_policy_proposal(
            db=db,
            merchant_id=req.merchant_id,
            input_text=req.text
        )
        return {
            "proposal_id": proposal.id,
            "merchant_id": proposal.merchant_id,
            "raw_text": proposal.raw_input_text,
            "parsed_policy": proposal.parsed_policy_json,
            "status": proposal.status,
            "created_at": proposal.created_at.isoformat() if proposal.created_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/policy/confirm")
async def confirm_owner_policy(
    req: ConfirmPolicyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Explicitly confirm and activate an owner policy proposal."""
    try:
        merchant = await OwnerPolicyService.confirm_policy_proposal(
            db=db,
            proposal_id=req.proposal_id,
            merchant_id=req.merchant_id
        )
        return {
            "status": "CONFIRMED_AND_ACTIVE",
            "merchant_id": merchant.id,
            "minimum_margin_percent": float(merchant.minimum_margin_percent),
            "maximum_discount_percent": float(merchant.maximum_discount_percent)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals")
async def get_pending_approvals(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """List all pending owner approval items."""
    approvals = await OwnerPolicyService.list_pending_approvals(db, merchant_id)
    return {
        "merchant_id": merchant_id,
        "count": len(approvals),
        "approvals": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "title": a.title,
                "description": a.description,
                "payload": a.payload_json,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in approvals
        ]
    }


@router.post("/approvals/{approval_id}/resolve")
async def resolve_approval(
    approval_id: str,
    req: ResolveApprovalRequest,
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a pending commercial action."""
    try:
        resolved = await OwnerPolicyService.resolve_approval(
            db=db,
            approval_id=approval_id,
            merchant_id=req.merchant_id,
            decision=req.decision.upper()
        )
        return {
            "approval_id": resolved.id,
            "status": resolved.status,
            "resolved_at": resolved.resolved_at.isoformat() if resolved.resolved_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
