"""Phase 12.2 — Demo Environment & Deterministic Demo Dataset Integration Tests.
Razorpay AI Buildathon 2026 — Track 01

Validates:
1. Repeatable demo reset without duplicate accumulation
2. Completeness of the 8 required semantic records:
   - Successful commercial decision & payment capture
   - Payment failure (checkout abandonment)
   - NO_OFFER decision
   - Exploration decision
   - Learning observation (AppliedModelObservationRecord)
   - Candidate policy with insufficient evidence
   - Active baseline policy
   - Governance audit activity
3. Authoritative services exercised directly against persistent demo substrate
4. Tenant safety and strict cross-tenant boundary (Atlas vs Alpha)
5. Information hygiene (no live Razorpay keys, test mode markers intact)
6. Dashboard projection consistency against seeded demo state
7. Canonical buyer journey live execution through runtime pipeline
"""

import pytest
import os
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from domain.models import (
    Base,
    Merchant,
    Product,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    ExecutionRecord,
    Order,
    Payment,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
    AppliedModelObservationRecord,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    PolicyLifecycleAuditRecord,
    AuditEvent
)
from services.runtime.schemas import CanonicalDecisionRequest, DecisionMode
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest, ExecutionBoundaryStatus
from services.boundary.service import DecisionExecutionBoundaryService
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.schemas import PolicyPromotionRequest, PromotionStatus
from services.selection.ranking import CANONICAL_BASELINE_POLICY_ID
from services.dashboard.service import (
    DashboardOverviewService,
    PolicyViewService,
    LearningViewService
)
from scripts.run_demo_population import reset_demo_merchants, seed_demo_merchants

