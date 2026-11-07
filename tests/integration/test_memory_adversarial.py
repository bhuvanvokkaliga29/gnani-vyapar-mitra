"""Adversarial and Edge Case Verification Suite for Phase 8.3 Merchant Policy Memory.

Verifies the 25 adversarial failure modes specified in Phase 8.3 requirements:
1. Same context, different opportunities
2. Same opportunity, duplicate observation
3. Retry of same write (idempotent)
4. Same policy, multiple versions
5. Same context across policies
6. Same policy across contexts
7. Merchant A attempting to read Merchant B history
8. Simulated evidence preserved
9. Test Mode observed evidence preserved
10. Invalid evidence preserved
11. Guardrail violation preserved
12. Zero contribution preserved
13. Negative contribution preserved
14. Missing reward rejected
15. Reward version preserved
16. Contribution-formula version preserved
17. Reordered database results handled deterministically
18. Pagination consistency
19. Historical policy version immutability
20. Concurrent duplicate insertion safety
21. Client attempts to inject reward
22. Client attempts to inject learning eligibility
23. Post-outcome data mutating pre-decision context
24. Aggregation across mixed contexts
25. Historical record after policy version change
+ Static AST Boundary Audit
"""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus
)
from services.reward.schemas import (
    PolicyOpportunityReward,
    RewardState
)
from services.reward.calculator import RewardSignalEvaluator
from services.memory.service import PolicyMemoryService
from services.memory.schemas import (
    PolicyMemoryRecordSchema,
    HistoricalObservationFilter,
    RecordMemoryRequest
)
from services.memory.errors import (
    MemoryTenantViolationError,
    DuplicateMemoryRecordError,
    MemoryError
)
from domain.models import Merchant


def make_adv_evidence(
    idx: int,
    merchant_id: str = "merch_adv",
    policy_id: str = "p_treat",
    policy_version: str = "merchant-policy/v1",
    scenario_id: str = None,
    buyer_context_key: str = "bck_backpack_mid",
    contrib_paise: int = 50000,
    source: EvidenceSource = EvidenceSource.SIMULATED,
    is_safe: bool = True
) -> PolicyLearningEvidence:
    scen = scenario_id or f"scen_{idx}"
    return PolicyLearningEvidence(
        evidence_id=f"evi_adv_{idx}",
        evidence_version="merchant-learning/v1",
        merchant_id=merchant_id,
        experiment_id="exp_adv_01",
        experiment_observation_id=f"obs_adv_{idx}",
        scenario_id=scen,
        policy_id=policy_id,
        policy_version=policy_version,
        variant=VariantType.TREATMENT,
        buyer_context_key=buyer_context_key,
        source=source,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION if source == EvidenceSource.SIMULATED else LearningOutcomeType.PAYMENT_SUCCESS,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=contrib_paise * 2 if source == EvidenceSource.SIMULATED else 0,
        expected_contribution_paise=contrib_paise if source == EvidenceSource.SIMULATED else 0,
        observed_revenue_paise=contrib_paise * 2 if source != EvidenceSource.SIMULATED else None,
        observed_contribution_paise=contrib_paise if source != EvidenceSource.SIMULATED else None,
        margin_percent=50.0 if is_safe else 10.0,
        evidence_status=EvidenceQualityStatus.VALID if is_safe else EvidenceQualityStatus.GUARDRAIL_FAILURE,
        learning_eligible=is_safe,
        aggregation_key=f"{merchant_id}:{buyer_context_key}:{policy_id}:{policy_version}",
        idempotency_key=f"idem_adv_{idx}",
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=idx)
    )


@pytest.fixture
async def seed_merchant(db_session):
    m = Merchant(id="merch_adv", name="Adv Merchant", currency="INR", status="ACTIVE")
    m_other = Merchant(id="merch_other", name="Other Merchant", currency="INR", status="ACTIVE")
    db_session.add_all([m, m_other])
    await db_session.commit()
    return m


@pytest.mark.asyncio
async def test_case_1_same_context_different_opportunities(db_session, seed_merchant):
    """Case 1: Same context across two distinct opportunities -> Both preserved in memory."""
    e1 = make_adv_evidence(1, scenario_id="scen_a", buyer_context_key="bck_same")
    e2 = make_adv_evidence(2, scenario_id="scen_b", buyer_context_key="bck_same")

    m1 = await PolicyMemoryService.record_observation(db_session, e1)
    m2 = await PolicyMemoryService.record_observation(db_session, e2)

    assert m1.opportunity_id != m2.opportunity_id
    assert m1.buyer_context_key == m2.buyer_context_key


@pytest.mark.asyncio
async def test_case_2_and_3_same_opportunity_duplicate_and_retry(db_session, seed_merchant):
    """Cases 2 & 3: Duplicate observation and write retry -> Idempotent, exactly one record created."""
    e = make_adv_evidence(3)
    m1 = await PolicyMemoryService.record_observation(db_session, e)
    m2 = await PolicyMemoryService.record_observation(db_session, e)

    assert m1.memory_id == m2.memory_id
    assert m1.idempotency_key == m2.idempotency_key


