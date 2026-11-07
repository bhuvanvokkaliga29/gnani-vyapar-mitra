"""Integration tests for Merchant Commerce & Context API endpoints."""

import pytest
from httpx import AsyncClient
from decimal import Decimal


@pytest.mark.asyncio
async def test_create_and_get_merchant_flow(client: AsyncClient):
    """Full lifecycle: create merchant -> retrieve merchant profile."""
    req_data = {
        "id": "merch_integration_test",
        "name": "Integration Merchant Ltd",
        "currency": "INR",
        "business_objective": "MAXIMIZE_CONTRIBUTION",
        "minimum_margin_percent": 30.0,
        "maximum_discount_percent": 5.0,
        "target_aov_paise": 500000
    }

    # 1. Create merchant
    create_res = await client.post("/api/v1/merchants", json=req_data)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["id"] == "merch_integration_test"
    assert data["name"] == "Integration Merchant Ltd"
    assert Decimal(str(data["minimum_margin_percent"])) == Decimal("30.00")

    # 2. Retrieve merchant
    get_res = await client.get("/api/v1/merchants/merch_integration_test")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == "merch_integration_test"


@pytest.mark.asyncio
async def test_add_products_and_relationships_to_merchant(client: AsyncClient):
    """Create merchant -> add 2 products -> relate them -> verify context."""
    # 1. Create merchant
    m_id = "merch_catalog_test"
    await client.post("/api/v1/merchants", json={"id": m_id, "name": "Catalog Test Merchant"})

    # 2. Add Product A
    prod_a = {
        "id": "prod_cat_a",
        "sku": "SKU-CAT-A",
        "name": "Main Espresso Machine",
        "category": "Coffee Equipment",
        "price_paise": 4500000,  # ₹45,000
        "cost_paise": 2500000,   # ₹25,000
        "inventory_quantity": 10
    }
    res_a = await client.post(f"/api/v1/merchants/{m_id}/products", json=prod_a)
    assert res_a.status_code == 201
    assert res_a.json()["gross_profit_paise"] == 2000000
    assert res_a.json()["is_eligible"] is True

    # 3. Add Product B
    prod_b = {
        "id": "prod_cat_b",
        "sku": "SKU-CAT-B",
        "name": "Precision Coffee Tamper",
        "category": "Barista Tools",
        "price_paise": 250000,  # ₹2,500
        "cost_paise": 100000,   # ₹1,000
        "inventory_quantity": 50
    }
    res_b = await client.post(f"/api/v1/merchants/{m_id}/products", json=prod_b)
    assert res_b.status_code == 201

    # 4. Define Complementary Relationship
    rel_req = {
        "primary_product_id": "prod_cat_a",
        "related_product_id": "prod_cat_b",
        "relationship_type": "COMPLEMENTARY",
        "affinity_score": 0.95
    }
    res_rel = await client.post(f"/api/v1/merchants/{m_id}/relationships", json=rel_req)
    assert res_rel.status_code == 201
    assert res_rel.json()["relationship_type"] == "COMPLEMENTARY"

    # 5. Fetch Unified Commerce Context
    context_res = await client.get(f"/api/v1/merchants/{m_id}/commerce-context")
    assert context_res.status_code == 200
    ctx = context_res.json()

    assert ctx["merchant_id"] == m_id
    assert len(ctx["products"]) == 2
    assert len(ctx["relationships"]) == 1
    assert ctx["relationships"][0]["primary_product_id"] == "prod_cat_a"
    assert ctx["relationships"][0]["related_product_id"] == "prod_cat_b"
    assert ctx["constraints"]["minimum_margin_percent"] == "25.00"
