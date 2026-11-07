"""Multi-Tenant Isolation Hardening Tests.

Verifies strict tenant segregation across catalog reads, product updates,
relationship definitions, constraints, and priorities.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_multi_tenant_complete_isolation(client: AsyncClient):
    """Setup Merchant A and Merchant B and verify complete isolation."""
    # 1. Register Merchant A and Merchant B
    m_a = "merch_iso_a"
    m_b = "merch_iso_b"

    await client.post("/api/v1/merchants", json={
        "id": m_a,
        "name": "Merchant Alpha",
        "minimum_margin_percent": 20.0,
        "maximum_discount_percent": 5.0
    })
    await client.post("/api/v1/merchants", json={
        "id": m_b,
        "name": "Merchant Beta",
        "minimum_margin_percent": 35.0,
        "maximum_discount_percent": 12.0
    })

    # 2. Add products to Merchant A
    p_a1 = {"id": "prod_a1", "sku": "SKU-A1", "name": "Alpha Item 1", "category": "Cat A", "price_paise": 10000, "cost_paise": 5000}
    p_a2 = {"id": "prod_a2", "sku": "SKU-A2", "name": "Alpha Item 2", "category": "Cat A", "price_paise": 20000, "cost_paise": 10000}
    await client.post(f"/api/v1/merchants/{m_a}/products", json=p_a1)
    await client.post(f"/api/v1/merchants/{m_a}/products", json=p_a2)

    # 3. Add products to Merchant B
    p_b1 = {"id": "prod_b1", "sku": "SKU-B1", "name": "Beta Item 1", "category": "Cat B", "price_paise": 15000, "cost_paise": 8000}
    p_b2 = {"id": "prod_b2", "sku": "SKU-B2", "name": "Beta Item 2", "category": "Cat B", "price_paise": 30000, "cost_paise": 12000}
    await client.post(f"/api/v1/merchants/{m_b}/products", json=p_b1)
    await client.post(f"/api/v1/merchants/{m_b}/products", json=p_b2)

    # 4. Context Read Isolation: A's context contains only A items, B contains only B
    ctx_a = (await client.get(f"/api/v1/merchants/{m_a}/commerce-context")).json()
    ctx_b = (await client.get(f"/api/v1/merchants/{m_b}/commerce-context")).json()

    a_ids = {p["id"] for p in ctx_a["products"]}
    b_ids = {p["id"] for p in ctx_b["products"]}

    assert a_ids == {"prod_a1", "prod_a2"}
    assert b_ids == {"prod_b1", "prod_b2"}
    assert a_ids.isdisjoint(b_ids)

    # 5. Product Modification Isolation: Merchant A cannot update Merchant B's product
    update_res = await client.patch(
        f"/api/v1/merchants/{m_a}/products/prod_b1",
        json={"price_paise": 99999}
    )
    assert update_res.status_code == 404

    # 6. Relationship Cross-Linking Isolation: Linking prod_a1 with prod_b1 must fail
    cross_rel = await client.post(
        f"/api/v1/merchants/{m_a}/relationships",
        json={
            "primary_product_id": "prod_a1",
            "related_product_id": "prod_b1",
            "relationship_type": "COMPLEMENTARY"
        }
    )
    assert cross_rel.status_code == 400
    assert "Cross-merchant" in cross_rel.json()["detail"]

    # 7. Constraint Isolation: Changing A's constraints does not affect B
    await client.put(
        f"/api/v1/merchants/{m_a}/constraints",
        json={"minimum_margin_percent": 45.0}
    )
    ctx_a_updated = (await client.get(f"/api/v1/merchants/{m_a}/commerce-context")).json()
    ctx_b_unchanged = (await client.get(f"/api/v1/merchants/{m_b}/commerce-context")).json()

    assert ctx_a_updated["constraints"]["minimum_margin_percent"] == "45.00"
    assert ctx_b_unchanged["constraints"]["minimum_margin_percent"] == "35.00"

    # 8. Priority Isolation: Changing A's priorities does not affect B
    await client.put(
        f"/api/v1/merchants/{m_a}/priorities",
        json={"priority_product_ids": ["prod_a1"]}
    )
    ctx_a_prio = (await client.get(f"/api/v1/merchants/{m_a}/commerce-context")).json()
    ctx_b_prio = (await client.get(f"/api/v1/merchants/{m_b}/commerce-context")).json()

    assert ctx_a_prio["priorities"]["priority_product_ids"] == ["prod_a1"]
    assert ctx_b_prio["priorities"]["priority_product_ids"] == []
