"""Unit Tests for Phase 10 Dashboard Projection and Read Services.

Tests:
- DashboardOverviewService
- DecisionViewService
- PolicyViewService
- ExperimentViewService
- LearningViewService
- ActivityViewService
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from domain.models import Base, Merchant, Product
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.dashboard.service import (
    DashboardOverviewService,
    DecisionViewService,
    PolicyViewService,
    ExperimentViewService,
    LearningViewService,
    ActivityViewService
)


@pytest.fixture
async def unit_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def seed_merchant(unit_db):
    m = Merchant(
        id="merch_unit_test",
        name="Unit Test Travel",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    p = Product(
        id="prod_unit_01",
        merchant_id=m.id,
        sku="SKU-UNIT-01",
        name="Unit Test Backpack",
        category="travel_backpack",
        price_paise=450000,
        cost_paise=250000,
        inventory_quantity=20,
        reserved_quantity=0,
        is_active=True,
        attributes={"weight_kg": 1.2}
    )
    unit_db.add_all([m, p])
    await unit_db.commit()
    return m, p


@pytest.mark.asyncio
async def test_dashboard_overview_service(unit_db, seed_merchant):
    m, _ = seed_merchant

    # Generate a canonical decision
    dec_req = CanonicalDecisionRequest(
        merchant_id=m.id,
        opportunity_id="opp_unit_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(unit_db, dec_req)

    # Fetch overview
    overview = await DashboardOverviewService.get_overview(unit_db, m.id)
    assert overview.merchant_id == m.id
    assert overview.merchant_name == "Unit Test Travel"
    assert overview.decision_count == 1
    assert overview.ai_buyer_opportunities_count == 1
    assert overview.runtime_status == "HEALTHY"
    assert len(overview.recent_decisions) == 1
    assert overview.recent_decisions[0].decision_id == envelope.decision_id


@pytest.mark.asyncio
async def test_decision_view_service(unit_db, seed_merchant):
    m, _ = seed_merchant

    dec_req = CanonicalDecisionRequest(
        merchant_id=m.id,
        opportunity_id="opp_unit_02",
        raw_prompt="waterproof laptop backpack"
    )
    envelope = await CanonicalDecisionRuntime.decide(unit_db, dec_req)

    # Execute
    exec_res = await DecisionExecutionBoundaryService.execute_decision(
        db=unit_db,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=m.id)
    )

    # Test list
    res_list = await DecisionViewService.list_decisions(unit_db, m.id, limit=10, offset=0)
    assert res_list.total >= 1
    assert any(d.decision_id == envelope.decision_id for d in res_list.items)

    # Test detail
    detail = await DecisionViewService.get_decision_detail(unit_db, envelope.decision_id, m.id)
    assert detail.decision_id == envelope.decision_id
    assert detail.opportunity_id == "opp_unit_02"
    assert detail.execution_id == exec_res.execution_id
    assert detail.buyer_offer.offer_price_paise == envelope.selected_policy.proposed_price_paise
    assert detail.merchant_evaluation.cogs_paise >= 0
    assert detail.merchant_evaluation.gross_margin_percent >= 0


@pytest.mark.asyncio
async def test_policy_view_service(unit_db, seed_merchant):
    m, _ = seed_merchant

    policies_dto = await PolicyViewService.get_policies(unit_db, m.id)
    assert policies_dto.merchant_id == m.id
    # Default versions should be accessible
    assert isinstance(policies_dto.versions, list)


@pytest.mark.asyncio
async def test_learning_view_service(unit_db, seed_merchant):
    m, _ = seed_merchant

    learning_dto = await LearningViewService.get_learning_center(unit_db, m.id)
    assert learning_dto.merchant_id == m.id
    assert learning_dto.model_metadata.dimension > 0
    assert learning_dto.model_metadata.model_version == "learning-model/v1"
    assert learning_dto.evidence_class == "TEST_MODE_OBSERVED"


@pytest.mark.asyncio
async def test_activity_view_service(unit_db, seed_merchant):
    m, _ = seed_merchant

    activity_dto = await ActivityViewService.list_activity(unit_db, m.id, limit=10, offset=0)
    assert activity_dto.total >= 0
    assert isinstance(activity_dto.items, list)
