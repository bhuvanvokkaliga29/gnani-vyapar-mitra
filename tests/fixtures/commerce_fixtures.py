"""Reusable test fixtures and mock builders for MerchantCommerceContext."""

from decimal import Decimal
from datetime import datetime, timezone
from domain.commerce_schemas import (
    MerchantCommerceContext,
    ProductResponse,
    RelationshipResponse
)


def build_test_commerce_context(
    merchant_id: str = "merch_atlas_travel",
    business_objective: str = "BALANCE_REVENUE_AND_MARGIN",
    minimum_margin_percent: Decimal = Decimal("25.00"),
    maximum_discount_percent: Decimal = Decimal("8.00"),
    target_aov_paise: int = 400000
) -> MerchantCommerceContext:
    """Build a complete, realistic MerchantCommerceContext for policy testing."""
    now = datetime.now(timezone.utc)

    products = [
        ProductResponse(
            id="prod_backpack_01",
            merchant_id=merchant_id,
            sku="ATLAS-APEX-BP",
            name="Atlas Apex Travel Backpack",
            description="Premium water-resistant travel backpack designed for business travel and daily commute. Fits 16-inch laptop.",
            category="travel_backpack",
            price_paise=499900,
            cost_paise=250000,
            currency="INR",
            inventory_quantity=20,
            reserved_quantity=5,
            available_to_sell=15,
            gross_profit_paise=249900,
            gross_margin_percent=Decimal("49.99"),
            is_active=True,
            is_eligible=True,
            ineligibility_reason=None,
            attributes={
                "laptop_size": 16.0,
                "material": "nylon",
                "color": "black",
                "water_resistant": True,
                "weight": "lightweight"
            },
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_daypack_01",
            merchant_id=merchant_id,
            sku="ATLAS-DAY-DP",
            name="Atlas Daily Commute Daypack",
            description="Compact daily commute daypack fitting 15-inch laptops.",
            category="travel_backpack",
            price_paise=299900,
            cost_paise=150000,
            currency="INR",
            inventory_quantity=25,
            reserved_quantity=5,
            available_to_sell=20,
            gross_profit_paise=149900,
            gross_margin_percent=Decimal("49.98"),
            is_active=True,
            is_eligible=True,
            ineligibility_reason=None,
            attributes={
                "laptop_size": 15.0,
                "material": "polyester",
                "color": "grey",
                "water_resistant": True
            },
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_sleeve_01",
            merchant_id=merchant_id,
            sku="ATLAS-SLV-16",
            name="Atlas Armor Laptop Sleeve 16-inch",
            description="Shock-absorbing laptop sleeve fitting up to 16-inch laptops.",
            category="laptop_sleeve",
            price_paise=99900,
            cost_paise=40000,
            currency="INR",
            inventory_quantity=30,
            reserved_quantity=5,
            available_to_sell=25,
            gross_profit_paise=59900,
            gross_margin_percent=Decimal("59.96"),
            is_active=True,
            is_eligible=True,
            ineligibility_reason=None,
            attributes={
                "laptop_size": 16.0,
                "material": "neoprene",
                "color": "black"
            },
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_sleeve_14_inch",
            merchant_id=merchant_id,
            sku="ATLAS-SLV-14",
            name="Atlas Compact Sleeve 14-inch",
            description="Sleeve fitting 14-inch laptops only.",
            category="laptop_sleeve",
            price_paise=89900,
            cost_paise=35000,
            currency="INR",
            inventory_quantity=10,
            reserved_quantity=0,
            available_to_sell=10,
            gross_profit_paise=54900,
            gross_margin_percent=Decimal("61.07"),
            is_active=True,
            is_eligible=True,
            ineligibility_reason=None,
            attributes={
                "laptop_size": 14.0,
                "material": "neoprene",
                "color": "black"
            },
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_leather_backpack_01",
            merchant_id=merchant_id,
            sku="ATLAS-LTH-BP",
            name="Atlas Heritage Leather Pack",
            description="Handcrafted genuine leather backpack.",
            category="travel_backpack",
            price_paise=699900,
            cost_paise=450000,
            currency="INR",
            inventory_quantity=10,
            reserved_quantity=2,
            available_to_sell=8,
            gross_profit_paise=249900,
            gross_margin_percent=Decimal("35.71"),
            is_active=True,
            is_eligible=True,
            ineligibility_reason=None,
            attributes={
                "material": "leather",
                "color": "brown"
            },
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_mouse_01",
            merchant_id=merchant_id,
            sku="ATLAS-MOU-01",
            name="Atlas Ergonomic Wireless Mouse",
            description="Bluetooth ergonomic wireless mouse.",
            category="wireless_mouse",
            price_paise=129900,
            cost_paise=60000,
            currency="INR",
            inventory_quantity=50,
            reserved_quantity=5,
            available_to_sell=45,
            gross_profit_paise=69900,
            gross_margin_percent=Decimal("53.81"),
            is_active=True,
            is_eligible=True,
            ineligibility_reason=None,
            attributes={
                "connectivity": "bluetooth",
                "color": "black"
            },
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_out_of_stock_sleeve",
            merchant_id=merchant_id,
            sku="ATLAS-OOS-SLV",
            name="Atlas Out Of Stock Sleeve",
            description="Sold out item.",
            category="laptop_sleeve",
            price_paise=99900,
            cost_paise=40000,
            currency="INR",
            inventory_quantity=0,
            reserved_quantity=0,
            available_to_sell=0,
            gross_profit_paise=59900,
            gross_margin_percent=Decimal("59.96"),
            is_active=True,
            is_eligible=False,
            ineligibility_reason="Insufficient inventory available to sell",
            attributes={},
            created_at=now,
            updated_at=now
        ),
        ProductResponse(
            id="prod_low_margin_backpack",
            merchant_id=merchant_id,
            sku="ATLAS-LOW-MGN",
            name="Atlas Clearance Pack",
            description="Low margin clearance pack.",
            category="travel_backpack",
            price_paise=200000,
            cost_paise=180000,
            currency="INR",
            inventory_quantity=10,
            reserved_quantity=0,
            available_to_sell=10,
            gross_profit_paise=20000,
            gross_margin_percent=Decimal("10.00"),
            is_active=True,
            is_eligible=False,
            ineligibility_reason="Product margin 10.00% is below minimum required margin 25.00%",
            attributes={"color": "blue"},
            created_at=now,
            updated_at=now
        )
    ]

    relationships = [
        RelationshipResponse(
            id=1,
            merchant_id=merchant_id,
            primary_product_id="prod_backpack_01",
            related_product_id="prod_sleeve_01",
            relationship_type="COMPLEMENTARY",
            affinity_score=Decimal("0.85"),
            source="merchant_defined",
            confidence=Decimal("1.00"),
            created_at=now
        ),
        RelationshipResponse(
            id=2,
            merchant_id=merchant_id,
            primary_product_id="prod_backpack_01",
            related_product_id="prod_daypack_01",
            relationship_type="SUBSTITUTE",
            affinity_score=Decimal("0.70"),
            source="merchant_defined",
            confidence=Decimal("1.00"),
            created_at=now
        ),
        RelationshipResponse(
            id=3,
            merchant_id=merchant_id,
            primary_product_id="prod_backpack_01",
            related_product_id="prod_mouse_01",
            relationship_type="CROSS_SELL",
            affinity_score=Decimal("0.50"),
            source="merchant_defined",
            confidence=Decimal("1.00"),
            created_at=now
        )
    ]

    return MerchantCommerceContext(
        merchant_id=merchant_id,
        merchant_name="Atlas Travel Gear",
        currency="INR",
        status="active",
        business_objective=business_objective,
        constraints={
            "minimum_margin_percent": minimum_margin_percent,
            "maximum_discount_percent": maximum_discount_percent,
            "target_aov_paise": target_aov_paise
        },
        priorities={
            "priority_product_ids": ["prod_backpack_01"],
            "priority_categories": ["travel_backpack"],
            "clearance_product_ids": []
        },
        products=products,
        relationships=relationships,
        generated_at=now
    )
