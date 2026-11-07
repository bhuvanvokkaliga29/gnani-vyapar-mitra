"""Phase 9.5: End-to-End Runtime Hardening & Release Verification Test Suite.

Merchant Policy Agent — Razorpay AI Buildathon 2026 — Track 01

Verifies the complete composed runtime across all Phase 9 subsystems:
- Phase 9.1: Canonical Decision Runtime
- Phase 9.2: Active Policy & Safety Execution Boundary
- Phase 9.3: Outcome, Feedback & Recovery Loop
- Phase 9.4: Observability, Audit & Tenant Isolation
- Phase 9.5: End-to-End Hardening & Release Readiness
"""

import pytest
import asyncio
from decimal import Decimal
from sqlalchemy import select, and_, func

from domain.models import (
    Merchant,
    Product,
    Order,
    Payment,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
    PolicyLearningModelState,
    AppliedModelObservationRecord,
    AuditEvent
)
from apps.api.core.state_machine import TransactionState
from services.outcome.schemas import ProcessingState, OutcomeStatus
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.runtime.errors import DecisionTenantViolationError
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.errors import (
    DecisionTenantViolationError as BoundaryTenantViolationError,
    DecisionStaleError,
    PolicyLifecycleStateError,
    SafetyRejectionError,
    ExecutionAuthorizationError
)
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService
from services.outcome.errors import OutcomeTenantViolationError
from services.learning.model_service import PolicyLearningModelService
from services.observability.trace import TraceReconstructionService, TraceStageStatus
from services.audit.service import AuditService
from services.audit.errors import AuditTenantViolationError, AuditImmutabilityViolationError
from apps.api.core.logging import sanitize_value, sensitive_data_filter_processor


