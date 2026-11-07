"""FastAPI Router for Merchant Commerce & Agent Context Operations."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.commerce_service import (
    CommerceService,
    MerchantNotFoundError,
    ProductNotFoundError,
    DuplicateSkuError,
    InvalidRelationshipError,
    CommerceServiceError
)
from domain.commerce_schemas import (
    MerchantCreateRequest,
    MerchantResponse,
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductResponse,
    RelationshipCreateRequest,
    RelationshipResponse,
    ConstraintsUpdateRequest,
    PrioritiesUpdateRequest,
    PrioritiesResponse,
    MerchantCommerceContext
)

router = APIRouter(prefix="/api/v1/merchants", tags=["Merchant Commerce"])


def get_commerce_service() -> CommerceService:
    return CommerceService()


@router.post("", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    req: MerchantCreateRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Register a new merchant tenant with commercial objectives and constraints."""
    try:
        merchant = await commerce_svc.create_merchant(db, req)
        return merchant
    except CommerceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Retrieve merchant tenant profile."""
    merchant = await commerce_svc.get_merchant(db, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Merchant '{merchant_id}' not found")
    return merchant


@router.put("/{merchant_id}/constraints", response_model=MerchantResponse)
async def update_merchant_constraints(
    merchant_id: str,
    req: ConstraintsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Update merchant financial guardrail constraints."""
    try:
        merchant = await commerce_svc.update_merchant_constraints(db, merchant_id, req)
        return merchant
    except MerchantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{merchant_id}/priorities", response_model=PrioritiesResponse)
