"""Unit tests for Phase 8.3 Policy Memory schemas and contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from services.experiments.schemas import VariantType
from services.learning.schemas import EvidenceSource, LearningOutcomeType
from services.reward.schemas import RewardState
from services.memory.schemas import (
    PolicyMemoryRecordSchema,
    HistoricalObservationFilter,
    HistoricalObservationList,
    HistoricalPolicySummary
)


def test_policy_memory_schema_valid():
    """PolicyMemoryRecordSchema conforms to contract merchant-memory/v1."""
    mem = PolicyMemoryRecordSchema(
        memory_id="mem_01",
        memory_version="merchant-memory/v1",
        merchant_id="merch_atlas",
        opportunity_id="exp_01:scen_01:TREATMENT",
        buyer_context_key="bck_test",
        scenario_id="scen_01",
        policy_id="p_treat",
        policy_version="merchant-policy/v1",
        experiment_id="exp_01",
        experiment_version="policy-experiment/v1",
        variant=VariantType.TREATMENT,
        evidence_id="evi_01",
        evidence_source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        learning_eligible=True,
        reward_id="rwd_01",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state=RewardState.REWARD_ELIGIBLE,
        is_admissible=True,
        is_safety_violation=False,
        realized_revenue_paise=350000,
        realized_cogs_paise=175000,
        realized_discount_paise=0,
        reward_contribution_paise=175000,
        margin_percent=50.0,
        idempotency_key="mem_evi_01",
        observed_at=datetime.now(timezone.utc)
    )

    assert mem.memory_version == "merchant-memory/v1"
    assert mem.reward_contribution_paise == 175000
    assert mem.opportunity_id == "exp_01:scen_01:TREATMENT"


def test_policy_memory_forbids_extra_fields():
    """PolicyMemoryRecordSchema strictly forbids extra fields (e.g. bandit weights, opinions)."""
    with pytest.raises(ValidationError):
        PolicyMemoryRecordSchema(
            memory_id="mem_02",
            merchant_id="merch_atlas",
            opportunity_id="exp_01:scen_02:CONTROL",
            buyer_context_key="bck_test",
            scenario_id="scen_02",
            policy_id="p_ctrl",
            experiment_id="exp_01",
            variant=VariantType.CONTROL,
            evidence_id="evi_02",
            evidence_source=EvidenceSource.SIMULATED,
            outcome_type=LearningOutcomeType.NO_SELECTION,
            learning_eligible=True,
            reward_id="rwd_02",
            reward_state=RewardState.REWARD_ZERO,
            is_admissible=True,
            idempotency_key="mem_evi_02",
            observed_at=datetime.now(timezone.utc),
            learned_policy_rank=1,      # FORBIDDEN!
            bandit_selection_weight=0.9 # FORBIDDEN!
        )


def test_historical_policy_summary_factual_only():
    """HistoricalPolicySummary stores factual aggregations only."""
    summary = HistoricalPolicySummary(
        merchant_id="merch_atlas",
        policy_id="p_treat",
        total_opportunities=10,
        eligible_opportunities=10,
        guardrail_violations=0,
        is_policy_admissible=True,
        converted_payments=4,
        conversion_rate=0.4,
        total_contribution_paise=400000,
        contribution_per_shopper_paise=40000,
        contribution_per_shopper_decimal=40000.0,
        average_margin_percent=50.0
    )

    assert summary.conversion_rate == 0.4
    assert summary.contribution_per_shopper_paise == 40000
    assert summary.is_policy_admissible is True
    # Verify no opinion / decision fields exist on schema
    assert not hasattr(summary, "winner")
    assert not hasattr(summary, "recommendation")