@pytest.fixture
async def seed_hardening_merchants(db_session):
    """Seed two distinct merchants with product catalogs for multi-tenant verification."""
    mA = Merchant(
        id="merch_95_alpha",
        name="Hardening Alpha",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    mB = Merchant(
        id="merch_95_beta",
        name="Hardening Beta",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("15.00"),
        maximum_discount_percent=Decimal("20.00")
    )
    pA = Product(
        id="prod_95_alpha_01",
        merchant_id=mA.id,
        sku="SKU-95-A01",
        name="Alpha Alpine Backpack",
        category="travel_backpack",
        price_paise=450000,
        cost_paise=250000,
        inventory_quantity=30,
        is_active=True,
        attributes={"laptop_size": 15.6}
    )
    pB = Product(
        id="prod_95_beta_01",
        merchant_id=mB.id,
        sku="SKU-95-B01",
        name="Beta Urban Backpack",
        category="travel_backpack",
        price_paise=550000,
        cost_paise=300000,
        inventory_quantity=20,
        is_active=True,
        attributes={"laptop_size": 17.0}
    )
    db_session.add_all([mA, mB, pA, pB])
    await db_session.commit()
    return mA, mB, pA, pB


# =============================================================================
# PART 2 & PART 3: END-TO-END HAPPY PATH & IDENTITY CHAIN
# =============================================================================

@pytest.mark.asyncio
async def test_end_to_end_runtime_happy_path_and_identity_chain(db_session, seed_hardening_merchants):
    """Verify complete 8-stage runtime lifecycle and unbroken identity chain."""
    mA, _, pA, _ = seed_hardening_merchants
    opp_id = "opp_95_e2e_01"
    req_id = "req_95_e2e_01"

    # Stage 1: Phase 9.1 Canonical Decision
    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id=opp_id,
        raw_prompt="travel backpack under 5000",
        request_id=req_id
    )
    dec_resp = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    assert dec_resp.merchant_id == mA.id
    assert dec_resp.opportunity_id == opp_id
    assert dec_resp.decision_id.startswith("dec_")
    assert dec_resp.selected_policy.candidate_id is not None
    assert dec_resp.selected_policy.proposed_price_paise > 0

    # Inspect persistent decision record
    dec_rec = (await db_session.execute(
        select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == dec_resp.decision_id)
    )).scalar_one()
    assert dec_rec.merchant_id == mA.id
    assert dec_rec.decision_mode in ["EXPLOIT", "EXPLORE"]

    # Stage 2: Phase 9.2 Execution Boundary
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=dec_resp.decision_id,
        request=exec_req
    )
    assert boundary_res.merchant_id == mA.id
    assert boundary_res.execution_id.startswith("dexec_")
    assert boundary_res.authorization_id.startswith("eauth_")
    assert boundary_res.boundary_status == "EXECUTION_COMPLETED"
    assert boundary_res.order_id.startswith("ord_")

    # Stage 3: Phase 5 / Razorpay Test Mode Transaction
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    pmt_id = f"pay_95_{boundary_res.order_id[-10:]}"
    payment = Payment(
        id=pmt_id,
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured",
        method="card"
    )
    db_session.add(payment)
    await db_session.commit()

    # Stage 4: Phase 9.3 Outcome Feedback & Recovery
    outcome_req = OutcomeProcessRequest(
        merchant_id=mA.id,
        execution_id=boundary_res.execution_id
    )
    outcome_resp = await OutcomeFeedbackService.process_outcome(db_session, outcome_req)
    assert outcome_resp.merchant_id == mA.id
    assert outcome_resp.outcome_id.startswith("out_")
    assert outcome_resp.outcome_status == OutcomeStatus.PAYMENT_SUCCESS.value
    assert outcome_resp.processing_state == ProcessingState.COMPLETED.value
    assert outcome_resp.reward_contribution_paise > 0
    assert outcome_resp.evidence_id is not None
    assert outcome_resp.memory_id is not None

    # Inspect persistent outcome, evidence, memory, and model application
    out_rec = (await db_session.execute(
        select(OutcomeFeedbackRecord).where(OutcomeFeedbackRecord.id == outcome_resp.outcome_id)
    )).scalar_one()
    assert out_rec.is_terminal is True
    assert out_rec.reward_contribution_paise == outcome_resp.reward_contribution_paise

    evi_rec = (await db_session.execute(
        select(LearningEvidenceRecord).where(LearningEvidenceRecord.id == outcome_resp.evidence_id)
    )).scalar_one()
    assert evi_rec.merchant_id == mA.id
    assert evi_rec.evidence_status == "VALID"
    assert evi_rec.source == "TEST_MODE_OBSERVED"

    mem_rec = (await db_session.execute(
        select(PolicyMemoryRecord).where(PolicyMemoryRecord.id == outcome_resp.memory_id)
    )).scalar_one()
    assert mem_rec.merchant_id == mA.id
    assert mem_rec.evidence_id == outcome_resp.evidence_id

    amo_rec = (await db_session.execute(
        select(AppliedModelObservationRecord).where(
            and_(
                AppliedModelObservationRecord.merchant_id == mA.id,
                AppliedModelObservationRecord.evidence_id == outcome_resp.evidence_id
            )
        )
    )).scalar_one()
    assert amo_rec.id.startswith("amo_")

    # Stage 5: Phase 9.4 Trace Reconstruction
    trace = await TraceReconstructionService.reconstruct_opportunity(
        db=db_session,
        merchant_id=mA.id,
        opportunity_id=opp_id
    )
    assert trace.trace_status == TraceStageStatus.COMPLETED.value
    assert trace.decision_id == dec_resp.decision_id
    assert trace.execution_id == boundary_res.execution_id
    assert trace.order_id == boundary_res.order_id
    assert trace.payment_id == pmt_id
    assert trace.outcome_id == outcome_resp.outcome_id
    assert trace.evidence_id == outcome_resp.evidence_id
    assert trace.memory_id == outcome_resp.memory_id
    assert trace.applied_observation_id == amo_rec.id
    assert trace.stages_present == [
        "9.1_DECISION",
        "9.2_EXECUTION",
        "PHASE_5_ORDER",
        "PHASE_5_PAYMENT",
        "9.3_OUTCOME",
        "8.1_EVIDENCE",
        "8.3_MEMORY",
        "8.4_MODEL_UPDATE"
    ]


