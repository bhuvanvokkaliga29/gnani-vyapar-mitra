"""Context Determinism and Update Propagation Hardening Tests."""

import pytest
from httpx import AsyncClient
from decimal import Decimal


@pytest.mark.asyncio
async def test_repeated_context_calls_are_deterministic(client: AsyncClient):
    """Calling commerce-context multiple times without mutation produces identical semantics and ordering."""
    m_id = "merch_determ_test"
    await client.post("/api/v1/merchants", json={"id": m_id, "name": "Determinism Merchant"})

    # Add 3 products with different names/IDs to verify stable sorting
    for i in [3, 1, 2]:
        await client.post(
            f"/api/v1/merchants/{m_id}/products",
            json={
                "id": f"prod_det_{i}",
                "sku": f"SKU-DET-{i}",
                "name": f"Item {i}",
                "category": "Cat",
                "price_paise": 1000 * i,
                "cost_paise": 500 * i,
                "inventory_quantity": 10
            }
        )

    # Fetch context 5 consecutive times
    snapshots = []
    for _ in range(5):
        res = await client.get(f"/api/v1/merchants/{m_id}/commerce-context")
        assert res.status_code == 200
        data = res.json()
        # Exclude generated_at timestamp from byte-for-byte comparison
        data.pop("generated_at", None)
        snapshots.append(data)

    # Assert all snapshots are identical
    first = snapshots[0]
    for snap in snapshots[1:]:
        assert snap == first

    # Assert deterministic ordering of products by id.asc()
    product_ids = [p["id"] for p in first["products"]]
    assert product_ids == ["prod_det_1", "prod_det_2", "prod_det_3"]


@pytest.mark.asyncio
async def test_update_propagation_to_commerce_context(client: AsyncClient):
    """Verify that updating individual fields immediately propagates to commerce-context."""
    m_id = "merch_prop_test"
    await client.post("/api/v1/merchants", json={
        "id": m_id,
        "name": "Propagation Merchant",
        "minimum_margin_percent": 25.0
    })

    # 1. Create product (Price: 10000, Cost: 7000 -> Profit: 3000, Margin: 30.00%, Eligible: True)
    p_id = "prod_prop_item"
    await client.post(f"/api/v1/merchants/{m_id}/products", json={
        "id": p_id,
        "sku": "SKU-PROP-1",
        "name": "Prop Item",
        "category": "General",
        "price_paise": 10000,
        "cost_paise": 7000,
        "inventory_quantity": 20
    })

    ctx1 = (await client.get(f"/api/v1/merchants/{m_id}/commerce-context")).json()
    p1 = ctx1["products"][0]
    assert p1["gross_profit_paise"] == 3000
    assert p1["gross_margin_percent"] == "30.00"
    assert p1["is_eligible"] is True

    # 2. Update price to 20000 (Cost remains 7000 -> Profit: 13000, Margin: 65.00%)
    await client.patch(f"/api/v1/merchants/{m_id}/products/{p_id}", json={"price_paise": 20000})
    ctx2 = (await client.get(f"/api/v1/merchants/{m_id}/commerce-context")).json()
    p2 = ctx2["products"][0]
    assert p2["price_paise"] == 20000
    assert p2["gross_profit_paise"] == 13000
    assert p2["gross_margin_percent"] == "65.00"

    # 3. Update inventory to 0 -> Product becomes ineligible
    await client.patch(f"/api/v1/merchants/{m_id}/products/{p_id}", json={"inventory_quantity": 0})
    ctx3 = (await client.get(f"/api/v1/merchants/{m_id}/commerce-context")).json()
    p3 = ctx3["products"][0]
    assert p3["available_to_sell"] == 0
    assert p3["is_eligible"] is False
    assert "Insufficient inventory" in p3["ineligibility_reason"]

    # 4. Restock and update margin floor to 70% -> Product (margin 65%) becomes ineligible due to floor violation
    await client.patch(f"/api/v1/merchants/{m_id}/products/{p_id}", json={"inventory_quantity": 10})
    await client.put(f"/api/v1/merchants/{m_id}/constraints", json={"minimum_margin_percent": 70.0})
    ctx4 = (await client.get(f"/api/v1/merchants/{m_id}/commerce-context")).json()
    p4 = ctx4["products"][0]
    assert p4["is_eligible"] is False
    assert "below minimum required margin" in p4["ineligibility_reason"]
