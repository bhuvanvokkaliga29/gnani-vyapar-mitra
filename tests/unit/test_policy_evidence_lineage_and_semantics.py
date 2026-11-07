"""Comprehensive Unit & Lineage Tests for Policy Evidence Attribution & Semantics.

Fulfills requirements for:
- Current-effective policy evidence semantics (is_current, learning_eligible, observed_at <= now).
- Policy-specific evidence attribution (policy A != policy B).
- Multi-tenant evidence isolation (merchant A != merchant B).
- Baseline NO_OFFER independence (paid transactions != NO_OFFER evidence).
- Ineligible & future evidence rejection.
- Idempotency / duplicate replay protection.
- Superseded observation preservation.
- Reconciliation between Overview Top Signal and Policy Version Registry.
- PolicyViewService API & UI mapping exact fidelity.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func, and_

from domain.models import (
    Base,
    Merchant,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    PolicyMemoryRecord,
    LearningEvidenceRecord,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    AppliedModelObservationRecord,
    ExperimentRecord,
    ObservationRecord
)
from services.dashboard.service import PolicyViewService, DashboardOverviewService
from services.memory.service import PolicyMemoryService
from services.memory.schemas import PolicyMemoryRecordSchema
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus,
    EvidenceLifecycleState
)
from services.experiments.schemas import VariantType
from services.reward.schemas import PolicyOpportunityReward, RewardState


@pytest.fixture
async def mem_db():
    """In-memory isolated test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def seed_merchants(mem_db: AsyncSession):
    """Seed test merchants A and B."""
    now = datetime.now(timezone.utc)
    mA = Merchant(id="merch_A", name="Merchant Alpha", currency="INR", status="ACTIVE")
    mB = Merchant(id="merch_B", name="Merchant Beta", currency="INR", status="ACTIVE")
    mem_db.add_all([mA, mB])

    # Experiment containers
    expA = ExperimentRecord(
        id="exp_A",
        merchant_id="merch_A",
        name="Runtime Exp A",
        status="ACTIVE",
        control_policy_id="cand_base_no_offer",
        treatment_policy_id="cand_A",
        control_proposal_snapshot={},
        treatment_proposal_snapshot={},
        hypothesis={},
        created_at=now
    )
    expB = ExperimentRecord(
        id="exp_B",
        merchant_id="merch_B",
        name="Runtime Exp B",
        status="ACTIVE",
        control_policy_id="cand_base_no_offer",
        treatment_policy_id="cand_B",
        control_proposal_snapshot={},
        treatment_proposal_snapshot={},
        hypothesis={},
        created_at=now
    )
    mem_db.add_all([expA, expB])

    # Registered policy versions for Merchant A
    pvr_base_A = MerchantPolicyVersionRecord(
        id="pver_A_base",
        merchant_id="merch_A",
        policy_id="cand_base_no_offer",
        policy_version="merchant-policy/v1",
        lifecycle_status="ACTIVE",
        strategy_type="NO_OFFER",
        created_at=now
    )
    pvr_cand_A = MerchantPolicyVersionRecord(
        id="pver_A_candA",
        merchant_id="merch_A",
        policy_id="cand_A",
        policy_version="merchant-policy/v1",
        lifecycle_status="CANDIDATE",
        strategy_type="SINGLE_PRODUCT",
        created_at=now
    )
    pvr_cand_A2 = MerchantPolicyVersionRecord(
        id="pver_A_candB",
        merchant_id="merch_A",
        policy_id="cand_B",
        policy_version="merchant-policy/v1",
        lifecycle_status="CANDIDATE",
        strategy_type="COMPLEMENTARY_BUNDLE",
        created_at=now
    )
    act_A = MerchantActivePolicy(
        merchant_id="merch_A",
        policy_id="cand_base_no_offer",
        policy_version="merchant-policy/v1",
        activated_at=now,
        promotion_id="init_base"
    )
    mem_db.add_all([pvr_base_A, pvr_cand_A, pvr_cand_A2, act_A])
    await mem_db.commit()