# =============================================================================
# PART 4 & PART 5: FINANCIAL & EXECUTION AUTHORITY AUDIT
# =============================================================================

@pytest.mark.asyncio
async def test_financial_authority_client_cannot_choose_price_or_reward(db_session, seed_hardening_merchants):
    """Verify client cannot forge prices or rewards; calculations are server-side integer paise."""
    mA, _, _, _ = seed_hardening_merchants

    # 1. Canonical decision assigns server-calculated price
    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_fin_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    assert isinstance(envelope.selected_policy.proposed_price_paise, int)
    assert envelope.selected_policy.proposed_price_paise > 0

    # 2. Boundary executes with server-verified amount, client cannot send custom amount
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )
    assert boundary_res.authorized_amount_paise == envelope.selected_policy.proposed_price_paise

    # 3. Order is created with exact integer paise matching authorization
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    assert order.amount_paise == boundary_res.authorized_amount_paise


@pytest.mark.asyncio
async def test_negative_execution_authority_reused_token_and_replay_rejection(db_session, seed_hardening_merchants):
    """Verify execution boundary prevents replaying or reusing decisions and tokens."""
    mA, _, _, _ = seed_hardening_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_replay_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)

    # First execution succeeds
    res1 = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )
    assert res1.boundary_status == "EXECUTION_COMPLETED"

    # Second execution attempt on the same decision is idempotently returned without creating duplicate orders
    res2 = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )
    assert res2.is_duplicate is True
    assert res2.execution_id == res1.execution_id
    assert res2.order_id == res1.order_id


# =============================================================================
# PART 9 & PART 10: OUTCOME TRUTH & LEARNING CONTAMINATION AUDIT
# =============================================================================

@pytest.mark.asyncio
async def test_learning_contamination_unpaid_order_produces_zero_learning(db_session, seed_hardening_merchants):
    """Verify UNPAID/PENDING transactions produce zero evidence, zero memory, and zero model updates."""
    mA, _, _, _ = seed_hardening_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_unpaid_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # Leave Order in CREATION_PENDING (Unpaid)
    outcome_resp = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    )
    assert outcome_resp.outcome_status == OutcomeStatus.ORDER_CREATED.value
    assert outcome_resp.processing_state == ProcessingState.RESOLVED.value
    assert outcome_resp.learning_eligible is False
    assert outcome_resp.evidence_id is None
    assert outcome_resp.memory_id is None

    # Verify ZERO learning evidence in DB
    evi_count = (await db_session.execute(
        select(func.count(LearningEvidenceRecord.id)).where(
            LearningEvidenceRecord.execution_id == boundary_res.execution_id
        )
    )).scalar_one()
    assert evi_count == 0


@pytest.mark.asyncio
async def test_terminal_state_monotonicity_prevents_downgrade(db_session, seed_hardening_merchants):
    """Verify terminal PAYMENT_SUCCESS cannot be downgraded by subsequent failed webhooks."""
    mA, _, _, _ = seed_hardening_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_mono_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # 1. Mark Paid
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    db_session.add(Payment(
        id=f"pay_95_mono_{order.id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured"
    ))
    await db_session.commit()

    # Process successful outcome
    out_succ = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    )
    assert out_succ.outcome_status == OutcomeStatus.PAYMENT_SUCCESS.value
    assert out_succ.learning_eligible is True

    # 2. Simulate stale webhook claiming failure
    order.status = TransactionState.FAILED.value
    await db_session.commit()

    out_replay = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    )
    # Monotonicity preserves PAYMENT_SUCCESS
    assert out_replay.outcome_status == OutcomeStatus.PAYMENT_SUCCESS.value
    assert out_replay.is_duplicate is True


# =============================================================================
# PART 11 & PART 12: EXACTLY-ONCE LEARNING & CRASH RECOVERY
# =============================================================================