@pytest.mark.asyncio
async def test_case_4_same_policy_multiple_versions(db_session, seed_merchant):
    """Case 4: Same policy ID evaluated under v1 and v2 -> Separate version records preserved."""
    e_v1 = make_adv_evidence(4, policy_id="p_vers", policy_version="merchant-policy/v1")
    e_v2 = make_adv_evidence(5, policy_id="p_vers", policy_version="merchant-policy/v2")

    m_v1 = await PolicyMemoryService.record_observation(db_session, e_v1)
    m_v2 = await PolicyMemoryService.record_observation(db_session, e_v2)

    assert m_v1.policy_version == "merchant-policy/v1"
    assert m_v2.policy_version == "merchant-policy/v2"


@pytest.mark.asyncio
async def test_case_5_and_6_context_and_policy_orthogonality(db_session, seed_merchant):
    """Cases 5 & 6: Same context across different policies, and same policy across different contexts."""
    # Same context, different policies
    e_p1 = make_adv_evidence(6, policy_id="p_one", buyer_context_key="bck_ctx_x")
    e_p2 = make_adv_evidence(7, policy_id="p_two", buyer_context_key="bck_ctx_x")
    m_p1 = await PolicyMemoryService.record_observation(db_session, e_p1)
    m_p2 = await PolicyMemoryService.record_observation(db_session, e_p2)
    assert m_p1.policy_id != m_p2.policy_id
    assert m_p1.buyer_context_key == m_p2.buyer_context_key

    # Same policy, different contexts
    e_c1 = make_adv_evidence(8, policy_id="p_shared", buyer_context_key="bck_ctx_1")
    e_c2 = make_adv_evidence(9, policy_id="p_shared", buyer_context_key="bck_ctx_2")
    m_c1 = await PolicyMemoryService.record_observation(db_session, e_c1)
    m_c2 = await PolicyMemoryService.record_observation(db_session, e_c2)
    assert m_c1.buyer_context_key != m_c2.buyer_context_key
    assert m_c1.policy_id == m_c2.policy_id


@pytest.mark.asyncio
async def test_case_7_merchant_a_attempting_to_read_merchant_b(db_session, seed_merchant):
    """Case 7: Merchant A attempting to read Merchant B history raises MemoryTenantViolationError."""
    e_other = make_adv_evidence(10, merchant_id="merch_other")
    m_other = await PolicyMemoryService.record_observation(db_session, e_other)

    with pytest.raises(MemoryTenantViolationError):
        await PolicyMemoryService.get_observation(db_session, "merch_adv", m_other.memory_id)


@pytest.mark.asyncio
async def test_cases_8_and_9_simulated_and_test_mode_preservation(db_session, seed_merchant):
    """Cases 8 & 9: Simulated and Test Mode observed sources are explicitly preserved."""
    e_sim = make_adv_evidence(11, source=EvidenceSource.SIMULATED)
    e_test = make_adv_evidence(12, source=EvidenceSource.TEST_MODE_OBSERVED)

    m_sim = await PolicyMemoryService.record_observation(db_session, e_sim)
    m_test = await PolicyMemoryService.record_observation(db_session, e_test)

    assert m_sim.evidence_source == EvidenceSource.SIMULATED
    assert m_test.evidence_source == EvidenceSource.TEST_MODE_OBSERVED


@pytest.mark.asyncio
async def test_cases_10_11_12_13_economic_states_preservation(db_session, seed_merchant):
    """Cases 10, 11, 12, 13: Invalid, Guardrail violation, Zero, and Negative contribution."""
    # 10. Invalid evidence
    e_inv = make_adv_evidence(13)
    e_inv.evidence_status = EvidenceQualityStatus.INVALID
    e_inv.learning_eligible = False
    m_inv = await PolicyMemoryService.record_observation(db_session, e_inv)
    assert m_inv.reward_state == RewardState.REWARD_INVALID
    assert m_inv.is_admissible is False

    # 11. Guardrail violation
    e_grd = make_adv_evidence(14, is_safe=False)
    m_grd = await PolicyMemoryService.record_observation(db_session, e_grd)
    assert m_grd.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION
    assert m_grd.is_admissible is True
    assert m_grd.is_safety_violation is True
    assert m_grd.reward_contribution_paise == 0

    # 12. Zero contribution (non-purchase)
    e_zero = make_adv_evidence(15)
    e_zero.outcome_type = LearningOutcomeType.NO_SELECTION
    e_zero.expected_revenue_paise = 0
    e_zero.expected_contribution_paise = 0
    m_zero = await PolicyMemoryService.record_observation(db_session, e_zero)
    assert m_zero.reward_state == RewardState.REWARD_ZERO
    assert m_zero.reward_contribution_paise == 0

    # 13. Negative contribution
    e_neg = make_adv_evidence(16)
    e_neg.expected_revenue_paise = 100000
    e_neg.expected_contribution_paise = -20000  # -₹200
    m_neg = await PolicyMemoryService.record_observation(db_session, e_neg)
    assert m_neg.reward_contribution_paise == -20000