def make_memory_record(
    merchant_id: str,
    policy_id: str,
    opportunity_id: str,
    contrib_paise: int = 100000,
    learning_eligible: bool = True,
    is_current: bool = True,
    superseded_by: str = None,
    observed_at: datetime = None,
    context_key: str = "ctx_default"
) -> PolicyMemoryRecord:
    now = observed_at or datetime.now(timezone.utc)
    evi_id = f"evi_{uuid.uuid4().hex[:8]}"
    return PolicyMemoryRecord(
        id=f"mem_{uuid.uuid4().hex[:8]}",
        memory_version="merchant-memory/v1",
        merchant_id=merchant_id,
        opportunity_id=opportunity_id,
        buyer_context_key=context_key,
        scenario_id=opportunity_id,
        policy_id=policy_id,
        policy_version="merchant-policy/v1",
        experiment_id=f"exp_{merchant_id[6:]}",
        experiment_version="policy-experiment/v1",
        variant="TREATMENT",
        evidence_id=evi_id,
        evidence_source="TEST_MODE_OBSERVED",
        outcome_type="PAYMENT_SUCCESS",
        learning_eligible=learning_eligible,
        reward_id=f"rew_{uuid.uuid4().hex[:8]}",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state="FINAL",
        reward_contribution_paise=contrib_paise,
        is_admissible=True,
        is_safety_violation=False,
        is_current=is_current,
        superseded_by=superseded_by,
        idempotency_key=f"idem_mem_{uuid.uuid4().hex[:10]}",
        observed_at=now,
        persisted_at=now
    )


# ==============================================================================
# TESTS 1, 2, 3: Evidence counts for Policy A & Policy B increment authoritatively
# ==============================================================================

@pytest.mark.asyncio
async def test_1_and_2_and_3_policy_specific_evidence_attribution(mem_db: AsyncSession, seed_merchants):
    """TEST 1, 2, 3:
    - Outcome 1 for policy A -> count A = 1
    - Outcome 2 for policy A -> count A = 2
    - Outcome 3 for policy B -> count A = 2, count B = 1
    """
    # 1. First eligible outcome for policy A
    rec_A1 = make_memory_record(merchant_id="merch_A", policy_id="cand_A", opportunity_id="opp_A1", contrib_paise=150000)
    mem_db.add(rec_A1)
    await mem_db.commit()

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    cand_B = next(v for v in policies.versions if v.policy_id == "cand_B")
    assert cand_A.evidence_count == 1
    assert cand_A.observed_contribution_paise == 150000
    assert cand_B.evidence_count == 0

    # 2. Second eligible outcome for policy A
    rec_A2 = make_memory_record(merchant_id="merch_A", policy_id="cand_A", opportunity_id="opp_A2", contrib_paise=120000)
    mem_db.add(rec_A2)
    await mem_db.commit()

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 2
    assert cand_A.observed_contribution_paise == 270000

    # 3. Third eligible outcome for policy B
    rec_B1 = make_memory_record(merchant_id="merch_A", policy_id="cand_B", opportunity_id="opp_B1", contrib_paise=200000)
    mem_db.add(rec_B1)
    await mem_db.commit()

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    cand_B = next(v for v in policies.versions if v.policy_id == "cand_B")
    assert cand_A.evidence_count == 2
    assert cand_A.observed_contribution_paise == 270000
    assert cand_B.evidence_count == 1
    assert cand_B.observed_contribution_paise == 200000


# ==============================================================================
# TEST 4: Multi-Tenant Evidence Isolation
# ==============================================================================

@pytest.mark.asyncio
async def test_4_merchant_isolation(mem_db: AsyncSession, seed_merchants):
    """TEST 4: Merchant B's evidence does not leak into Merchant A."""
    rec_merch_B = make_memory_record(merchant_id="merch_B", policy_id="cand_A", opportunity_id="opp_foreign", contrib_paise=999999)
    mem_db.add(rec_merch_B)
    await mem_db.commit()

    policies_A = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies_A.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 0
    assert cand_A.observed_contribution_paise == 0


# ==============================================================================
# TEST 5 & 10: NO_OFFER Non-Purchase and Active Baseline Isolation
# ==============================================================================