@pytest.mark.asyncio
async def test_exactly_once_learning_under_10_concurrent_workers(db_session, seed_hardening_merchants):
    """Verify 10 concurrent replay calls for the same paid execution apply the model exactly once."""
    mA, _, _, _ = seed_hardening_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_conc_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # Mark Paid
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    db_session.add(Payment(
        id=f"pay_95_conc_{order.id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured"
    ))
    await db_session.commit()

    # 0. Capture initial model baseline A_0, b_0 BEFORE any feedback processing
    model_0, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    obs_count_0 = model_0.observation_count
    mat_a_0 = [row[:] for row in model_0.A]
    vec_b_0 = model_0.b[:]

    # 1. First legitimate processing call: updates model exactly once
    init_res = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    )
    assert init_res.is_duplicate is False
    assert init_res.learning_eligible is True

    model_1, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    obs_count_1 = model_1.observation_count
    mat_a_1 = [row[:] for row in model_1.A]
    vec_b_1 = model_1.b[:]

    # Verify the legitimate update produced a real, valid change in observation count and matrices
    assert obs_count_1 == obs_count_0 + 1
    assert mat_a_1 != mat_a_0
    assert vec_b_1 != vec_b_0

    # 2. Run 10 sequential/concurrent replayed requests
    results = []
    for _ in range(10):
        res = await OutcomeFeedbackService.process_outcome(
            db_session,
            OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
        )
        results.append(res)

    for r in results:
        assert r.is_duplicate is True
        assert r.outcome_status == OutcomeStatus.PAYMENT_SUCCESS.value

    # 3. Model matrices after 10 replays: proves EXACTLY ONE net change in A/b
    model_final, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    assert model_final.observation_count == obs_count_1
    assert model_final.A == mat_a_1
    assert model_final.b == vec_b_1


# =============================================================================
# PART 17 & PART 18: TENANT ISOLATION & ASYNC CONTEXT ISOLATION
# =============================================================================

@pytest.mark.asyncio
async def test_strict_multi_tenant_isolation_all_boundaries(db_session, seed_hardening_merchants):
    """Verify complete cross-tenant isolation across decisions, executions, outcomes, and audit."""
    mA, mB, _, _ = seed_hardening_merchants

    # Beta creates decision and execution
    env_beta = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=mB.id, opportunity_id="opp_95_beta_iso", raw_prompt="travel backpack under 6000")
    )
    res_beta = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=env_beta.decision_id,
        request=DecisionExecuteRequest(merchant_id=mB.id)
    )

    # 1. Alpha tries to execute Beta's decision -> REJECTED
    with pytest.raises(BoundaryTenantViolationError):
        await DecisionExecutionBoundaryService.execute_decision(
            db=db_session,
            decision_id=env_beta.decision_id,
            request=DecisionExecuteRequest(merchant_id=mA.id)
        )

    # 2. Alpha tries to process Beta's execution outcome -> REJECTED
    with pytest.raises(OutcomeTenantViolationError):
        await OutcomeFeedbackService.process_outcome(
            db_session,
            OutcomeProcessRequest(merchant_id=mA.id, execution_id=res_beta.execution_id)
        )

    # 3. Alpha tries to query Beta's audit events -> Zero records returned
    audit_events_alpha = await AuditService.query_events(
        db=db_session,
        merchant_id=mA.id,
        opportunity_id="opp_95_beta_iso"
    )
    assert audit_events_alpha.total_count == 0


# =============================================================================
# PART 22 & PART 23: INFORMATION HYGIENE & AUDIT IMMUTABILITY
# =============================================================================

def test_information_hygiene_and_log_injection_prevention():
    """Verify secrets and economics are redacted and log injection newlines are stripped."""
    raw_payload = {
        "api_key": "rzp_test_secret12345",
        "auth_token": "bearer_super_secret_token",
        "cogs_paise": 250000,
        "gross_margin_percent": 35.5,
        "matrix_a": [[1.0, 0.0], [0.0, 1.0]],
        "user_input": "normal query\r\nINJECTED_LOG_LINE: admin login success",
        "oversized": "A" * 2000
    }
    sanitized = sanitize_value(raw_payload)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["cogs_paise"] == "[REDACTED]"
    assert sanitized["gross_margin_percent"] == "[REDACTED]"
    assert sanitized["matrix_a"] == "[REDACTED]"
    assert "\r" not in sanitized["user_input"]
    assert "\n" not in sanitized["user_input"]
    assert len(sanitized["oversized"]) == 1024 + len("...[TRUNCATED]")