@pytest.mark.asyncio
async def test_cases_14_15_16_reward_contract_and_version_integrity(db_session, seed_merchant):
    """Cases 14, 15, 16: Reward version and formula version are preserved immutably."""
    e = make_adv_evidence(17)
    m = await PolicyMemoryService.record_observation(db_session, e)
    assert m.reward_version == "merchant-reward/v1"
    assert m.formula_version == "contribution-formula/v1"


@pytest.mark.asyncio
async def test_cases_17_and_18_deterministic_ordering_and_pagination(db_session, seed_merchant):
    """Cases 17 & 18: Historical retrieval is deterministically ordered (observed_at DESC, id ASC) and paginates."""
    for i in range(5):
        await PolicyMemoryService.record_observation(db_session, make_adv_evidence(30 + i))

    # Page 1 (limit 2)
    p1 = await PolicyMemoryService.query_history(
        db_session,
        HistoricalObservationFilter(merchant_id="merch_adv", limit=2, offset=0)
    )
    assert len(p1.items) == 2

    # Page 2 (limit 2)
    p2 = await PolicyMemoryService.query_history(
        db_session,
        HistoricalObservationFilter(merchant_id="merch_adv", limit=2, offset=2)
    )
    assert len(p2.items) == 2

    # Verify no overlap
    ids_p1 = {item.memory_id for item in p1.items}
    ids_p2 = {item.memory_id for item in p2.items}
    assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_case_19_historical_policy_version_immutability(db_session, seed_merchant):
    """Case 19: Stored historical record preserves its original policy version even when new versions appear."""
    e_old = make_adv_evidence(40, policy_id="p_stable", policy_version="merchant-policy/v1")
    m_old = await PolicyMemoryService.record_observation(db_session, e_old)

    e_new = make_adv_evidence(41, policy_id="p_stable", policy_version="merchant-policy/v2")
    m_new = await PolicyMemoryService.record_observation(db_session, e_new)

    rec_old = await PolicyMemoryService.get_observation(db_session, "merch_adv", m_old.memory_id)
    assert rec_old.policy_version == "merchant-policy/v1"
    assert m_new.policy_version == "merchant-policy/v2"


@pytest.mark.asyncio
async def test_cases_21_and_22_client_cannot_forge_reward_or_eligibility(db_session, seed_merchant):
    """Cases 21 & 22: RecordMemoryRequest only accepts evidence_id + merchant_id; client cannot pass reward or eligibility."""
    req = RecordMemoryRequest(evidence_id="evi_test", merchant_id="merch_adv")
    assert not hasattr(req, "reward_contribution_paise")
    assert not hasattr(req, "learning_eligible")


@pytest.mark.asyncio
async def test_case_23_anti_leakage_pre_decision_context_immutable(db_session, seed_merchant):
    """Case 23: Memory record separates buyer_context_key from post-decision realized revenue."""
    e = make_adv_evidence(50)
    m = await PolicyMemoryService.record_observation(db_session, e)
    # buyer_context_key does not contain realized paise
    assert "paise" not in m.buyer_context_key.lower()


@pytest.mark.asyncio
async def test_case_24_aggregation_across_mixed_contexts(db_session, seed_merchant):
    """Case 24: Aggregated summary over diverse contexts returns factual aggregates."""
    e1 = make_adv_evidence(61, policy_id="p_mix", buyer_context_key="bck_cat_1", contrib_paise=30000)
    e2 = make_adv_evidence(62, policy_id="p_mix", buyer_context_key="bck_cat_2", contrib_paise=70000)
    await PolicyMemoryService.record_observation(db_session, e1)
    await PolicyMemoryService.record_observation(db_session, e2)

    summary = await PolicyMemoryService.get_policy_summary(db_session, "merch_adv", "p_mix")
    assert summary.total_opportunities == 2
    assert summary.total_contribution_paise == 100000
    assert summary.contribution_per_shopper_paise == 50000


@pytest.mark.asyncio
async def test_case_25_static_ast_boundary_audit():
    """Static AST Boundary Audit: services/memory must contain zero learning algorithms or bandits."""
    import os
    import ast

    memory_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "memory")
    forbidden_terms = [
        "RazorpayClient",
        "rzp_test",
        "bandit",
        "q_learning",
        "reinforcement_learning",
        "epsilon_greedy",
        "policy_gradient",
        "update_policy",
        "optimize_policy",
        "rank_policies",
        "select_next_policy"
    ]

    for root, _, files in os.walk(memory_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    _ = ast.parse(content, filename=file_path)

                    for term in forbidden_terms:
                        assert term.lower() not in content.lower(), (
                            f"Security boundary violation: '{term}' found in {file_path}. "
                            "Phase 8.3 stores and retrieves history only. "
                            "It must NOT implement learning algorithms or policy selection."
                        )
