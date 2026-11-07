"""Integration Tests for Phase 9.1 Canonical Decision Runtime.

Contract: canonical-decision/v1
Verifies complete end-to-end execution, idempotency, persistence, and FastAPI endpoints.
"""

import pytest
from httpx import AsyncClient

from domain.models import Merchant, Product, CanonicalDecisionRecord
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    BudgetType,
    AttributeRequirement,
    OperatorType,
    ConfidenceLevel
)
from services.runtime.schemas import (
    CANONICAL_DECISION_SCHEMA_VERSION,
    CanonicalDecisionRequest,
    DecisionEnvelope
)
from services.runtime.service import CanonicalDecisionRuntime


@pytest.fixture
async def seed_runtime_merchant(db_session):
    """Seed active merchant with product catalog for runtime testing."""
    merchant = Merchant(
        id="merch_runtime_01",
        name="Runtime Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=15.0,
        maximum_discount_percent=25.0,
        target_aov_paise=500000
    )
    p1 = Product(
        id="prod_rt_pack_1",
        merchant_id=merchant.id,
        name="Voyager Pro Backpack",
        sku="SKU-RT-01",
        category="travel_backpack",
        price_paise=450000,
        cost_paise=250000,
        inventory_quantity=20,
        attributes={"laptop_size": 16.0, "water_resistant": True},
        is_active=True
    )
    p2 = Product(
        id="prod_rt_pack_2",
        merchant_id=merchant.id,
        name="Urban Commuter Pack",
        sku="SKU-RT-02",
        category="travel_backpack",
        price_paise=350000,
        cost_paise=180000,
        inventory_quantity=15,
        attributes={"laptop_size": 14.0, "water_resistant": False},
        is_active=True
    )
    db_session.add_all([merchant, p1, p2])
    await db_session.commit()
    await db_session.refresh(merchant)
    return merchant


@pytest.mark.asyncio
async def test_end_to_end_decision_with_raw_prompt(db_session, seed_runtime_merchant):
    """Pipeline runs from raw natural language buyer text to typed DecisionEnvelope."""
    merchant = seed_runtime_merchant
    req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_rt_test_001",
        raw_prompt="I need a travel backpack under 5000 with 15.6 inch laptop compartment"
    )

    envelope = await CanonicalDecisionRuntime.decide(db_session, req)

    # 1. Structural Verifications
    assert isinstance(envelope, DecisionEnvelope)
    assert envelope.decision_version == CANONICAL_DECISION_SCHEMA_VERSION
    assert envelope.merchant_id == merchant.id
    assert envelope.opportunity_id == "opp_rt_test_001"
    assert envelope.decision_id.startswith("dec_")

    # 2. Intent Summary & Context Key
    assert envelope.intent_summary.category == "travel_backpack"
    assert envelope.intent_summary.budget_paise == 500000
    assert "travel_backpack" in envelope.buyer_context_key

    # 3. Selected Policy & Economics
    assert envelope.selected_policy.candidate_id is not None
    assert envelope.selected_policy.proposed_price_paise > 0
    assert envelope.selected_policy.gross_profit_paise >= 0
    assert envelope.selected_policy.gross_margin_percent >= merchant.minimum_margin_percent

    # 4. Mode and Rationale
    assert envelope.decision_mode.value in ("EXPLOIT", "EXPLORE")
    assert envelope.decision_reason is not None

    # 5. Safety Audit
    assert envelope.safety_audit.status == "ADMISSIBLE"
    assert envelope.safety_audit.is_admissible is True

    # 6. Trace
    assert envelope.trace.total_latency_ms > 0
    assert envelope.trace.candidates_generated_count >= 1


@pytest.mark.asyncio
async def test_end_to_end_decision_with_structured_intent(db_session, seed_runtime_merchant):
    """Pipeline accepts strongly-typed BuyerIntent directly."""
    merchant = seed_runtime_merchant
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(amount_paise=600000, currency="INR", budget_type=BudgetType.MAX),
        requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6)],
        confidence=ConfidenceLevel.HIGH
    )
    req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_rt_test_002",
        buyer_intent=intent
    )

    envelope = await CanonicalDecisionRuntime.decide(db_session, req)
    assert envelope.intent_summary.category == "travel_backpack"
    assert envelope.intent_summary.budget_paise == 600000
    assert envelope.safety_audit.is_admissible is True


@pytest.mark.asyncio
async def test_idempotent_decision_execution(db_session, seed_runtime_merchant):
    """Repeated execution with identical (merchant_id, opportunity_id) returns cached envelope."""
    merchant = seed_runtime_merchant
    req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_rt_idemp_01",
        raw_prompt="travel backpack under 5000"
    )

    envelope_1 = await CanonicalDecisionRuntime.decide(db_session, req)
    envelope_2 = await CanonicalDecisionRuntime.decide(db_session, req)

    # Identical decision ID and timestamp
    assert envelope_1.decision_id == envelope_2.decision_id
    assert envelope_1.selected_policy.candidate_id == envelope_2.selected_policy.candidate_id
    assert envelope_1.selected_policy.proposed_price_paise == envelope_2.selected_policy.proposed_price_paise


@pytest.mark.asyncio
async def test_fastapi_canonical_decision_endpoints(client: AsyncClient, seed_runtime_merchant):
    """FastAPI endpoints POST /api/v1/decisions/evaluate and GET /api/v1/decisions/{id}."""
    merchant = seed_runtime_merchant
    payload = {
        "merchant_id": merchant.id,
        "opportunity_id": "opp_api_test_01",
        "raw_prompt": "travel backpack under 5000 with 15.6 inch laptop compartment"
    }

    # 1. POST Evaluate
    post_resp = await client.post("/api/v1/decisions/evaluate", json=payload)
    assert post_resp.status_code == 200, post_resp.text
    envelope_data = post_resp.json()
    assert envelope_data["decision_version"] == CANONICAL_DECISION_SCHEMA_VERSION
    decision_id = envelope_data["decision_id"]

    # 2. GET Decision
    get_resp = await client.get(f"/api/v1/decisions/{decision_id}?merchant_id={merchant.id}")
    assert get_resp.status_code == 200, get_resp.text
    retrieved = get_resp.json()
    assert retrieved["decision_id"] == decision_id
    assert retrieved["opportunity_id"] == "opp_api_test_01"