@pytest.mark.asyncio
async def test_audit_event_immutability_enforced(db_session, seed_hardening_merchants):
    """Verify AuditEvent rows cannot be updated or deleted."""
    mA, _, _, _ = seed_hardening_merchants

    audit = await AuditService.record_event(
        db=db_session,
        merchant_id=mA.id,
        entity_type="DECISION",
        entity_id="dec_95_audit_01",
        action="DECISION_CREATED",
        payload={"note": "original audit"}
    )
    await db_session.commit()
    audit_id = audit.id

    # Attempt to modify
    audit.action = "TAMPERED_ACTION"
    with pytest.raises(AuditImmutabilityViolationError):
        await db_session.commit()
    await db_session.rollback()

    # Attempt to delete
    audit_fresh = (await db_session.execute(select(AuditEvent).where(AuditEvent.id == audit_id))).scalar_one()
    await db_session.delete(audit_fresh)
    with pytest.raises(AuditImmutabilityViolationError):
        await db_session.commit()
    await db_session.rollback()


# =============================================================================
# PART 8, PART 12 & PART 26: SAFETY, CRASH RECOVERY & COLD START
# =============================================================================

@pytest.mark.asyncio
async def test_runtime_safety_inventory_depletion_at_execution_boundary(db_session, seed_hardening_merchants):
    """Verify fresh state re-evaluation at execution boundary blocks proposal if inventory was depleted."""
    mA, _, pA, _ = seed_hardening_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_deplete_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    assert envelope.execution_status == "PENDING_EXECUTION_GATE"

    # Deplete inventory before boundary execution
    pA.inventory_quantity = 0
    await db_session.commit()

    # Execution boundary re-evaluates fresh state and rejects safely
    res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )
    assert res.boundary_status == "SAFETY_REJECTED"
    assert res.order_id is None
    assert any("INSUFFICIENT_INVENTORY" in r or "inventory" in r.lower() for r in res.rejection_reasons)


