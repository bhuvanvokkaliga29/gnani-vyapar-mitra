"""FastAPI Router for Demo State Management & Reset."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from apps.api.core.database import get_db
from domain.growth_models import (
    GrowthDoctorFinding,
    OwnerApprovalItem,
    GrowthCampaign,
    CommunityGroupDeal
)
from services.marketplace.service import MarketplaceGrowthService
from services.growth_doctor.service import GrowthDoctorService
from services.campaigns.service import CampaignService

router = APIRouter(prefix="/api/v1/demo", tags=["Demo State Control"])


class ResetDemoRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"


@router.post("/reset")
async def reset_demo_data(
    req: ResetDemoRequest,
    db: AsyncSession = Depends(get_db)
):
    """Safely reset and re-seed demo growth findings, campaigns, and approvals."""
    try:
        # 1. Clear ephemeral growth tables for this merchant
        await db.execute(delete(GrowthDoctorFinding).where(GrowthDoctorFinding.merchant_id == req.merchant_id))
        await db.execute(delete(OwnerApprovalItem).where(OwnerApprovalItem.merchant_id == req.merchant_id))
        await db.execute(delete(GrowthCampaign).where(GrowthCampaign.merchant_id == req.merchant_id))
        await db.execute(delete(CommunityGroupDeal).where(CommunityGroupDeal.merchant_id == req.merchant_id))
        await db.commit()

        # 2. Re-initialize defaults
        await MarketplaceGrowthService.ensure_default_channels(db, req.merchant_id)
        await GrowthDoctorService.analyze_merchant(db, req.merchant_id)
        await CampaignService.ensure_sample_contacts(db, req.merchant_id)

        return {
            "status": "RESET_SUCCESSFUL",
            "merchant_id": req.merchant_id,
            "message": "Demo data refreshed to clean benchmark state."
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")
