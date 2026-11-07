"""Clean-Database Rebuild Test.

Proves that an empty database can be completely initialized from models,
seeded with Atlas Travel Gear, and queried for MerchantCommerceContext without
any manual intervention or pre-existing state.
"""

import os
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from domain.models import Base
from services.commerce_service import CommerceService
from domain.commerce_schemas import (
    MerchantCreateRequest,
    ProductCreateRequest,
    RelationshipCreateRequest,
    PrioritiesUpdateRequest
)

CLEAN_DB_FILE = "./clean_rebuild_test.db"
CLEAN_DB_URL = f"sqlite+aiosqlite:///{CLEAN_DB_FILE}"


@pytest.mark.asyncio
async def test_clean_database_rebuild_and_seed():
    """Verify clean database lifecycle: Empty -> Schema Creation -> Seed -> Context Retrieval."""
    # 1. Ensure clean slate
    if os.path.exists(CLEAN_DB_FILE):
        os.remove(CLEAN_DB_FILE)

    engine = create_async_engine(CLEAN_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        # 2. Schema Creation (simulating clean migration)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        commerce_svc = CommerceService()
        merchant_id = "merch_atlas_travel"

        # 3. Seed Merchant
        async with session_factory() as session:
            m_req = MerchantCreateRequest(
                id=merchant_id,
                name="Atlas Travel Gear",
                currency="INR",
                business_objective="BALANCE_REVENUE_AND_MARGIN",
                minimum_margin_percent=Decimal("25.00"),
                maximum_discount_percent=Decimal("8.00"),
                target_aov_paise=400000
            )
            merchant = await commerce_svc.create_merchant(session, m_req)
            assert merchant.id == merchant_id

        # 4. Seed Products
        products = [
            ProductCreateRequest(
                id="prod_travel_backpack",
                sku="SKU-BACKPACK-01",
                name="Atlas All-Weather Travel Backpack (35L)",
                category="Bags & Luggage",
                price_paise=299900,
                cost_paise=180000,
                currency="INR",
                inventory_quantity=30
            ),
            ProductCreateRequest(
                id="prod_laptop_sleeve",
                sku="SKU-SLEEVE-02",
                name="Shock-Resistant 16-Inch Laptop Sleeve",
                category="Electronics Accessories",
                price_paise=79900,
                cost_paise=35000,
                currency="INR",
                inventory_quantity=50
            )
        ]

        async with session_factory() as session:
            for p_req in products:
                p = await commerce_svc.create_product(session, merchant_id, p_req)
                assert p.id == p_req.id

        # 5. Seed Relationship
        async with session_factory() as session:
            r_req = RelationshipCreateRequest(
                primary_product_id="prod_travel_backpack",
                related_product_id="prod_laptop_sleeve",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.85"),
                source="merchant_defined"
            )
            rel = await commerce_svc.create_product_relationship(session, merchant_id, r_req)
            assert rel.relationship_type == "COMPLEMENTARY"

        # 6. Retrieve Commerce Context
        async with session_factory() as session:
            context = await commerce_svc.get_merchant_commerce_context(session, merchant_id)
            assert context.merchant_id == merchant_id
            assert len(context.products) == 2
            assert len(context.relationships) == 1
            assert context.constraints["minimum_margin_percent"] == Decimal("25.00")
            assert context.products[0].gross_profit_paise > 0
            assert context.products[0].is_eligible is True

    finally:
        await engine.dispose()
        if os.path.exists(CLEAN_DB_FILE):
            try:
                os.remove(CLEAN_DB_FILE)
            except OSError:
                pass