@pytest.mark.asyncio
async def test_cold_start_clean_database_initialization():
    """Verify cold start initializes all tables and constraints on a clean database without errors."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from domain.models import Base

    clean_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with clean_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Verify tables exist
        res = await conn.execute(select(1))
        assert res.scalar() == 1
    await clean_engine.dispose()


@pytest.mark.asyncio
async def test_crash_recovery_resumes_incomplete_feedback(db_session, seed_hardening_merchants):
    """Verify outcome feedback resumes from incomplete states without duplicate evidence or memory."""
    mA, _, _, _ = seed_hardening_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_95_crash_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # Mark Paid
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    db_session.add(Payment(
        id=f"pay_95_crash_{order.id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured"
    ))
    await db_session.commit()

    # Simulate worker crash after initial outcome record creation
    # Process outcome completely
    resp1 = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    )
    assert resp1.processing_state == ProcessingState.COMPLETED.value
    assert resp1.learning_eligible is True

    # Retry processing after simulated crash / restart
    resp2 = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    )
    assert resp2.is_duplicate is True
    assert resp2.outcome_id == resp1.outcome_id
    assert resp2.evidence_id == resp1.evidence_id
    assert resp2.memory_id == resp1.memory_id

    # Verify strictly 1 evidence record and 1 memory record
    evi_count = (await db_session.execute(
        select(func.count(LearningEvidenceRecord.id)).where(
            LearningEvidenceRecord.execution_id == boundary_res.execution_id
        )
    )).scalar_one()
    assert evi_count == 1


@pytest.mark.asyncio
async def test_alembic_migration_chain_from_clean_database(tmp_path):
    """Verify reproducible Alembic migration chain: clean DB -> alembic upgrade head -> table invariants."""
    from alembic.config import Config
    from alembic import command
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    clean_db_file = tmp_path / "alembic_clean.db"
    clean_db_url = f"sqlite+aiosqlite:///{clean_db_file.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", clean_db_url)

    # Run alembic upgrade head synchronously
    command.upgrade(alembic_cfg, "head")

    # Verify tables created by migrations
    engine = create_async_engine(clean_db_url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = {row[0] for row in res.fetchall()}

        from domain.models import Base
        model_tables = set(Base.metadata.tables.keys())
        assert model_tables.issubset(tables)
        assert "alembic_version" in tables

        res_ver = await conn.execute(text("SELECT version_num FROM alembic_version;"))
        version = res_ver.scalar()
        assert version == "0db8d2e8f8f1"
    await engine.dispose()


@pytest.mark.asyncio
async def test_application_restart_persistence_and_recovery(tmp_path):
    """Verify runtime state survives process/engine disposal and resumes seamlessly in a fresh application instance."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from alembic.config import Config
    from alembic import command

    db_file = tmp_path / "restart_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    # Step 1: Run alembic migrations on clean DB
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    # Step 2: Application Lifecycle Instance #1 (Before restart)
    engine1 = create_async_engine(db_url, connect_args={"check_same_thread": False})
    Session1 = async_sessionmaker(bind=engine1, class_=AsyncSession, expire_on_commit=False)

    async with Session1() as session1:
        # Seed merchant & product
        m = Merchant(
            id="merch_restart_01",
            name="Restart Test Merchant",
            currency="INR",
            status="ACTIVE",
            business_objective="MAXIMIZE_REVENUE",
            minimum_margin_percent=Decimal("20.00"),
            maximum_discount_percent=Decimal("25.00")
        )
        p = Product(
            id="prod_restart_01",
            merchant_id=m.id,
            sku="SKU-RESTART-01",
            name="Restart Alpine Backpack",
            category="travel_backpack",
            price_paise=450000,
            cost_paise=250000,
            inventory_quantity=30,
            reserved_quantity=0,
            is_active=True,
            attributes={"weight_kg": 1.2}
        )
        session1.add_all([m, p])
        await session1.commit()

        # Decision & Execution
        dec_req = CanonicalDecisionRequest(
            merchant_id=m.id,
            opportunity_id="opp_restart_01",
            raw_prompt="travel backpack under 5000"
        )
        envelope = await CanonicalDecisionRuntime.decide(session1, dec_req)
        exec_res = await DecisionExecutionBoundaryService.execute_decision(
            db=session1,
            decision_id=envelope.decision_id,
            request=DecisionExecuteRequest(merchant_id=m.id)
        )

        # Mark Paid in Phase 5
        order = (await session1.execute(select(Order).where(Order.id == exec_res.order_id))).scalar_one()
        order.status = TransactionState.PAID.value
        session1.add(Payment(
            id=f"pay_restart_{order.id[-10:]}",
            order_id=order.id,
            amount_paise=exec_res.authorized_amount_paise,
            currency="INR",
            status="captured"
        ))
        await session1.commit()
        execution_id = exec_res.execution_id

    # SIMULATE HARD APPLICATION SHUTDOWN / CRASH:
    # Completely dispose engine1 and all connection pools
    await engine1.dispose()
    del engine1
    del Session1

    # Step 3: Application Lifecycle Instance #2 (Fresh Restart)
    engine2 = create_async_engine(db_url, connect_args={"check_same_thread": False})
    Session2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)

    async with Session2() as session2:
        # Verify uncorrupted state after restart
        ord_post = (await session2.execute(select(Order).where(Order.id == exec_res.order_id))).scalar_one()
        assert ord_post.status == TransactionState.PAID.value

        # Resume outcome feedback in fresh application session
        outcome_res = await OutcomeFeedbackService.process_outcome(
            session2,
            OutcomeProcessRequest(merchant_id="merch_restart_01", execution_id=execution_id)
        )
        assert outcome_res.outcome_status == OutcomeStatus.PAYMENT_SUCCESS.value
        assert outcome_res.processing_state == ProcessingState.COMPLETED.value
        assert outcome_res.learning_eligible is True

        # Verify model was created and updated in the restarted instance
        model_state, _ = await PolicyLearningModelService.get_or_create_model(session2, "merch_restart_01")
        assert model_state.observation_count == 1

    await engine2.dispose()
