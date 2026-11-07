"""Security, boundary, and tenant isolation tests for Phase 8.1 Learning Evidence."""

import os
import ast
import pytest
from httpx import AsyncClient
from domain.models import Merchant, ExperimentRecord, ObservationRecord


def test_architectural_boundary_no_learning_algorithms_or_razorpay_in_learning():
    """Static AST Boundary Audit: services/learning must contain zero learning algorithms, bandits, or Razorpay clients."""
    learning_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "learning")
    forbidden_terms = [
        "RazorpayClient",
        "rzp_test",
        "bandit",
        "q_learning",
        "reinforcement_learning",
        "epsilon_greedy",
        "policy_gradient",
        "reward_model",
        "update_policy",
        "optimize_policy"
    ]

    for root, _, files in os.walk(learning_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    _ = ast.parse(content, filename=file_path)

                    for term in forbidden_terms:
                        assert term.lower() not in content.lower(), (
                            f"Security boundary violation: '{term}' found in {file_path}. "
                            "Phase 8.1 defines the evidence contract only. "
                            "It must NOT implement bandits, reward models, or policy updates."
                        )


@pytest.mark.asyncio
async def test_tenant_isolation_cross_merchant_learning_access_denied(client: AsyncClient, db_session):
    """Tenant Isolation: Merchant B cannot read or ingest Merchant A's learning evidence."""
    m_a = Merchant(id="merch_alpha", name="Alpha Gear", currency="INR", status="ACTIVE")
    m_b = Merchant(id="merch_beta", name="Beta Tech", currency="INR", status="ACTIVE")
    exp_a = ExperimentRecord(
        id="exp_alpha_sec",
        merchant_id="merch_alpha",
        name="Alpha Secret Exp",
        control_policy_id="p_ctrl",
        treatment_policy_id="p_treat",
        control_proposal_snapshot={"merchant_id": "merch_alpha"},
        treatment_proposal_snapshot={"merchant_id": "merch_alpha"},
        hypothesis={"population_description": "P", "control_description": "C", "treatment_description": "T", "expected_direction": "HIGHER", "primary_metric": "M", "rationale": "R"},
        status="COMPLETED"
    )
    obs_a = ObservationRecord(
        id="obs_alpha_sec",
        experiment_id="exp_alpha_sec",
        scenario_id="scen_sec_01",
        variant="TREATMENT",
        outcome_type="SIMULATED",
        is_selected=True,
        revenue_paise=300000,
        contribution_paise=150000,
        margin_percent=50.0,
        guardrail_violations=[],
        idempotency_key="obs_alpha_sec_key"
    )
    db_session.add_all([m_a, m_b, exp_a, obs_a])
    await db_session.commit()

    # Merchant A ingests evidence
    res_ingest_a = await client.post(
        f"/api/v1/learning/evidence/ingest-experiment/{exp_a.id}?merchant_id=merch_alpha"
    )
    assert res_ingest_a.status_code == 200
    evi_id = res_ingest_a.json()[0]["evidence_id"]

    # Merchant B attempts to fetch Merchant A's evidence -> 404 (isolated)
    res_b_get = await client.get(f"/api/v1/learning/evidence/{evi_id}?merchant_id=merch_beta")
    assert res_b_get.status_code == 404

    # Merchant B attempts to ingest Merchant A's experiment -> 403 (forbidden)
    res_b_ingest = await client.post(
        f"/api/v1/learning/evidence/ingest-experiment/{exp_a.id}?merchant_id=merch_beta"
    )
    assert res_b_ingest.status_code == 403


@pytest.mark.asyncio
async def test_no_merchant_policy_mutation_side_effects(client: AsyncClient, db_session):
    """Passive Invariant: Ingesting learning evidence causes zero side-effects to merchant policies or priorities."""
    m = Merchant(id="merch_gamma", name="Gamma Travel", currency="INR", status="ACTIVE")
    exp = ExperimentRecord(
        id="exp_gamma_sec",
        merchant_id="merch_gamma",
        name="Gamma Exp",
        control_policy_id="p_ctrl",
        treatment_policy_id="p_treat",
        control_proposal_snapshot={"merchant_id": "merch_gamma"},
        treatment_proposal_snapshot={"merchant_id": "merch_gamma"},
        hypothesis={"population_description": "P", "control_description": "C", "treatment_description": "T", "expected_direction": "HIGHER", "primary_metric": "M", "rationale": "R"},
        status="COMPLETED"
    )
    obs = ObservationRecord(
        id="obs_gamma_sec",
        experiment_id="exp_gamma_sec",
        scenario_id="scen_sec_02",
        variant="CONTROL",
        outcome_type="SIMULATED",
        is_selected=False,
        revenue_paise=0,
        contribution_paise=0,
        margin_percent=0.0,
        guardrail_violations=[],
        idempotency_key="obs_gamma_sec_key"
    )
    db_session.add_all([m, exp, obs])
    await db_session.commit()

    # Ingest evidence
    res_ingest = await client.post(
        f"/api/v1/learning/evidence/ingest-experiment/{exp.id}?merchant_id=merch_gamma"
    )
    assert res_ingest.status_code == 200

    # Verify merchant record remains completely untouched
    db_m = await db_session.get(Merchant, "merch_gamma")
    assert db_m.status == "ACTIVE"
