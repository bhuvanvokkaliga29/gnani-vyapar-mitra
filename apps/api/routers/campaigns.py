"""FastAPI Router for Campaigns & Community Group Deals."""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.core.database import get_db
from domain.growth_models import CustomerContact, GrowthCampaign, CommunityGroupDeal
from services.campaigns.service import CampaignService

router = APIRouter(prefix="/api/v1/campaigns", tags=["Campaigns & Community Deals"])


class CreateCampaignRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    name: str
    discount_percent: float
    target_segment: Optional[str] = "INACTIVE_60_DAYS"


class OptOutRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    phone: str


class CreateGroupDealRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    target_group_name: str
    product_id: str
    min_threshold_units: int
    discounted_price_paise: int


class PledgeGroupDealRequest(BaseModel):
    units: Optional[int] = 1


@router.get("/contacts")
async def get_customer_contacts(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve customer contacts with clear consent flags."""
    contacts = await CampaignService.ensure_sample_contacts(db, merchant_id)
    return {
        "merchant_id": merchant_id,
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "is_opted_in": c.is_opted_in,
                "total_orders_count": c.total_orders_count,
                "total_spend_paise": c.total_spend_paise,
                "preferred_category": c.preferred_category,
                "last_order_at": c.last_order_at.isoformat() if c.last_order_at else None,
                "opt_out_at": c.opt_out_at.isoformat() if c.opt_out_at else None
            }
            for c in contacts
        ]
    }


@router.post("/opt-out")
async def opt_out_contact(
    req: OptOutRequest,
    db: AsyncSession = Depends(get_db)
):
    """Handle STOP / unsubscribe and persist immediate opt-out."""
    try:
        contact = await CampaignService.handle_customer_opt_out(
            db=db,
            merchant_id=req.merchant_id,
            phone=req.phone
        )
        return {
            "status": "OPTED_OUT",
            "phone": contact.phone,
            "is_opted_in": contact.is_opted_in,
            "opt_out_at": contact.opt_out_at.isoformat() if contact.opt_out_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("")
async def get_campaigns(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """List marketing and win-back campaigns."""
    result = await db.execute(
        select(GrowthCampaign).where(GrowthCampaign.merchant_id == merchant_id)
    )
    campaigns = result.scalars().all()
    return {
        "merchant_id": merchant_id,
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "campaign_type": c.campaign_type,
                "target_segment": c.target_segment,
                "message_template": c.message_template,
                "offered_discount_percent": float(c.offered_discount_percent),
                "recipient_count": c.recipient_count,
                "status": c.status,
                "is_simulated": c.is_simulated,
                "simulated_opens": c.simulated_opens,
                "simulated_conversions": c.simulated_conversions,
                "simulated_revenue_paise": c.simulated_revenue_paise,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "dispatched_at": c.dispatched_at.isoformat() if c.dispatched_at else None
            }
            for c in campaigns
        ]
    }


@router.post("/create")
async def create_campaign(
    req: CreateCampaignRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new win-back campaign subject to policy discount bounds."""
    try:
        campaign = await CampaignService.create_winback_campaign(
            db=db,
            merchant_id=req.merchant_id,
            name=req.name,
            discount_percent=Decimal(str(req.discount_percent)),
            target_segment=req.target_segment or "INACTIVE_60_DAYS"
        )
        return {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "recipient_count": campaign.recipient_count,
            "offered_discount_percent": float(campaign.offered_discount_percent),
            "message_template": campaign.message_template
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/dispatch")
async def dispatch_campaign(
    campaign_id: str,
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """Dispatch campaign in simulated mode."""
    try:
        camp = await CampaignService.dispatch_campaign(db, campaign_id, merchant_id)
        return {
            "campaign_id": camp.id,
            "status": camp.status,
            "is_simulated": camp.is_simulated,
            "simulated_opens": camp.simulated_opens,
            "simulated_conversions": camp.simulated_conversions,
            "simulated_revenue_paise": camp.simulated_revenue_paise
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/group-deals")
async def get_group_deals(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """List community group deals."""
    result = await db.execute(
        select(CommunityGroupDeal).where(CommunityGroupDeal.merchant_id == merchant_id)
    )
    deals = result.scalars().all()
    return {
        "merchant_id": merchant_id,
        "deals": [
            {
                "id": d.id,
                "deal_code": d.deal_code,
                "target_group_name": d.target_group_name,
                "product_id": d.product_id,
                "min_threshold_units": d.min_threshold_units,
                "current_pledged_units": d.current_pledged_units,
                "base_price_paise": d.base_price_paise,
                "discounted_price_paise": d.discounted_price_paise,
                "gross_margin_percent": float(d.gross_margin_percent),
                "status": d.status,
                "is_simulated": d.is_simulated,
                "expires_at": d.expires_at.isoformat() if d.expires_at else None
            }
            for d in deals
        ]
    }


@router.post("/group-deals/create")
async def create_group_deal(
    req: CreateGroupDealRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a community group deal verifying margin floor protection."""
    try:
        deal = await CampaignService.create_group_deal(
            db=db,
            merchant_id=req.merchant_id,
            target_group_name=req.target_group_name,
            product_id=req.product_id,
            min_threshold_units=req.min_threshold_units,
            discounted_price_paise=req.discounted_price_paise
        )
        return {
            "deal_id": deal.id,
            "deal_code": deal.deal_code,
            "status": deal.status,
            "gross_margin_percent": float(deal.gross_margin_percent),
            "min_threshold_units": deal.min_threshold_units
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-deals/{deal_id}/pledge")
async def pledge_group_deal(
    deal_id: str,
    req: PledgeGroupDealRequest,
    db: AsyncSession = Depends(get_db)
):
    """Pledge units towards group deal threshold."""
    try:
        deal = await CampaignService.pledge_group_deal(db, deal_id, req.units or 1)
        return {
            "deal_id": deal.id,
            "deal_code": deal.deal_code,
            "current_pledged_units": deal.current_pledged_units,
            "min_threshold_units": deal.min_threshold_units,
            "status": deal.status
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