@pytest.mark.asyncio
async def test_5_and_10_no_offer_active_baseline_zero_evidence(mem_db: AsyncSession, seed_merchants):
    """TEST 5 & 10:
    - NO_OFFER / non-purchase does not create offer policy evidence.
    - Active NO_OFFER baseline remains 0 even if candidate policies have paid observations.
    """
    # Add paid observations for cand_A
    rec_A = make_memory_record(merchant_id="merch_A", policy_id="cand_A", opportunity_id="opp_paid_1", contrib_paise=150000)
    mem_db.add(rec_A)
    await mem_db.commit()

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    # Active baseline must strictly be 0
    assert policies.active_policy.policy_id == "cand_base_no_offer"
    assert policies.active_policy.evidence_count == 0
    assert policies.active_policy.observed_contribution_paise == 0

    base_version = next(v for v in policies.versions if v.policy_id == "cand_base_no_offer")
    assert base_version.evidence_count == 0
    assert base_version.observed_contribution_paise == 0


# ==============================================================================
# TEST 6: Ineligible Evidence is Excluded
# ==============================================================================

@pytest.mark.asyncio
async def test_6_ineligible_evidence_rejected(mem_db: AsyncSession, seed_merchants):
    """TEST 6: Ineligible evidence (learning_eligible=False) does not increment count."""
    rec_ineligible = make_memory_record(
        merchant_id="merch_A",
        policy_id="cand_A",
        opportunity_id="opp_ineligible",
        learning_eligible=False
    )
    mem_db.add(rec_ineligible)
    await mem_db.commit()

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 0
    assert cand_A.observed_contribution_paise == 0


# ==============================================================================
# TEST 7: Duplicate Replay Idempotency
# ==============================================================================

@pytest.mark.asyncio
async def test_7_duplicate_replay_idempotency(mem_db: AsyncSession, seed_merchants):
    """TEST 7: Duplicate evidence replay does not increment count twice."""
    now = datetime.now(timezone.utc)
    evidence = PolicyLearningEvidence(
        evidence_id="evi_replay_01",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_A",
        experiment_id="exp_A",
        experiment_version="policy-experiment/v1",
        experiment_observation_id="obs_rep_01",
        scenario_id="scen_rep",
        policy_id="cand_A",
        policy_version="merchant-policy/v1",
        variant=VariantType.TREATMENT,
        buyer_context_key="ctx_replay",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=500000,
        expected_contribution_paise=200000,
        observed_revenue_paise=500000,
        observed_contribution_paise=200000,
        margin_percent=40.0,
        evidence_status=EvidenceQualityStatus.VALID,
        lifecycle_state=EvidenceLifecycleState.LEARNING_ELIGIBLE,
        learning_eligible=True,
        aggregation_key="merch_A:ctx_replay:cand_A:merchant-policy/v1",
        idempotency_key="evi_idem_rep_01",
        observed_at=now
    )

    # First record
    m1 = await PolicyMemoryService.record_observation(mem_db, evidence)
    await mem_db.commit()

    # Replay identical evidence
    m2 = await PolicyMemoryService.record_observation(mem_db, evidence)
    await mem_db.commit()

    assert m1.memory_id == m2.memory_id

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 1
    assert cand_A.observed_contribution_paise == 200000


# ==============================================================================
# TEST 8: Superseded Records Excluded from Current-Effective Count
# ==============================================================================

@pytest.mark.asyncio
async def test_8_superseded_records_excluded_from_current_effective(mem_db: AsyncSession, seed_merchants):
    """TEST 8: Superseded records (is_current=False) remain in DB history but are excluded from current count."""
    rec_old = make_memory_record(
        merchant_id="merch_A",
        policy_id="cand_A",
        opportunity_id="opp_reconciled",
        contrib_paise=100000,
        is_current=False,
        superseded_by="mem_new"
    )
    rec_new = make_memory_record(
        merchant_id="merch_A",
        policy_id="cand_A",
        opportunity_id="opp_reconciled",
        contrib_paise=150000,
        is_current=True
    )
    mem_db.add_all([rec_old, rec_new])
    await mem_db.commit()

    # Database retains both (history preserved)
    total_db = (await mem_db.execute(select(func.count(PolicyMemoryRecord.id)).where(PolicyMemoryRecord.policy_id == "cand_A"))).scalar()
    assert total_db == 2

    # Current-effective count must be 1, contribution must be 150000 (not 250000)
    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 1
    assert cand_A.observed_contribution_paise == 150000


