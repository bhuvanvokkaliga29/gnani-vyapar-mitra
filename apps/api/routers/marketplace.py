"""FastAPI Router for Marketplace Growth Manager Endpoints."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from apps.api.core.database import get_db
from domain.models import Product
from services.marketplace.service import MarketplaceGrowthService

router = APIRouter(prefix="/api/v1/marketplace", tags=["Marketplace Growth Manager"])


class GenerateListingRequest(BaseModel):
    merchant_id: str
    product_id: str
    channel_id: Optional[str] = "AMAZON"


class ExportOndcRequest(BaseModel):
    merchant_id: str
    product_id: str


@router.get("/channels")
async def get_channels(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve channel economics configuration matrix."""
    channels = await MarketplaceGrowthService.ensure_default_channels(db, merchant_id)
    return {
        "merchant_id": merchant_id,
        "channels": [
            {
                "channel_id": c.channel_id,
                "name": c.name,
                "fee_percent": float(c.fee_percent),
                "fixed_fee_paise": c.fixed_fee_paise,
                "shipping_base_paise": c.shipping_base_paise,
                "return_rate_percent": float(c.return_rate_percent),
                "return_cost_paise": c.return_cost_paise,
                "ad_cost_paise": c.ad_cost_paise,
                "verification_status": c.verification_status,
                "audience_fit": c.audience_fit,
                "is_active": c.is_active
            }
            for c in channels
        ]
    }


@router.get("/plan")
async def get_marketplace_plan(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """Generate per-SKU channel economics and LIST / HOLD / DIRECT_CHANNEL recommendations."""
    try:
        plan = await MarketplaceGrowthService.generate_channel_plan(db, merchant_id)
        return {
            "merchant_id": merchant_id,
            "sku_count": len(plan),
            "plan": plan
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/listings/generate")
async def generate_listing_pack(
    req: GenerateListingRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate channel listing pack strictly grounded in verified product attributes."""
    product = (await db.execute(
        select(Product).where(and_(Product.id == req.product_id, Product.merchant_id == req.merchant_id))
    )).scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{req.product_id}' not found")

    pack = MarketplaceGrowthService.generate_listing_pack(
        product=product,
        channel_id=req.channel_id or "AMAZON"
    )
    return pack


@router.post("/export/ondc")
async def export_ondc_catalog(
    req: ExportOndcRequest,
    db: AsyncSession = Depends(get_db)
):
    """Export product in standard ONDC Beckn catalog JSON schema."""
    product = (await db.execute(
        select(Product).where(and_(Product.id == req.product_id, Product.merchant_id == req.merchant_id))
    )).scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{req.product_id}' not found")

    pack = MarketplaceGrowthService.generate_listing_pack(product=product, channel_id="ONDC")
    return {
        "status": "EXPORT_SUCCESS",
        "format": "ONDC_BECKN_V1.2",
        "ondc_catalog_json": pack["ondc_export_json"]
    }
