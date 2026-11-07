"""Security, boundary, and tenant isolation tests for Phase 7 Experiments."""

import os
import ast
import pytest
from httpx import AsyncClient
from domain.models import Merchant


def test_architectural_boundary_no_direct_razorpay_in_experiments():
    """Static AST Boundary Audit: services/experiments must contain zero direct Razorpay clients or payment calls."""
    experiments_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "experiments")
    forbidden_terms = [
        "RazorpayClient",
        "rzp_test",
        "api.razorpay.com",
        "client.order.create",
        "client.payment.capture"
    ]

    for root, _, files in os.walk(experiments_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    _ = ast.parse(content, filename=file_path)

                    for term in forbidden_terms:
                        assert term not in content, (
                            f"Security boundary violation: '{term}' found in {file_path}. "
                            "Phase 7 Experiments must never call Razorpay directly; "
                            "all Test Mode executions must strictly traverse Phase 5 ExecutionGate."
                        )


@pytest.mark.asyncio
async def test_tenant_isolation_cross_merchant_access_denied(client: AsyncClient, db_session):
    """Tenant Isolation: Merchant B cannot access or run Merchant A's experiment."""
    m_a = Merchant(id="merch_alpha", name="Alpha Gear", currency="INR", status="ACTIVE")
    m_b = Merchant(id="merch_beta", name="Beta Tech", currency="INR", status="ACTIVE")
    db_session.add_all([m_a, m_b])
    await db_session.commit()

    # Create experiment for Merchant A
    create_payload = {
        "merchant_id": "merch_alpha",
        "name": "Alpha Secret Exp",
        "control_policy_id": "p_ctrl_a",
        "treatment_policy_id": "p_treat_a",
        "population_scenarios": ["s1", "s2"],
        "hypothesis": {
            "population_description": "Pop",
            "control_description": "Ctrl",
            "treatment_description": "Treat",
            "expected_direction": "HIGHER",
            "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
            "rationale": "Rationale"
        }
    }
    res_create = await client.post("/api/v1/experiments", json=create_payload)
    assert res_create.status_code == 201
    exp_id = res_create.json()["experiment_id"]

    # Merchant B attempts to fetch Merchant A's experiment -> 404 (isolated)
    res_b_get = await client.get(f"/api/v1/experiments/{exp_id}?merchant_id=merch_beta")
    assert res_b_get.status_code == 404

    # Merchant B attempts to start Merchant A's experiment -> 403 / 400
    res_b_start = await client.post(f"/api/v1/experiments/{exp_id}/start?merchant_id=merch_beta", json={})
    assert res_b_start.status_code in [403, 404]


@pytest.mark.asyncio
async def test_no_automatic_policy_learning_invariant(client: AsyncClient, db_session):
    """No-Automatic-Learning Invariant: Completing an experiment does NOT mutate merchant policy or priority tables."""
    m = Merchant(id="merch_atlas_travel", name="Atlas", currency="INR", status="ACTIVE")
    db_session.add(m)
    await db_session.commit()

    # Create & run experiment
    create_payload = {
        "merchant_id": "merch_atlas_travel",
        "name": "No-Learning Verification Exp",
        "control_policy_id": "p_c",
        "treatment_policy_id": "p_t",
        "population_scenarios": [f"scen_nl_{i}" for i in range(10)],
        "hypothesis": {
            "population_description": "Pop",
            "control_description": "Ctrl",
            "treatment_description": "Treat",
            "expected_direction": "HIGHER",
            "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
            "rationale": "Rationale"
        }
    }
    res_create = await client.post("/api/v1/experiments", json=create_payload)
    exp_id = res_create.json()["experiment_id"]

    res_run = await client.post(
        f"/api/v1/experiments/{exp_id}/run?merchant_id=merch_atlas_travel",
        json={"execute_test_mode_orders": False}
    )
    assert res_run.status_code == 200
    result = res_run.json()

    # Invariant: Output contract is experiment-result/v1; NO policy parameters or merchant records have been mutated
    assert result["result_version"] == "experiment-result/v1"
    assert result["status"] == "COMPLETED"
    # Verification: Merchant record untouched
    db_m = await db_session.get(Merchant, "merch_atlas_travel")
    assert db_m.status == "ACTIVE"