# ==============================================================================
# TEST 9: Future Evidence Excluded
# ==============================================================================

@pytest.mark.asyncio
async def test_9_future_evidence_excluded(mem_db: AsyncSession, seed_merchants):
    """TEST 9: Evidence with observed_at in the future is excluded."""
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    rec_future = make_memory_record(
        merchant_id="merch_A",
        policy_id="cand_A",
        opportunity_id="opp_future",
        observed_at=future_time
    )
    mem_db.add(rec_future)
    await mem_db.commit()

    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 0
    assert cand_A.observed_contribution_paise == 0


# ==============================================================================
# TEST 11: Overview Top Learned Signal Reconciliation
# ==============================================================================

@pytest.mark.asyncio
async def test_11_overview_top_signal_vs_policy_registry(mem_db: AsyncSession, seed_merchants):
    """TEST 11: Overview top learned signal corresponds to the top memory record, which may be an explored candidate."""
    # Policy cand_explored is NOT in the version registry, but has high evidence in ctx_travel
    rec_exp = make_memory_record(
        merchant_id="merch_A",
        policy_id="cand_explored_super",
        opportunity_id="opp_exp_1",
        contrib_paise=350000,
        context_key="ctx_travel"
    )
    # Policy cand_A is in version registry and has lower evidence in ctx_city
    rec_A = make_memory_record(
        merchant_id="merch_A",
        policy_id="cand_A",
        opportunity_id="opp_A_1",
        contrib_paise=100000,
        context_key="ctx_city"
    )
    mem_db.add_all([rec_exp, rec_A])
    await mem_db.commit()

    # Overview top signal must reflect cand_explored_super (top economic contributor)
    overview = await DashboardOverviewService.get_overview(mem_db, "merch_A")
    assert overview.learning_insight is not None
    assert overview.learning_insight.observed_preference_strategy == "cand_explored_super"
    assert overview.learning_insight.observed_contribution_paise == 350000
    assert overview.learning_insight.evidence_count == 1

    # Policies page queries registry policies (cand_A and cand_B)
    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == 1
    assert cand_A.observed_contribution_paise == 100000

    cand_B = next(v for v in policies.versions if v.policy_id == "cand_B")
    assert cand_B.evidence_count == 0


# ==============================================================================
# TEST 12 & 13: Policies API & UI Exact Fidelity
# ==============================================================================

@pytest.mark.asyncio
async def test_12_and_13_api_and_ui_mapping_fidelity(mem_db: AsyncSession, seed_merchants):
    """TEST 12 & 13: Policies API equals authoritative query, and DTO serializes exactly as UI expects."""
    rec = make_memory_record(merchant_id="merch_A", policy_id="cand_A", opportunity_id="opp_exact", contrib_paise=180000)
    mem_db.add(rec)
    await mem_db.commit()

    # 1. Authoritative DB query
    now_utc = datetime.now(timezone.utc)
    auth_count = (await mem_db.execute(
        select(func.count(PolicyMemoryRecord.id)).where(
            and_(
                PolicyMemoryRecord.merchant_id == "merch_A",
                PolicyMemoryRecord.policy_id == "cand_A",
                PolicyMemoryRecord.learning_eligible == True,
                PolicyMemoryRecord.is_current == True,
                PolicyMemoryRecord.observed_at <= now_utc
            )
        )
    )).scalar()

    # 2. Service API DTO
    policies = await PolicyViewService.get_policies(mem_db, "merch_A")
    cand_A = next(v for v in policies.versions if v.policy_id == "cand_A")
    assert cand_A.evidence_count == auth_count == 1
    assert cand_A.observed_contribution_paise == 180000

    # 3. UI Serialization Shape Check
    ui_dict = cand_A.model_dump()
    assert ui_dict["evidence_count"] == 1
    assert ui_dict["observed_contribution_paise"] == 180000
    assert ui_dict["policy_id"] == "cand_A"
    assert ui_dict["lifecycle_status"] == "CANDIDATE"
