"""Deterministic Policy Baseline Strategy Generator.

Provides a pure rule-based commercial strategy benchmark and fallback.
Used to evaluate whether the AI Policy Agent provides measurable value
beyond deterministic heuristics.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from domain.commerce_schemas import MerchantCommerceContext, ProductResponse
from domain.intent_schemas import BuyerIntent, ConfidenceLevel
from services.policy.schemas import (
    PolicyProposal,
    PolicyCandidate,
    ProposalStatus,
    StrategyType,
    CandidateValidationStatus,
    PolicyEvidence
)
from services.policy.context import filter_eligible_products, get_complementary_products
from services.policy.validator import PolicyValidator
from services.policy.ranking import PolicyScorer


class DeterministicPolicyBaseline:
    """Pure rule-based baseline policy generator (no LLM reasoning)."""

    def __init__(self):
        self.validator = PolicyValidator()
        self.scorer = PolicyScorer()

    def generate_baseline_proposal(
        self,
        intent: BuyerIntent,
        context: MerchantCommerceContext
    ) -> PolicyProposal:
        """Deterministically generate compliant baseline strategies."""
        proposal_id = f"prop_base_{uuid.uuid4().hex[:10]}"
        eligible = filter_eligible_products(context, intent)

        # Handle no eligible products
        if not eligible:
            no_offer = PolicyCandidate(
                candidate_id=f"cand_base_no_offer",
                strategy_type=StrategyType.NO_OFFER,
                product_ids=[],
                rationale="No products in catalog satisfy the stated buyer constraints.",
                confidence=ConfidenceLevel.HIGH,
                validation_status=CandidateValidationStatus.APPROVED
            )
            now = datetime.now(timezone.utc)
            return PolicyProposal(
                proposal_id=proposal_id,
                merchant_id=context.merchant_id,
                policy_version="merchant-policy/v1",
                prompt_version="deterministic-baseline/v1",
                intent_version=getattr(intent, "schema_version", "buyer-intent/v1") or "buyer-intent/v1",
                context_version="commerce-context/v1",
                validator_version="deterministic-validator/v1",
                objective=context.business_objective,
                model_provider="rule-based-baseline",
                model_name="deterministic-baseline",
                status=ProposalStatus.VALID,
                candidates=[no_offer],
                selected_candidate=no_offer,
                total_candidates=1,
                valid_candidates_count=1,
                rejected_candidates_count=0,
                is_provisional=True,
                context_snapshot_at=context.generated_at,
                generation_timestamp=now,
                created_at=now
            )

        candidates: List[PolicyCandidate] = []

        # Candidate 1: Best Single Product
        primary_item = eligible[0]
        cand1 = PolicyCandidate(
            candidate_id=f"cand_base_single_{primary_item.id}",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=[primary_item.id],
            bundle_components=[{"product_id": primary_item.id, "quantity": intent.quantity or 1}],
            positioning="Standard catalog recommendation.",
            rationale=f"Primary eligible product '{primary_item.name}' matches buyer category.",
            confidence=ConfidenceLevel.HIGH,
            evidence=[
                PolicyEvidence(
                    evidence_type="merchant_attribute",
                    field="category",
                    description=f"Product category is '{primary_item.category}'"
                )
            ]
        )
        cand1 = self.validator.validate_candidate(cand1, intent, context)
        cand1 = self.scorer.score_candidate(cand1, intent, context)
        candidates.append(cand1)

        # Candidate 2: Complementary Bundle (if relationship exists)
        complements = get_complementary_products(primary_item.id, context)
        if complements:
            addon = complements[0]
            cand2 = PolicyCandidate(
                candidate_id=f"cand_base_bundle_{primary_item.id}_{addon.id}",
                strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
                product_ids=[primary_item.id, addon.id],
                bundle_components=[
                    {"product_id": primary_item.id, "quantity": intent.quantity or 1},
                    {"product_id": addon.id, "quantity": 1}
                ],
                positioning="Complementary accessories bundle.",
                rationale=f"Bundles primary item '{primary_item.name}' with complementary '{addon.name}'.",
                confidence=ConfidenceLevel.HIGH,
                evidence=[
                    PolicyEvidence(
                        evidence_type="merchant_relationship",
                        field="COMPLEMENTARY",
                        description=f"{primary_item.name} has complementary relationship with {addon.name}"
                    )
                ]
            )
            cand2 = self.validator.validate_candidate(cand2, intent, context)
            cand2 = self.scorer.score_candidate(cand2, intent, context)
            candidates.append(cand2)

        # Rank candidates
        ranked = self.scorer.rank_candidates(candidates, context)
        approved = [c for c in ranked if c.validation_status == CandidateValidationStatus.APPROVED]

        now = datetime.now(timezone.utc)
        if approved:
            status = ProposalStatus.APPROVED_FOR_EVALUATION
            selected = approved[0]
        else:
            # Safe NO_OFFER fallback if neither candidate approved
            fallback = PolicyCandidate(
                candidate_id="cand_base_fallback_no_offer",
                strategy_type=StrategyType.NO_OFFER,
                product_ids=[],
                rationale="Baseline candidates failed deterministic validation.",
                confidence=ConfidenceLevel.HIGH,
                validation_status=CandidateValidationStatus.APPROVED
            )
            ranked.append(fallback)
            selected = fallback
            status = ProposalStatus.VALID
            approved = [fallback]

        return PolicyProposal(
            proposal_id=proposal_id,
            merchant_id=context.merchant_id,
            policy_version="merchant-policy/v1",
            prompt_version="deterministic-baseline/v1",
            intent_version=getattr(intent, "schema_version", "buyer-intent/v1") or "buyer-intent/v1",
            context_version="commerce-context/v1",
            validator_version="deterministic-validator/v1",
            objective=context.business_objective,
            model_provider="rule-based-baseline",
            model_name="deterministic-baseline",
            status=status,
            candidates=ranked,
            selected_candidate=selected,
            total_candidates=len(ranked),
            valid_candidates_count=len(approved),
            rejected_candidates_count=len(ranked) - len(approved),
            is_provisional=True,
            context_snapshot_at=context.generated_at,
            generation_timestamp=now,
            created_at=now
        )
