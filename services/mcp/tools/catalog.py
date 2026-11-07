"""Catalog discovery tools for MCP: search_catalog and get_product.

Contract: mcp-commerce/v1

INVARIANTS:
1. Reuses CommerceService (services/commerce_service.py). Zero duplicate catalog logic.
2. Tenant scope is derived from authenticated context, not tool arguments.
3. Every output is filtered through BuyerResponseFirewall. Zero cost or margin leakage.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import AsyncSessionLocal
from services.commerce_service import CommerceService
from services.mcp.schemas import McpCapability, BuyerSafeProductView
from services.mcp.auth import check_capability, get_current_auth_context
from services.mcp.firewall import BuyerResponseFirewall
from services.mcp.errors import McpProductNotFoundError

logger = structlog.get_logger()
_commerce_service = CommerceService()


async def search_catalog(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price_paise: Optional[int] = None,
    currency: str = "INR",
    db: Optional[AsyncSession] = None
) -> List[BuyerSafeProductView]:
    """Search and discover buyer-visible products in the merchant's catalog.
    
    Args:
        query: Optional text search string matching product name or description.
        category: Optional category filter (e.g. 'Backpacks', 'Travel Gear').
        max_price_paise: Optional maximum price ceiling in integer paise.
        currency: Three-letter currency code (default: INR).
        db: Optional database session for test execution.
    
    Returns:
        List of sanitized, buyer-safe product views (zero COGS or margin leakage).
    """
    check_capability(McpCapability.CATALOG_READ)
    identity = get_current_auth_context()
    merchant_id = identity.merchant_id

    async def _execute(session: AsyncSession) -> List[BuyerSafeProductView]:
        products = await _commerce_service.list_products(session, merchant_id, active_only=True)
        results: List[BuyerSafeProductView] = []

        query_clean = query.strip().lower() if query else None
        cat_clean = category.strip().lower() if category else None

        for p in products:
            # Category match
            if cat_clean and (p.category or "").lower() != cat_clean:
                continue

            # Budget match
            if max_price_paise is not None and p.price_paise > max_price_paise:
                continue

            # Text query match
            if query_clean:
                name_match = query_clean in (p.name or "").lower()
                desc_match = query_clean in (p.description or "").lower()
                cat_match = query_clean in (p.category or "").lower()
                if not (name_match or desc_match or cat_match):
                    continue

            results.append(BuyerResponseFirewall.sanitize_product(p))

        logger.info(
            "mcp_search_catalog_executed",
            merchant_id=merchant_id,
            query=query,
            category=category,
            max_price_paise=max_price_paise,
            matched_count=len(results)
        )
        return results

    if db is not None:
        return await _execute(db)
    async with AsyncSessionLocal() as session:
        return await _execute(session)


async def get_product(
    product_id: str,
    db: Optional[AsyncSession] = None
) -> BuyerSafeProductView:
    """Retrieve detailed, buyer-safe information for a single catalog product.
    
    Args:
        product_id: Authoritative product identifier (e.g. prod_atlas_backpack).
        db: Optional database session for test execution.
        
    Returns:
        Authoritative BuyerSafeProductView.
        
    Raises:
        McpProductNotFoundError: If product does not exist or belongs to another merchant.
    """
    check_capability(McpCapability.CATALOG_READ)
    identity = get_current_auth_context()
    merchant_id = identity.merchant_id

    async def _execute(session: AsyncSession) -> BuyerSafeProductView:
        product = await _commerce_service.get_product(session, product_id)
        if not product or product.merchant_id != merchant_id or not product.is_active:
            logger.warn("mcp_product_not_found", product_id=product_id, merchant_id=merchant_id)
            raise McpProductNotFoundError(
                f"Product '{product_id}' was not found in merchant '{merchant_id}' catalog.",
                details={"product_id": product_id, "merchant_id": merchant_id}
            )

        return BuyerResponseFirewall.sanitize_product(product)

    if db is not None:
        return await _execute(db)
    async with AsyncSessionLocal() as session:
        return await _execute(session)
