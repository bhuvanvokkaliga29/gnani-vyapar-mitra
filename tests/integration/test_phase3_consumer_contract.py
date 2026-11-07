"""Phase 2 -> Phase 3 Consumer Contract and Schema Round-Trip Tests.

Proves that downstream Policy Agents can consume MerchantCommerceContext without
any database access, and that the context object survives strict JSON round-tripping.
"""

import json
from datetime import datetime, timezone
import pytest
from decimal import Decimal
from typing import List, Dict, Optional, Any
from domain.commerce_schemas import MerchantCommerceContext, ProductResponse, RelationshipResponse
from domain.economics import BasketItem, evaluate_basket_economics


class DummyPolicyAgentConsumer:
    """Mock Policy Agent reasoning consumer operating exclusively on MerchantCommerceContext.

    Has ZERO database connection and ZERO SQL access.
    """

    def __init__(self, context: MerchantCommerceContext):
        self.context = context

    def get_merchant_objective(self) -> str:
        return self.context.business_objective

    def get_margin_floor(self) -> Decimal:
        val = self.context.constraints.get("minimum_margin_percent")
        return Decimal(str(val))

    def get_discount_ceiling(self) -> Decimal:
        val = self.context.constraints.get("maximum_discount_percent")
        return Decimal(str(val))

    def get_eligible_products(self) -> List[ProductResponse]:
        """Find catalog products currently in stock and compliant with margin floor."""
        return [p for p in self.context.products if p.is_eligible and p.available_to_sell > 0]

    def get_complementary_skus(self, primary_product_id: str) -> List[str]:
        """Find products marked COMPLEMENTARY to the given primary product."""
        return [
            r.related_product_id
            for r in self.context.relationships
            if r.primary_product_id == primary_product_id and r.relationship_type == "COMPLEMENTARY"
        ]

    def get_substitutes(self, primary_product_id: str) -> List[str]:
        """Find substitute products."""
        return [
            r.related_product_id
            for r in self.context.relationships
            if r.primary_product_id == primary_product_id and r.relationship_type == "SUBSTITUTE"
        ]

    def evaluate_bundle_proposal(self, product_ids: List[str], discount_paise: int = 0):
        """Evaluate whether a proposed bundle satisfies merchant guardrails."""
        prod_map = {p.id: p for p in self.context.products}
        items = [
            BasketItem(
                product_id=pid,
                quantity=1,
                unit_price_paise=prod_map[pid].price_paise,
                unit_cost_paise=prod_map[pid].cost_paise
            )
            for pid in product_ids
        ]
        return evaluate_basket_economics(
            items=items,
            promotional_discount_paise=discount_paise,
            minimum_margin_percent=self.get_margin_floor(),
            maximum_discount_percent=self.get_discount_ceiling()
        )


def test_schema_round_trip():
    """Verify MerchantCommerceContext survives full JSON serialization and deserialization."""
    now = datetime.now(timezone.utc)

    sample_data = {
        "merchant_id": "merch_round_trip",
        "merchant_name": "Round Trip Merchant",
        "currency": "INR",
        "status": "active",
        "business_objective": "BALANCE_REVENUE_AND_MARGIN",
        "constraints": {
            "minimum_margin_percent": Decimal("25.00"),
            "maximum_discount_percent": Decimal("8.00"),
            "target_aov_paise": 400000
        },
        "priorities": {
            "priority_product_ids": ["p1"],
            "priority_categories": ["Cat"],
            "clearance_product_ids": []
        },
        "products": [
            ProductResponse(
                id="p1",
                merchant_id="merch_round_trip",
                sku="SKU-1",
                name="Item 1",
                category="Cat",
                price_paise=10000,
                cost_paise=6000,
                currency="INR",
                inventory_quantity=20,
                reserved_quantity=2,
                available_to_sell=18,
                gross_profit_paise=4000,
                gross_margin_percent=Decimal("40.00"),
                is_active=True,
                is_eligible=True,
                ineligibility_reason=None,
                attributes={"color": "black"},
                created_at=now,
                updated_at=now
            )
        ],
        "relationships": [
            RelationshipResponse(
                id=1,
                merchant_id="merch_round_trip",
                primary_product_id="p1",
                related_product_id="p2",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.85"),
                source="merchant_defined",
                confidence=Decimal("1.00"),
                created_at=now
            )
        ],
        "generated_at": now
    }

    # 1. Pydantic instance -> JSON string
    ctx_orig = MerchantCommerceContext(**sample_data)
    json_str = ctx_orig.model_dump_json()

    # 2. JSON string -> Dict -> Pydantic instance
    parsed_dict = json.loads(json_str)
    ctx_reconstructed = MerchantCommerceContext.model_validate(parsed_dict)

    # 3. Assert exact equality
    assert ctx_reconstructed.merchant_id == ctx_orig.merchant_id
    assert ctx_reconstructed.products[0].available_to_sell == 18
    assert ctx_reconstructed.products[0].gross_margin_percent == Decimal("40.00")
    assert ctx_reconstructed.relationships[0].relationship_type == "COMPLEMENTARY"


