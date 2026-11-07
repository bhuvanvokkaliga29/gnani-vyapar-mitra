"""Deterministic Contribution Calculator & Reward Signal Evaluator.

Adheres to:
- merchant-reward/v1
- contribution-formula/v1
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, List, Optional
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
from services.reward.errors import (
    RewardError,
    IneligibleRewardError,
    RewardDataUnavailableError,
    RewardAttributionError
)


class ContributionCalculator:
    """Deterministic commercial contribution and margin calculations (Phase 2 foundation)."""

    @staticmethod
    def calculate_contribution_paise(
        realized_revenue_paise: int,
        realized_cogs_paise: int
    ) -> int:
        """Calculate net gross contribution in integer paise.
        
        Formula: Contribution = RealizedRevenue - RealizedCOGS
        
        NOTE: Can be negative if selling below COGS (predatory pricing/loss leaders).
        We strictly preserve negative contribution to penalize value-destroying policies.
        """
        return realized_revenue_paise - realized_cogs_paise

    @staticmethod
    def calculate_margin_percent(
        realized_revenue_paise: int,
        realized_cogs_paise: int
    ) -> float:
        """Calculate gross profit margin percentage using exact Decimal arithmetic."""
        if realized_revenue_paise <= 0:
            return 0.0

        rev_dec = Decimal(realized_revenue_paise)
        cogs_dec = Decimal(realized_cogs_paise)
        margin = ((rev_dec - cogs_dec) / rev_dec) * Decimal(100)
        return float(margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class RewardSignalEvaluator:
    """Evaluates PolicyLearningEvidence into a versioned PolicyOpportunityReward."""

    @classmethod
    def evaluate_opportunity(
        cls,
        evidence: PolicyLearningEvidence
    ) -> PolicyOpportunityReward:
        """Derive an authoritative PolicyOpportunityReward from a single PolicyLearningEvidence record."""
        # Opportunity ID: experiment_id:scenario_id:variant
        opportunity_id = f"{evidence.experiment_id}:{evidence.scenario_id}:{evidence.variant.value}"

        # 1. Inadmissibility / Failure Filtering (Evidence Firewall)
        if evidence.evidence_status == EvidenceQualityStatus.INVALID:
            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_INVALID,
                is_admissible=False,
                reasons=["Evidence flagged as invalid or integrity broken."],
                contribution_paise=0
            )

        if evidence.evidence_status == EvidenceQualityStatus.GUARDRAIL_FAILURE:
            # ANTI-SELECTION INVARIANT: Guardrail failures remain in the population denominator
            # with 0 contribution, ensuring policies cannot artificially inflate contribution per shopper
            # by causing undesirable cases to become denominator exclusions.
            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_GUARDRAIL_VIOLATION,
                is_admissible=True,  # Retained in denominator to properly dilute economic metric!
                is_safety_violation=True,
                reasons=["Policy outcome violated merchant commercial safety guardrails."],
                contribution_paise=0,
                revenue_paise=0,
                cogs_paise=0
            )

        if evidence.evidence_status in [EvidenceQualityStatus.INSUFFICIENT_SAMPLE, EvidenceQualityStatus.INCONCLUSIVE]:
            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_INELIGIBLE,
                is_admissible=False,
                reasons=[f"Evidence status is {evidence.evidence_status.value}."],
                contribution_paise=0
            )

        if not evidence.learning_eligible:
            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_INELIGIBLE,
                is_admissible=False,
                reasons=evidence.eligibility_reasons or ["Evidence marked ineligible by Phase 8.1 validator."],
                contribution_paise=0
            )

        # 2. Non-Purchase / Non-Conversion Outcomes -> REWARD_ZERO (Admissible in Denominator)
        # Cases: NO_SELECTION, EXECUTION_REJECTED, PAYMENT_FAILURE, or ORDER_CREATED but unpaid
        if evidence.outcome_type in [
            LearningOutcomeType.NO_SELECTION,
            LearningOutcomeType.EXECUTION_REJECTED,
            LearningOutcomeType.PAYMENT_FAILURE,
            LearningOutcomeType.ORDER_CREATED,
            LearningOutcomeType.EXPERIMENT_INCONCLUSIVE
        ]:
            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_ZERO,
                is_admissible=True,
                reasons=[],
                contribution_paise=0,
                revenue_paise=0,
                cogs_paise=0
            )

        # 3. Successful Conversion Outcomes -> REWARD_ELIGIBLE
        if evidence.outcome_type == LearningOutcomeType.PAYMENT_SUCCESS:
            # Observed test-mode transaction
            rev = evidence.observed_revenue_paise or 0
            contrib = evidence.observed_contribution_paise if evidence.observed_contribution_paise is not None else rev
            cogs = rev - contrib

            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_ELIGIBLE,
                is_admissible=True,
                reasons=[],
                contribution_paise=contrib,
                revenue_paise=rev,
                cogs_paise=cogs,
                margin_percent=evidence.margin_percent
            )

        elif evidence.outcome_type == LearningOutcomeType.SIMULATED_SELECTION:
            # Simulated buyer selection
            rev = evidence.expected_revenue_paise
            contrib = evidence.expected_contribution_paise
            cogs = rev - contrib

            return cls._build_reward(
                evidence=evidence,
                opportunity_id=opportunity_id,
                state=RewardState.REWARD_ELIGIBLE,
                is_admissible=True,
                reasons=[],
                contribution_paise=contrib,
                revenue_paise=rev,
                cogs_paise=cogs,
                margin_percent=evidence.margin_percent
            )

        # Default fallback
        return cls._build_reward(
            evidence=evidence,
            opportunity_id=opportunity_id,
            state=RewardState.REWARD_INELIGIBLE,
            is_admissible=False,
            reasons=[f"Unhandled outcome type: {evidence.outcome_type.value}"],
            contribution_paise=0
        )

    @classmethod
    def _build_reward(
        cls,
        evidence: PolicyLearningEvidence,
        opportunity_id: str,
        state: RewardState,
        is_admissible: bool,
        reasons: List[str],
        contribution_paise: int,
        revenue_paise: int = 0,
        cogs_paise: int = 0,
        margin_percent: float = 0.0,
        is_safety_violation: bool = False
    ) -> PolicyOpportunityReward:
        """Construct the immutable PolicyOpportunityReward schema."""
        idempotency_key = f"rwd_{evidence.idempotency_key}"
        return PolicyOpportunityReward(
            reward_id=f"rwd_{uuid.uuid4().hex[:12]}",
            reward_version="merchant-reward/v1",
            formula_version="contribution-formula/v1",
            merchant_id=evidence.merchant_id,
            opportunity_id=opportunity_id,
            buyer_context_key=evidence.buyer_context_key,
            policy_id=evidence.policy_id,
            policy_version=evidence.policy_version,
            experiment_id=evidence.experiment_id,
            experiment_version=evidence.experiment_version,
            variant=evidence.variant,
            evidence_id=evidence.evidence_id,
            evidence_source=evidence.source,
            outcome_type=evidence.outcome_type,
            reward_state=state,
            is_admissible=is_admissible,
            is_safety_violation=is_safety_violation,
            inadmissibility_reasons=reasons,
            realized_revenue_paise=revenue_paise,
            realized_cogs_paise=cogs_paise,
            realized_discount_paise=0,
            reward_contribution_paise=contribution_paise,
            margin_percent=margin_percent,
            idempotency_key=idempotency_key
        )