LIVE_DB_URL = "sqlite+aiosqlite:///./test.db"
live_engine = create_async_engine(LIVE_DB_URL, connect_args={"check_same_thread": False})
LiveSessionLocal = async_sessionmaker(bind=live_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def live_db():
    """Session connected to the authoritative persistent demo database."""
    async with live_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with LiveSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_demo_reset_repeatable_no_duplicates(db_session):
    """Verify that running demo reset and seed multiple times does not accumulate duplicate rows."""
    merchants = ["merch_atlas_travel", "merch_alpha"]

    # First reset & seed
    await reset_demo_merchants(db_session, merchants)
    await seed_demo_merchants(db_session)
    
    prod_cnt_1 = (await db_session.execute(
        select(func.count(Product.id)).where(Product.merchant_id == "merch_atlas_travel")
    )).scalar_one()
    pol_cnt_1 = (await db_session.execute(
        select(func.count(MerchantPolicyVersionRecord.id)).where(MerchantPolicyVersionRecord.merchant_id == "merch_atlas_travel")
    )).scalar_one()

    assert prod_cnt_1 == 5
    assert pol_cnt_1 == 2  # Baseline NO_OFFER + Candidate BUNDLE

    # Second reset & seed
    await reset_demo_merchants(db_session, merchants)
    await seed_demo_merchants(db_session)

    prod_cnt_2 = (await db_session.execute(
        select(func.count(Product.id)).where(Product.merchant_id == "merch_atlas_travel")
    )).scalar_one()
    pol_cnt_2 = (await db_session.execute(
        select(func.count(MerchantPolicyVersionRecord.id)).where(MerchantPolicyVersionRecord.merchant_id == "merch_atlas_travel")
    )).scalar_one()

    # Must be identical — zero duplicate accumulation
    assert prod_cnt_2 == prod_cnt_1
    assert pol_cnt_2 == pol_cnt_1


@pytest.mark.asyncio
async def test_demo_hero_dataset_semantic_completeness(live_db):
    """Verify the 8 required semantic records exist in the persistent demo state for Atlas Travel Gear."""
    m_id = "merch_atlas_travel"

    # A. Successful commercial decision & outcome (captured payment)
    paid_res = await live_db.execute(
        select(func.count(OutcomeFeedbackRecord.id)).where(
            and_(
                OutcomeFeedbackRecord.merchant_id == m_id,
                OutcomeFeedbackRecord.outcome_status == "PAYMENT_SUCCESS"
            )
        )
    )
    assert paid_res.scalar_one() >= 1, "Must have at least one successful commercial outcome"

    # B. Payment failure (checkout abandonment)
    fail_res = await live_db.execute(
        select(func.count(Payment.id)).where(
            and_(
                Payment.status == "failed"
            )
        )
    )
    assert fail_res.scalar_one() >= 1, "Must have at least one payment failure"

    # C. NO_OFFER decision
    no_offer_res = await live_db.execute(
        select(func.count(CanonicalDecisionRecord.id)).where(
            and_(
                CanonicalDecisionRecord.merchant_id == m_id,
                CanonicalDecisionRecord.selected_strategy_type == "NO_OFFER"
            )
        )
    )
    assert no_offer_res.scalar_one() >= 1, "Must have at least one NO_OFFER decision"

    # D. Exploration decision
    explore_res = await live_db.execute(
        select(func.count(CanonicalDecisionRecord.id)).where(
            and_(
                CanonicalDecisionRecord.merchant_id == m_id,
                CanonicalDecisionRecord.decision_mode == "EXPLORE"
            )
        )
    )
    assert explore_res.scalar_one() >= 1, "Must have at least one exploration decision"

    # E. Learning observation (LinUCB update applied)
    obs_res = await live_db.execute(
        select(func.count(AppliedModelObservationRecord.id)).where(
            AppliedModelObservationRecord.merchant_id == m_id
        )
    )
    assert obs_res.scalar_one() >= 1, "Must have at least one applied model observation"

    # F. Candidate policy with insufficient evidence
    cand_res = await live_db.execute(
        select(MerchantPolicyVersionRecord).where(
            and_(
                MerchantPolicyVersionRecord.merchant_id == m_id,
                MerchantPolicyVersionRecord.lifecycle_status == "CANDIDATE"
            )
        )
    )
    cand_policy = cand_res.scalar_one_or_none()
    assert cand_policy is not None, "Must have a candidate policy"
    assert cand_policy.policy_id == "cand_54256751"

    # G. Active baseline policy
    active_pol = await PolicyLifecycleService.get_active_policy(live_db, m_id)
    assert active_pol is not None
    assert active_pol.policy_id in (CANONICAL_BASELINE_POLICY_ID, "cand_base_no_offer")

    # H. Governance/audit activity
    gov_res = await live_db.execute(
        select(func.count(PolicyLifecycleAuditRecord.id)).where(
            PolicyLifecycleAuditRecord.merchant_id == m_id
        )
    )
    assert gov_res.scalar_one() >= 1, "Must have governance lifecycle audit activity"


@pytest.mark.asyncio
async def test_demo_candidate_policy_evidence_gating(live_db):
    """Verify that promoting the candidate policy without sufficient evidence is rejected."""
    m_id = "merch_atlas_travel"
    
    prom_req = PolicyPromotionRequest(
        merchant_id=m_id,
        candidate_policy_id="cand_54256751",
        candidate_policy_version="merchant-policy/v1",
        reason="Automated test of candidate promotion evidence gate"
    )
    prom_res = await PolicyLifecycleService.promote_policy(live_db, prom_req)

    # Invariant: PREDICTION ≠ PROMOTION, LEARNING ≠ PROMOTION, CANDIDATE ≠ ACTIVE
    assert prom_res.promotion_status == PromotionStatus.INSUFFICIENT_EVIDENCE
    assert prom_res.resulting_active_policy_id in (CANONICAL_BASELINE_POLICY_ID, "cand_base_no_offer")


@pytest.mark.asyncio
async def test_demo_tenant_isolation(live_db):
    """Verify that demo data strictly respects tenant boundary between Atlas and Alpha."""
    # 1. Atlas cannot see Alpha decisions
    atlas_decs = (await live_db.execute(
        select(func.count(CanonicalDecisionRecord.id)).where(CanonicalDecisionRecord.merchant_id == "merch_atlas_travel")
    )).scalar_one()
    alpha_decs = (await live_db.execute(
        select(func.count(CanonicalDecisionRecord.id)).where(CanonicalDecisionRecord.merchant_id == "merch_alpha")
    )).scalar_one()

    assert atlas_decs > 0
    assert alpha_decs > 0

    # Cross-query must return 0
    cross = (await live_db.execute(
        select(func.count(CanonicalDecisionRecord.id)).where(
            and_(
                CanonicalDecisionRecord.merchant_id == "merch_atlas_travel",
                CanonicalDecisionRecord.opportunity_id.like("%alpha%")
            )
        )
    )).scalar_one()
    assert cross == 0, "No cross-tenant opportunity IDs may leak into Atlas Travel Gear"


@pytest.mark.asyncio
async def test_demo_environment_security_and_information_hygiene():
    """Verify that demo environment strictly uses Test Mode and contains no production secrets."""
    # Ensure no live keys are configured
    live_key = os.getenv("RAZORPAY_LIVE_KEY_ID")
    assert not live_key, "Live Razorpay Key ID must not be set in demo environment"

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    assert "prod" not in db_url.lower(), "Production database must not be targeted"


@pytest.mark.asyncio
async def test_demo_dashboard_reads_seeded_state_accurately(live_db):
    """Verify that Dashboard service read models correctly reflect the persistent demo state."""
    m_id = "merch_atlas_travel"

    overview = await DashboardOverviewService.get_overview(live_db, m_id)
    assert overview.ai_buyer_opportunities_count >= 30
    assert overview.decision_count >= 30
    assert overview.paid_transactions_count >= 5
    assert overview.observed_contribution_paise > 0

    policies = await PolicyViewService.get_policies(live_db, m_id)
    assert policies.active_policy is not None
    assert policies.active_policy.policy_id in (CANONICAL_BASELINE_POLICY_ID, "cand_base_no_offer")
    assert len(policies.versions) >= 2

    # Verify candidate is marked promotion_criteria_satisfied=False
    cand_item = next((v for v in policies.versions if v.policy_id == "cand_54256751"), None)
    assert cand_item is not None
    assert cand_item.promotion_criteria_satisfied is False
    assert cand_item.lifecycle_status == "CANDIDATE"

    learning = await LearningViewService.get_learning_center(live_db, m_id)
    assert learning.health.valid_evidence_count >= 10
    assert learning.health.model_updates_count >= 10
    assert learning.model_metadata.observation_count >= 10
    assert learning.model_metadata.learning_status == "OPTIMIZING"


@pytest.mark.asyncio
async def test_canonical_buyer_journey_live_execution(db_session):
    """Execute the canonical demo buyer journey end-to-end through real authoritative services."""
    await seed_demo_merchants(db_session)

    m_id = "merch_atlas_travel"
    req_id = f"req_demo_{uuid.uuid4().hex[:6]}"
    opp_id = f"opp_demo_canonical_{uuid.uuid4().hex[:6]}"
    canonical_prompt = "I need a travel backpack for a business trip under 8000"

    # 1. Authoritative Decision Runtime
    dec_req = CanonicalDecisionRequest(
        merchant_id=m_id,
        request_id=req_id,
        opportunity_id=opp_id,
        raw_prompt=canonical_prompt
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    assert envelope.decision_id is not None
    assert envelope.merchant_id == m_id
    assert envelope.intent_summary.category == "travel_backpack"
    assert envelope.scores.predicted_contribution_paise >= 0
    assert envelope.scores.composite_ranking_score > 0

    # 2. Decision Execution Boundary
    exec_req = DecisionExecuteRequest(
        merchant_id=m_id,
        idempotency_key=f"idem_exec_{opp_id}"
    )
    exec_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=exec_req
    )
    assert exec_res.boundary_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED
    assert exec_res.order_id is not None
    assert exec_res.authorized_amount_paise > 0

    # 3. Simulate Test-Mode UPI Payment Capture
    pmt_id = f"pay_demo_{uuid.uuid4().hex[:8]}"
    payment = Payment(
        id=pmt_id,
        order_id=exec_res.order_id,
        amount_paise=exec_res.authorized_amount_paise,
        currency="INR",
        status="captured",
        method="upi",
        captured_at=datetime.now(timezone.utc)
    )
    db_session.add(payment)
    order = await db_session.get(Order, exec_res.order_id)
    order.status = "PAID"
    await db_session.commit()

    # 4. Authoritative Outcome Feedback & Learning
    out_req = OutcomeProcessRequest(
        merchant_id=m_id,
        execution_id=exec_res.execution_id,
        idempotency_key=f"idem_out_{exec_res.execution_id}"
    )
    out_res = await OutcomeFeedbackService.process_outcome(db_session, out_req)
    assert out_res.outcome_status.value == "PAYMENT_SUCCESS"
    assert out_res.evidence_id is not None
    assert out_res.memory_id is not None
    assert out_res.reward_contribution_paise > 0


@pytest.mark.asyncio
async def test_canonical_atlas_demo_fixture_and_fresh_evaluation(live_db: AsyncSession):
    """Verify that the seeded Atlas Travel Gear demo environment exhibits authentic expired state,
    and deterministically generates a fresh, admissible, non-NO_OFFER decision ready for checkout."""
    merchant_id = "merch_atlas_travel"

    # 1. Verify seeded historical expired fixture
    stmt = select(CanonicalDecisionRecord).where(
        and_(
            CanonicalDecisionRecord.merchant_id == merchant_id,
            CanonicalDecisionRecord.opportunity_id == "opp_probe_before"
        )
    )
    fixture_rec = (await live_db.execute(stmt)).scalar_one_or_none()
    assert fixture_rec is not None, "Seeded expired fixture 'opp_probe_before' must exist"
    
    # Verify it is older than 15 minutes (900 seconds TTL)
    now_utc = datetime.now(timezone.utc)
    rec_created = fixture_rec.created_at
    if rec_created.tzinfo is None:
        rec_created = rec_created.replace(tzinfo=timezone.utc)
    age_seconds = (now_utc - rec_created).total_seconds()
    assert age_seconds >= 900, f"Fixture opp_probe_before must be >= 15m old for realistic demo rehearsal, got {age_seconds}s"

    # 2. Verify fresh opportunity evaluation with canonical demo fallback
    fresh_req = CanonicalDecisionRequest(
        merchant_id=merchant_id,
        opportunity_id=f"opp_verify_fresh_{uuid.uuid4().hex[:8]}"
    )
    # Check that canonical demo prompt was resolved
    assert fresh_req.raw_prompt == "High quality travel backpack for weekend travel under 7500"

    fresh_env = await CanonicalDecisionRuntime.decide(live_db, fresh_req)
    assert fresh_env.decision_id is not None
    assert fresh_env.merchant_id == merchant_id
    
    # 3. Decision must be admissible, pending execution gate, and strictly NOT NO_OFFER
    assert fresh_env.safety_audit.status == "ADMISSIBLE"
    assert fresh_env.execution_status == "PENDING_EXECUTION_GATE"
    assert fresh_env.execution_authorized is False  # Phase 9.1 non-authorization invariant
    assert fresh_env.buyer_offer.strategy_type != "NO_OFFER", "Fresh Atlas demo opportunity must not default to NO_OFFER"
    assert fresh_env.buyer_offer.strategy_type in ("SINGLE_PRODUCT", "COMPLEMENTARY_BUNDLE")
    assert fresh_env.buyer_offer.offered_price_paise > 0
    assert "prod_travel_backpack" in fresh_env.buyer_offer.product_ids

    # 4. Verify Phase 9.2 Execution Boundary successfully creates test checkout order
    exec_req = DecisionExecuteRequest(
        merchant_id=merchant_id,
        idempotency_key=f"idem_verify_fresh_exec_{fresh_env.decision_id}"
    )
    exec_res = await DecisionExecutionBoundaryService.execute_decision(
        db=live_db,
        decision_id=fresh_env.decision_id,
        request=exec_req
    )
    assert exec_res.boundary_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED
    assert exec_res.execution_authorized is True
    assert exec_res.order_id is not None
    assert exec_res.razorpay_order_id is not None
    assert exec_res.razorpay_order_id.startswith("order_")
    assert exec_res.authorized_amount_paise == fresh_env.buyer_offer.offered_price_paise

    # Clean up verification artifacts to maintain authoritative demo population invariants
    from services.execution.concurrency import InventoryReservationManager
    from sqlalchemy import delete

    p5_rec = await live_db.get(ExecutionRecord, exec_res.phase5_execution_id) if exec_res.phase5_execution_id else None
    quantities = p5_rec.audit_metadata.get("quantities", {}) if p5_rec and p5_rec.audit_metadata else {}
    if not quantities:
        quantities = {pid: 1 for pid in fresh_env.buyer_offer.product_ids}
    await InventoryReservationManager().release_inventory(live_db, quantities)

    if exec_res.order_id:
        await live_db.execute(delete(Order).where(Order.id == exec_res.order_id))
    if exec_res.execution_id:
        await live_db.execute(delete(DecisionExecutionRecord).where(DecisionExecutionRecord.id == exec_res.execution_id))
    if exec_res.phase5_execution_id:
        await live_db.execute(delete(ExecutionRecord).where(ExecutionRecord.id == exec_res.phase5_execution_id))
    if fresh_env.decision_id:
        await live_db.execute(delete(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == fresh_env.decision_id))
    await live_db.commit()