def test_phase3_dummy_consumer_reasoning():
    """Verify dummy consumer answers commercial reasoning queries without database access."""
    now = datetime.now(timezone.utc)

    backpack = ProductResponse(
        id="prod_bp",
        merchant_id="merch_test",
        sku="SKU-BP",
        name="Backpack",
        category="Luggage",
        price_paise=300000,  # ₹3,000
        cost_paise=180000,   # ₹1,800
        currency="INR",
        inventory_quantity=10,
        reserved_quantity=0,
        available_to_sell=10,
        gross_profit_paise=120000,
        gross_margin_percent=Decimal("40.00"),
        is_active=True,
        is_eligible=True,
        ineligibility_reason=None,
        attributes={},
        created_at=now,
        updated_at=now
    )
    sleeve = ProductResponse(
        id="prod_sl",
        merchant_id="merch_test",
        sku="SKU-SL",
        name="Laptop Sleeve",
        category="Accessories",
        price_paise=80000,   # ₹800
        cost_paise=35000,    # ₹350
        currency="INR",
        inventory_quantity=20,
        reserved_quantity=0,
        available_to_sell=20,
        gross_profit_paise=45000,
        gross_margin_percent=Decimal("56.25"),
        is_active=True,
        is_eligible=True,
        ineligibility_reason=None,
        attributes={},
        created_at=now,
        updated_at=now
    )

    context = MerchantCommerceContext(
        merchant_id="merch_test",
        merchant_name="Test Merchant",
        currency="INR",
        status="active",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        constraints={
            "minimum_margin_percent": Decimal("25.00"),
            "maximum_discount_percent": Decimal("8.00"),
            "target_aov_paise": 400000
        },
        priorities={"priority_product_ids": ["prod_bp"]},
        products=[backpack, sleeve],
        relationships=[
            RelationshipResponse(
                id=1,
                merchant_id="merch_test",
                primary_product_id="prod_bp",
                related_product_id="prod_sl",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.85"),
                source="merchant_defined",
                confidence=Decimal("1.00"),
                created_at=now
            )
        ]
    )

    consumer = DummyPolicyAgentConsumer(context)

    # 1. Answer: What is the optimization goal?
    assert consumer.get_merchant_objective() == "BALANCE_REVENUE_AND_MARGIN"

    # 2. Answer: What products are available to offer?
    assert len(consumer.get_eligible_products()) == 2

    # 3. Answer: What complements the Backpack?
    assert consumer.get_complementary_skus("prod_bp") == ["prod_sl"]

    # 4. Answer: Evaluate candidate bundle (Backpack + Sleeve with 5% discount)
    proposal_eval = consumer.evaluate_bundle_proposal(["prod_bp", "prod_sl"], discount_paise=19000)
    assert proposal_eval.is_compliant is True
    assert proposal_eval.gross_profit_paise == (380000 - 19000) - (180000 + 35000)