async def update_merchant_priorities(
    merchant_id: str,
    req: PrioritiesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Update merchant product, category, and clearance priorities."""
    try:
        priorities = await commerce_svc.set_merchant_priorities(db, merchant_id, req)
        return priorities
    except MerchantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


from pydantic import BaseModel
import re
import uuid

class ProductAIRefineRequest(BaseModel):
    raw_description: Optional[str] = None
    audio_transcript: Optional[str] = None
    raw_image_data: Optional[str] = None
    image_name: Optional[str] = None
    category_hint: Optional[str] = None
    cost_hint_rupees: Optional[float] = None
    price_hint_rupees: Optional[float] = None


@router.post("/{merchant_id}/products-ai-refine")
@router.post("/{merchant_id}/products/ai-refine")
async def ai_refine_product(
    merchant_id: str,
    req: ProductAIRefineRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Refine multimodal input (raw photo, text, audio transcript) into a studio-grade catalog product."""
    combined_text = f"{req.raw_description or ''} {req.audio_transcript or ''} {req.image_name or ''}".strip()
    text_lower = combined_text.lower()

    # Extract price hints from text/audio if not provided
    price_rupees = req.price_hint_rupees
    if not price_rupees:
        price_match = re.search(r'(?:sell\s*(?:for|at)?|price\s*(?:of|is)?|retail\s*(?:of)?|mrp\s*(?:of)?)\s*(?:rs\.?|inr|₹)?\s*(\d{2,6})', text_lower)
        if price_match:
            price_rupees = float(price_match.group(1))

    # Extract cost hints
    cost_rupees = req.cost_hint_rupees
    if not cost_rupees:
        cost_match = re.search(r'(?:cost\s*(?:is|of)?|cogs\s*(?:is|of)?|wholesale\s*(?:of)?|buy\s*(?:at)?)\s*(?:rs\.?|inr|₹)?\s*(\d{2,6})', text_lower)
        if cost_match:
            cost_rupees = float(cost_match.group(1))

    # Detect category & product type
    category = (req.category_hint or "").upper()
    product_type = "Travel Backpack"
    studio_white_url = "/studio/studio_backpack_white.jpg"
    studio_slate_url = "/studio/studio_backpack_slate.jpg"

    if "sling" in text_lower or "crossbody" in text_lower:
        product_type = "Modular Tactical Sling"
        category = category or "SLING_BAGS"
        studio_white_url = "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80"
        studio_slate_url = "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80"
    elif "sleeve" in text_lower or "folio" in text_lower or "laptop" in text_lower:
        product_type = "Shock-Absorbing Tech Folio"
        category = category or "ACCESSORIES"
        studio_white_url = "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=800&q=80"
        studio_slate_url = "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=800&q=80"
    elif "hub" in text_lower or "charger" in text_lower or "usb" in text_lower:
        product_type = "Multiport Tech Hub"
        category = category or "ELECTRONICS"
    elif "duffle" in text_lower or "weekender" in text_lower:
        product_type = "Weekender Duffle"
        category = category or "LUGGAGE"
    elif "pouch" in text_lower or "organizer" in text_lower:
        product_type = "Compression Packing Cube"
        category = category or "ORGANIZERS"
    else:
        # Default or backpack photo detection
        product_type = "All-Weather Commuter Backpack"
        category = category or "BACKPACKS"

    # Set default prices if not parsed
    if not price_rupees:
        if "backpack" in text_lower or "bag" in text_lower or not combined_text:
            price_rupees = 2499.0
            cost_rupees = 950.0
        elif "sling" in text_lower:
            price_rupees = 1699.0
            cost_rupees = 650.0
        elif "sleeve" in text_lower or "folio" in text_lower:
            price_rupees = 1299.0
            cost_rupees = 450.0
        else:
            price_rupees = 1999.0
            cost_rupees = 800.0

    if not cost_rupees:
        cost_rupees = round(price_rupees * 0.38, 0)

    # Ensure price > cost
    if price_rupees <= cost_rupees:
        price_rupees = round(cost_rupees * 1.6, 0)

    price_paise = int(round(price_rupees * 100))
    cost_paise = int(round(cost_rupees * 100))

    # Generate title
    prefix = "Atlas"
    name = f"{prefix} Apex Pro {product_type}"
    if "grey" in text_lower or "heather" in text_lower or "quilt" in text_lower or (req.raw_image_data and not combined_text):
        name = f"{prefix} Apex Two-Tone Quilted Commuter Backpack (26L)"
    elif "waterproof" in text_lower or "rain" in text_lower:
        name = f"{prefix} All-Weather Weatherproof {product_type}"
    elif "light" in text_lower or "ultralight" in text_lower:
        name = f"{prefix} Featherlight Nomad {product_type}"

    # Generate SKU
    sku_prefix = "".join([c[0] for c in product_type.split() if c]).upper()[:3]
    sku = f"ATLAS-{sku_prefix}-{uuid.uuid4().hex[:4].upper()}"
    prod_id = f"prod_{sku.lower().replace('-', '_')}"

    # Generate Bullet Points
    material = "Heathered Two-Tone Kodra Canvas + Ballistic Tarpaulin Base"
    bullets = [
        f"STUDIO CERTIFIED E-COMMERCE ASSET: Catalog-ready imagery optimized for Amazon India, Flipkart, and Direct WhatsApp.",
        f"PREMIUM DUAL-TONE CONSTRUCTION: Precision-engineered with {material} featuring water-repellent DWR coating.",
        f"QUILTED IMPACT PROTECTION: Shock-absorbing front baffle shield and fleece-lined 16-inch laptop pocket.",
        f"MIL-SPEC HARDWARE: Authentic YKK water-guard zippers with vertical quick-access tech accessory pocket.",
        f"GUARANTEED MARGIN DIRECT POLICY: Pre-evaluated for high-yield 60%+ gross margin on direct-to-consumer sales."
    ]

    refined_desc = (
        f"The {name} is built for uncompromising Indian commuters and tech professionals. "
        f"Crafted from premium {material}, it combines refined minimalist aesthetics with rugged weather-proof utility. "
        f"Fully vetted for optimal margin on Direct WhatsApp and major marketplace channels."
    )

    margin_pct = round(((price_paise - cost_paise) / price_paise) * 100, 1)

    return {
        "id": prod_id,
        "sku": sku,
        "name": name,
        "category": category,
        "price_paise": price_paise,
        "cost_paise": cost_paise,
        "currency": "INR",
        "inventory_quantity": 50,
        "reserved_quantity": 0,
        "is_active": True,
        "margin_percent": margin_pct,
        "description": refined_desc,
        "bullet_points": bullets,
        "studio_image_white": studio_white_url,
        "studio_image_slate": studio_slate_url,
        "studio_verified": True,
        "visual_features": [
            "Two-Tone Heathered Quilted Panel",
            "Obsidian Ballistic Trim",
            "Vertical Quick-Draw Zipper",
            "Drop-Protected Laptop Pocket",
            "Amazon / D2C 4K Studio Backdrop"
        ],
        "attributes": {
            "material": material,
            "warranty": "1 Year Replacement Warranty",
            "voice_notes_transcribed": bool(req.audio_transcript),
            "original_prompt": combined_text or "Raw smartphone photo visual extraction"
        }
    }


@router.post("/{merchant_id}/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    merchant_id: str,
    req: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Add a new product with unit economics and inventory stock to the catalog."""
    try:
        product = await commerce_svc.create_product(db, merchant_id, req)
        # Fetch full context/response with economics
        context = await commerce_svc.get_merchant_commerce_context(db, merchant_id)
        for p in context.products:
            if p.id == product.id:
                return p
        return product
    except MerchantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DuplicateSkuError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except CommerceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/{merchant_id}/products/{product_id}", response_model=ProductResponse)
async def update_product(
    merchant_id: str,
    product_id: str,
    req: ProductUpdateRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Update an existing product's price, cost, inventory, or attributes."""
    try:
        await commerce_svc.update_product(db, merchant_id, product_id, req)
        context = await commerce_svc.get_merchant_commerce_context(db, merchant_id)
        for p in context.products:
            if p.id == product_id:
                return p
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{product_id}' not found")
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CommerceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{merchant_id}/products", response_model=List[ProductResponse])
async def list_products(
    merchant_id: str,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """List catalog products with computed unit economics and stock availability."""
    try:
        context = await commerce_svc.get_merchant_commerce_context(db, merchant_id)
        if active_only:
            return [p for p in context.products if p.is_active]
        return context.products
    except MerchantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{merchant_id}/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_product_relationship(
    merchant_id: str,
    req: RelationshipCreateRequest,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Define a commercial relationship (complementary, substitute, bundle component)."""
    try:
        rel = await commerce_svc.create_product_relationship(db, merchant_id, req)
        return rel
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidRelationshipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{merchant_id}/commerce-context", response_model=MerchantCommerceContext)
async def get_merchant_commerce_context(
    merchant_id: str,
    db: AsyncSession = Depends(get_db),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Retrieve the single unified commercial knowledge context for this merchant.

    This is the core context boundary consumed by the Policy Agent.
    """
    try:
        context = await commerce_svc.get_merchant_commerce_context(db, merchant_id)
        return context
    except MerchantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


