"""Integration tests for edge cases, multi-tenant isolation, and invalid relationship rejections."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duplicate_sku_rejection_per_merchant(client: AsyncClient):
    """Enforce SKU uniqueness within the same merchant tenant."""
    m_id = "merch_sku_test"
    await client.post("/api/v1/merchants", json={"id": m_id, "name": "SKU Test Merchant"})

    prod1 = {
        "id": "prod_sku_1",
        "sku": "UNIQUE-SKU-99",
        "name": "Product 1",
        "category": "General",
        "price_paise": 1000,
        "cost_paise": 500
    }
    res1 = await client.post(f"/api/v1/merchants/{m_id}/products", json=prod1)
    assert res1.status_code == 201

    # Attempting to add product 2 with identical SKU under same merchant must return 409 Conflict
    prod2 = {
        "id": "prod_sku_2",
        "sku": "UNIQUE-SKU-99",
        "name": "Product 2 with duplicate SKU",
        "category": "General",
        "price_paise": 2000,
        "cost_paise": 1000
    }
    res2 = await client.post(f"/api/v1/merchants/{m_id}/products", json=prod2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_same_sku_across_different_merchants_allowed(client: AsyncClient):
    """Different merchant tenants may use identical SKUs without collision."""
    await client.post("/api/v1/merchants", json={"id": "merch_tenant_a", "name": "Tenant A"})
    await client.post("/api/v1/merchants", json={"id": "merch_tenant_b", "name": "Tenant B"})

    p_a = {"id": "prod_ta_1", "sku": "COMMON-SKU", "name": "Item A", "category": "Cat", "price_paise": 1000, "cost_paise": 500}
    p_b = {"id": "prod_tb_1", "sku": "COMMON-SKU", "name": "Item B", "category": "Cat", "price_paise": 2000, "cost_paise": 800}

    res_a = await client.post("/api/v1/merchants/merch_tenant_a/products", json=p_a)
    res_b = await client.post("/api/v1/merchants/merch_tenant_b/products", json=p_b)

    assert res_a.status_code == 201
    assert res_b.status_code == 201


@pytest.mark.asyncio
async def test_cross_merchant_relationship_prohibited(client: AsyncClient):
    """Enforce that product relationships cannot bridge across different merchants."""
    await client.post("/api/v1/merchants", json={"id": "merch_cross_1", "name": "Cross 1"})
    await client.post("/api/v1/merchants", json={"id": "merch_cross_2", "name": "Cross 2"})

    p1 = {"id": "p_cross_1", "sku": "S1", "name": "P1", "category": "C", "price_paise": 100, "cost_paise": 50}
    p2 = {"id": "p_cross_2", "sku": "S2", "name": "P2", "category": "C", "price_paise": 200, "cost_paise": 100}

    await client.post("/api/v1/merchants/merch_cross_1/products", json=p1)
    await client.post("/api/v1/merchants/merch_cross_2/products", json=p2)

    # Attempt to link product from merch_cross_1 with product from merch_cross_2
    rel_req = {
        "primary_product_id": "p_cross_1",
        "related_product_id": "p_cross_2",
        "relationship_type": "COMPLEMENTARY"
    }
    res = await client.post("/api/v1/merchants/merch_cross_1/relationships", json=rel_req)
    assert res.status_code == 400
    assert "Cross-merchant" in res.json()["detail"]


@pytest.mark.asyncio
async def test_self_relationship_prohibited(client: AsyncClient):
    """A product cannot be related to itself."""
    m_id = "merch_self_rel"
    await client.post("/api/v1/merchants", json={"id": m_id, "name": "Self Rel"})
    p = {"id": "p_self_1", "sku": "SS1", "name": "PS1", "category": "C", "price_paise": 100, "cost_paise": 50}
    await client.post(f"/api/v1/merchants/{m_id}/products", json=p)

    rel_req = {
        "primary_product_id": "p_self_1",
        "related_product_id": "p_self_1",
        "relationship_type": "COMPLEMENTARY"
    }
    res = await client.post(f"/api/v1/merchants/{m_id}/relationships", json=rel_req)
    assert res.status_code == 400
    assert "relationship with itself" in res.json()["detail"]


@pytest.mark.asyncio
async def test_nonexistent_merchant_returns_404(client: AsyncClient):
    """Querying commerce context for unknown merchant returns 404."""
    res = await client.get("/api/v1/merchants/nonexistent_merchant_999/commerce-context")
    assert res.status_code == 404
