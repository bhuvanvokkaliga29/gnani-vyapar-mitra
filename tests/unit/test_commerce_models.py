"""Unit tests for Phase 2 Pydantic schema validation and business constraints."""

import pytest
from decimal import Decimal
from pydantic import ValidationError
from domain.commerce_schemas import (
    MerchantCreateRequest,
    ProductCreateRequest,
    RelationshipCreateRequest,
    ConstraintsUpdateRequest
)


def test_valid_merchant_create_schema():
    """Verify valid merchant registration parameters."""
    req = MerchantCreateRequest(
        id="merch_test_valid",
        name="Test Merchant",
        currency="INR",
        business_objective="MAXIMIZE_CONTRIBUTION",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("10.00"),
        target_aov_paise=350000
    )
    assert req.id == "merch_test_valid"
    assert req.minimum_margin_percent == Decimal("20.00")


def test_merchant_schema_invalid_bounds():
    """Verify rejection of invalid margin or discount bounds."""
    # Negative margin
    with pytest.raises(ValidationError):
        MerchantCreateRequest(
            id="m1",
            name="M1",
            minimum_margin_percent=Decimal("-5.00")
        )

    # Discount > 100%
    with pytest.raises(ValidationError):
        MerchantCreateRequest(
            id="m1",
            name="M1",
            maximum_discount_percent=Decimal("105.00")
        )


def test_product_schema_price_and_cost_validation():
    """Verify price must be strictly positive and cost non-negative."""
    # Zero price must fail
    with pytest.raises(ValidationError):
        ProductCreateRequest(
            id="p1",
            sku="SKU-1",
            name="P1",
            category="Cat",
            price_paise=0,
            cost_paise=100
        )

    # Negative cost must fail
    with pytest.raises(ValidationError):
        ProductCreateRequest(
            id="p1",
            sku="SKU-1",
            name="P1",
            category="Cat",
            price_paise=1000,
            cost_paise=-50
        )


def test_relationship_schema_affinity_bounds():
    """Verify affinity scores are bounded between 0.0 and 1.0."""
    req = RelationshipCreateRequest(
        primary_product_id="prod_1",
        related_product_id="prod_2",
        relationship_type="COMPLEMENTARY",
        affinity_score=Decimal("0.80")
    )
    assert req.affinity_score == Decimal("0.80")

    # Affinity > 1.0 must fail
    with pytest.raises(ValidationError):
        RelationshipCreateRequest(
            primary_product_id="prod_1",
            related_product_id="prod_2",
            relationship_type="COMPLEMENTARY",
            affinity_score=Decimal("1.50")
        )
