"""Service Layer for Constrained Exploration / Exploitation Engine.

Contract: policy-exploration/v1
Handles:
- Database transaction management & optimistic/pessimistic concurrency locking.
- State-aware idempotency on (merchant_id, opportunity_id).
- Safe integration with Phase 8.5 (Selection) and Phase 8.6 (Safety Gate).
- Deterministic fallback when an exploratory candidate fails Phase 8.6.
- Tenant isolation and audit log persistence.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from domain.models import (
    Merchant,
    MerchantExplorationState,
    ExplorationDecisionRecord,
    PolicyMemoryRecord
)
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.policy.schemas import PolicyCandidate
from services.selection.schemas import (
    PolicySelectionRequest,
    PolicySelectionResult,
    CandidateSelectionScore
)
from services.selection.service import PolicySelectionService
from services.safety.schemas import (
    PolicySafetyRequest,
    PolicySafetyStatus,
    SAFETY_SCHEMA_VERSION
)
from services.safety.service import PolicySafetyService
from services.exploration.schemas import (
    EXPLORATION_SCHEMA_VERSION,
    ExplorationRequest,
    ExplorationDecision,
    ExplorationMode,
    ExplorationReasonCode,
    MerchantExplorationConfig
)
from services.exploration.engine import ExplorationEngine
from services.exploration.errors import (
    IncompatibleExplorationVersionError,
    MerchantExplorationIsolationError,
    ExplorationDecisionNotFoundError
)

logger = structlog.get_logger()


class PolicyExplorationService:
    """Authoritative service for Phase 8.7 exploration/exploitation decisions."""

    @classmethod
    async def decide_exploration(
        cls,
        db: AsyncSession,
        request: ExplorationRequest
    ) -> ExplorationDecision:
        """Deterministically choose between exploiting learned preference or bounded exploration."""
        # 1. Contract Version Validation
        if request.exploration_version != EXPLORATION_SCHEMA_VERSION:
            raise IncompatibleExplorationVersionError(
                f"Incompatible exploration version '{request.exploration_version}'. Expected '{EXPLORATION_SCHEMA_VERSION}'."
            )

        config = request.config or MerchantExplorationConfig()
        candidate_map: Dict[str, PolicyCandidate] = {c.candidate_id: c for c in request.candidates}

        # 2. Idempotency Check on (merchant_id, opportunity_id)
        stmt_idemp = select(ExplorationDecisionRecord).where(
            and_(
                ExplorationDecisionRecord.merchant_id == request.merchant_id,
                ExplorationDecisionRecord.opportunity_id == request.opportunity_id
            )
        )
        existing = (await db.execute(stmt_idemp)).scalar_one_or_none()
        if existing:
            # Reconstruct stored decision without re-evaluating or re-consuming budget
            chosen_cand = candidate_map.get(existing.selected_policy_id)
            if not chosen_cand:
                # Fallback placeholder if candidate map omitted on retrieval
                from services.policy.schemas import StrategyType, CandidateValidationStatus
                chosen_cand = PolicyCandidate(
                    candidate_id=existing.selected_policy_id,
                    strategy_type=StrategyType.SINGLE_PRODUCT,
                    product_ids=[],
                    validation_status=CandidateValidationStatus.APPROVED,
                    rationale="Idempotent retrieved decision"
                )

            return ExplorationDecision(
                decision_id=existing.id,
                merchant_id=existing.merchant_id,
                opportunity_id=existing.opportunity_id,
                buyer_context_key=existing.buyer_context_key,
                mode=ExplorationMode(existing.mode),
                exploit_policy_id=existing.exploit_policy_id,
                exploit_policy_version=existing.exploit_policy_version,
                selected_policy_id=existing.selected_policy_id,
                selected_policy_version=existing.selected_policy_version,
                selected_policy=chosen_cand,
                predicted_contribution_paise=existing.predicted_contribution_paise,
                uncertainty=existing.uncertainty,
                ucb_score_paise=existing.ucb_score_paise,
                exposure_paise=getattr(existing, "exposure_paise", 0) or 0,
                reason_code=ExplorationReasonCode(existing.reason_code),
                safety_check_reference=existing.safety_check_id,
                exploration_budget_state=existing.budget_state_json,
                policy_exposure_state=existing.policy_exposure_state_json,
                context_exposure_state=existing.context_exposure_state_json,
                model_version=existing.model_version,
                feature_version=existing.feature_version,
                selection_version=existing.selection_version,
                exploration_version=existing.exploration_version,
                config_version=existing.budget_state_json.get("config_version", "exp-config/v1") if isinstance(existing.budget_state_json, dict) else "exp-config/v1",
                decision_timestamp=existing.created_at
            )

        # 3. Verify Merchant Exists
        merch_res = await db.execute(select(Merchant).where(Merchant.id == request.merchant_id))
        merchant = merch_res.scalar_one_or_none()
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{request.merchant_id}' not found.")

        # 4. Resolve Canonical UTC Exploration Window & Lock/Initialize State
        now_utc = datetime.now(timezone.utc)
        resolved_window_id = config.resolve_window_id(now_utc)

        stmt_state = (
            select(MerchantExplorationState)
            .where(
                and_(
                    MerchantExplorationState.merchant_id == request.merchant_id,
                    MerchantExplorationState.window_id == resolved_window_id
                )
            )
            .with_for_update()
        )
        state_record = (await db.execute(stmt_state)).scalar_one_or_none()
        if not state_record:
            state_record = MerchantExplorationState(
                id=f"exp_state_{request.merchant_id}_{resolved_window_id}",
                merchant_id=request.merchant_id,
                window_id=resolved_window_id,
                opportunities_used=0,
                exposure_paise_used=0,
                consecutive_explorations=0,
                policy_counts_json={},
                context_counts_json={},
                version=1
            )
            db.add(state_record)
            await db.flush()

        # Capture before-decision audit snapshot
        opportunities_used_before = state_record.opportunities_used
        exposure_paise_used_before = state_record.exposure_paise_used
        consecutive_before = state_record.consecutive_explorations

        # 5. Resolve Phase 8.5 Selection Result
        selection_result = request.selection_result
        if not selection_result:
            selection_req = PolicySelectionRequest(
                merchant_id=request.merchant_id,
                opportunity_id=request.opportunity_id,
                buyer_context_key=request.buyer_context_key,
                intent=request.intent,
                candidates=request.candidates
            )
            selection_result = await PolicySelectionService.select_policy(db, selection_req)

        # Ensure canonical baseline is in candidate map if returned by selection
        for cand in request.candidates:
            candidate_map[cand.candidate_id] = cand

        from services.selection.ranking import CANONICAL_BASELINE_POLICY_ID, PolicyCandidateSelector
        if CANONICAL_BASELINE_POLICY_ID not in candidate_map:
            candidate_map[CANONICAL_BASELINE_POLICY_ID] = PolicyCandidateSelector.create_canonical_no_offer_baseline()

        # 6. Retrieve Historical Observation Evidence Counts
        stmt_obs = (
            select(PolicyMemoryRecord.policy_id, func.count(PolicyMemoryRecord.id))
            .where(PolicyMemoryRecord.merchant_id == request.merchant_id)
            .group_by(PolicyMemoryRecord.policy_id)
        )
        obs_rows = (await db.execute(stmt_obs)).all()
        evidence_counts = {r[0]: int(r[1]) for r in obs_rows}

        # Build current state dictionary
        state_dict = {
            "opportunities_used": state_record.opportunities_used,
            "exposure_paise_used": state_record.exposure_paise_used,
            "consecutive_explorations": state_record.consecutive_explorations,
            "policy_counts_json": dict(state_record.policy_counts_json),
            "context_counts_json": dict(state_record.context_counts_json)
        }

        # 7. Evaluate Exploration vs Exploitation Engine
        mode, chosen_cand, chosen_score, chosen_exposure, reason, diagnostic = ExplorationEngine.evaluate_exploration(
            selection_result=selection_result,
            candidate_map=candidate_map,
            config=config,
            state_dict=state_dict,
            evidence_counts=evidence_counts
        )

        exploit_cand = candidate_map.get(selection_result.selected_policy_id)

        # 8. Integrate with Phase 8.6 Safety Gate & Fallback Handling
        safety_check_ref: Optional[str] = None
        final_policy = chosen_cand
        final_mode = mode
        final_reason = reason
        committed_exposure_paise: int = 0
        pred_paise = chosen_score.predicted_contribution_paise if chosen_score else selection_result.selected_predicted_contribution_paise
        uncertainty_val = chosen_score.uncertainty if chosen_score else selection_result.selected_uncertainty
        ucb_paise = pred_paise + int(round(config.alpha_paise * uncertainty_val))

        if mode == ExplorationMode.EXPLORE and chosen_cand:
            # Validate exploratory candidate against Phase 8.6
            safety_req = PolicySafetyRequest(
                merchant_id=request.merchant_id,
                opportunity_id=request.opportunity_id,
                buyer_context_key=request.buyer_context_key,
                proposed_policy=chosen_cand,
                proposed_policy_version=getattr(chosen_cand, "policy_version", "merchant-policy/v1") or "merchant-policy/v1",
                selection_id=selection_result.selection_id,
                intent=request.intent,
                safety_version=SAFETY_SCHEMA_VERSION
            )
            safety_res = await PolicySafetyService.validate_policy(db, safety_req)

            if safety_res.status == PolicySafetyStatus.ADMISSIBLE:
                # Exploratory candidate is SAFE! Consume budget atomically.
                safety_check_ref = safety_res.safety_check_id
                state_record.opportunities_used += 1
                state_record.consecutive_explorations += 1

                # Update exact downside exposure paise
                state_record.exposure_paise_used += chosen_exposure
                committed_exposure_paise = chosen_exposure

                # Update per-policy and per-context counts
                p_counts = dict(state_record.policy_counts_json)
                p_counts[chosen_cand.candidate_id] = p_counts.get(chosen_cand.candidate_id, 0) + 1
                state_record.policy_counts_json = p_counts

                c_counts = dict(state_record.context_counts_json)
                c_counts[request.buyer_context_key] = c_counts.get(request.buyer_context_key, 0) + 1
                state_record.context_counts_json = c_counts

                state_record.version += 1
                final_policy = chosen_cand
                final_mode = ExplorationMode.EXPLORE
                final_reason = reason
            else:
                # Exploratory candidate is REJECTED by Phase 8.6!
                # Trigger deterministic fallback to exploit candidate!
                # Zero exposure is consumed!
                committed_exposure_paise = 0
                final_mode = ExplorationMode.EXPLOIT
                final_reason = ExplorationReasonCode.EXPLOIT_FALLBACK_EXPLORATION_UNSAFE
                final_policy = exploit_cand
                pred_paise = selection_result.selected_predicted_contribution_paise
                uncertainty_val = selection_result.selected_uncertainty
                ucb_paise = pred_paise + int(round(config.alpha_paise * uncertainty_val))

                # Validate fallback exploit candidate
                if exploit_cand:
                    safety_req_exploit = PolicySafetyRequest(
                        merchant_id=request.merchant_id,
                        opportunity_id=request.opportunity_id,
                        buyer_context_key=request.buyer_context_key,
                        proposed_policy=exploit_cand,
                        proposed_policy_version=getattr(exploit_cand, "policy_version", "merchant-policy/v1") or "merchant-policy/v1",
                        selection_id=selection_result.selection_id,
                        intent=request.intent,
                        safety_version=SAFETY_SCHEMA_VERSION
                    )
                    safety_res_exploit = await PolicySafetyService.validate_policy(db, safety_req_exploit)
                    safety_check_ref = safety_res_exploit.safety_check_id

                # Reset consecutive counter on exploit fallback; do not consume budget
                state_record.consecutive_explorations = 0
                state_record.version += 1

        else:
            # Mode is EXPLOIT: validate exploit candidate with Phase 8.6
            final_mode = ExplorationMode.EXPLOIT
            final_policy = exploit_cand
            final_reason = reason
            committed_exposure_paise = 0
            pred_paise = selection_result.selected_predicted_contribution_paise
            uncertainty_val = selection_result.selected_uncertainty
            ucb_paise = pred_paise + int(round(config.alpha_paise * uncertainty_val))

            if exploit_cand:
                safety_req_exploit = PolicySafetyRequest(
                    merchant_id=request.merchant_id,
                    opportunity_id=request.opportunity_id,
                    buyer_context_key=request.buyer_context_key,
                    proposed_policy=exploit_cand,
                    proposed_policy_version=getattr(exploit_cand, "policy_version", "merchant-policy/v1") or "merchant-policy/v1",
                    selection_id=selection_result.selection_id,
                    intent=request.intent,
                    safety_version=SAFETY_SCHEMA_VERSION
                )
                safety_res_exploit = await PolicySafetyService.validate_policy(db, safety_req_exploit)
                safety_check_ref = safety_res_exploit.safety_check_id

            # Reset consecutive exploration counter
            state_record.consecutive_explorations = 0
            state_record.version += 1

        # 9. Persist Exploration Decision Record
        decision_id = f"exp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        budget_snapshot = {
            "window_id": resolved_window_id,
            "window_start_utc": f"{resolved_window_id[4:]}T00:00:00Z" if resolved_window_id.startswith("win_") else None,
            "window_end_utc": f"{resolved_window_id[4:]}T23:59:59.999999Z" if resolved_window_id.startswith("win_") else None,
            "opportunities_used": state_record.opportunities_used,
            "opportunities_used_before": opportunities_used_before,
            "opportunities_used_after": state_record.opportunities_used,
            "max_opportunities": config.max_exploration_opportunities,
            "exposure_paise_used": state_record.exposure_paise_used,
            "exposure_paise_used_before": exposure_paise_used_before,
            "exposure_paise_used_after": state_record.exposure_paise_used,
            "max_exposure_paise": config.max_exposure_paise,
            "max_exposure_per_decision_paise": config.max_exposure_per_decision_paise,
            "max_underobserved_deficit_paise": config.max_underobserved_deficit_paise,
            "consecutive_explorations": state_record.consecutive_explorations,
            "consecutive_explorations_before": consecutive_before,
            "consecutive_explorations_after": state_record.consecutive_explorations,
            "max_consecutive": config.max_consecutive_explorations,
            "config_version": config.config_version
        }

        record = ExplorationDecisionRecord(
            id=decision_id,
            merchant_id=request.merchant_id,
            opportunity_id=request.opportunity_id,
            buyer_context_key=request.buyer_context_key,
            mode=final_mode.value,
            exploit_policy_id=selection_result.selected_policy_id,
            exploit_policy_version=selection_result.selected_policy_version,
            selected_policy_id=final_policy.candidate_id if final_policy else selection_result.selected_policy_id,
            selected_policy_version=getattr(final_policy, "policy_version", "merchant-policy/v1") if final_policy else "merchant-policy/v1",
            predicted_contribution_paise=pred_paise,
            uncertainty=uncertainty_val,
            ucb_score_paise=ucb_paise,
            exposure_paise=committed_exposure_paise,
            reason_code=final_reason.value,
            safety_check_id=safety_check_ref,
            budget_state_json=budget_snapshot,
            policy_exposure_state_json=dict(state_record.policy_counts_json),
            context_exposure_state_json=dict(state_record.context_counts_json),
            model_version=selection_result.model_version,
            feature_version=selection_result.feature_version,
            selection_version=selection_result.selection_version,
            exploration_version=EXPLORATION_SCHEMA_VERSION,
            created_at=now
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return ExplorationDecision(
            decision_id=record.id,
            merchant_id=record.merchant_id,
            opportunity_id=record.opportunity_id,
            buyer_context_key=record.buyer_context_key,
            mode=final_mode,
            exploit_policy_id=record.exploit_policy_id,
            exploit_policy_version=record.exploit_policy_version,
            selected_policy_id=record.selected_policy_id,
            selected_policy_version=record.selected_policy_version,
            selected_policy=final_policy,
            predicted_contribution_paise=record.predicted_contribution_paise,
            uncertainty=record.uncertainty,
            ucb_score_paise=record.ucb_score_paise,
            exposure_paise=record.exposure_paise,
            exploration_trigger=diagnostic.get("trigger_name"),
            reason_code=final_reason,
            safety_check_reference=record.safety_check_id,
            exploration_budget_state=record.budget_state_json,
            policy_exposure_state=record.policy_exposure_state_json,
            context_exposure_state=record.context_exposure_state_json,
            model_version=record.model_version,
            feature_version=record.feature_version,
            selection_version=record.selection_version,
            exploration_version=record.exploration_version,
            config_version=config.config_version,
            decision_timestamp=record.created_at
        )

    @classmethod
    async def get_decision(
        cls,
        db: AsyncSession,
        decision_id: str,
        merchant_id: str
    ) -> ExplorationDecision:
        """Fetch historical exploration decision with strict merchant tenant isolation."""
        stmt = select(ExplorationDecisionRecord).where(ExplorationDecisionRecord.id == decision_id)
        record = (await db.execute(stmt)).scalar_one_or_none()

        if not record:
            raise ExplorationDecisionNotFoundError(f"Exploration decision '{decision_id}' not found.")

        if record.merchant_id != merchant_id:
            raise MerchantExplorationIsolationError(
                f"Merchant '{merchant_id}' is not authorized to view decision '{decision_id}'."
            )

        from services.policy.schemas import StrategyType, CandidateValidationStatus
        placeholder_cand = PolicyCandidate(
            candidate_id=record.selected_policy_id,
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=[],
            validation_status=CandidateValidationStatus.APPROVED,
            rationale="Retrieved historical decision"
        )

        cfg_ver = "exp-config/v1"
        if isinstance(record.budget_state_json, dict):
            cfg_ver = record.budget_state_json.get("config_version", "exp-config/v1")

        return ExplorationDecision(
            decision_id=record.id,
            merchant_id=record.merchant_id,
            opportunity_id=record.opportunity_id,
            buyer_context_key=record.buyer_context_key,
            mode=ExplorationMode(record.mode),
            exploit_policy_id=record.exploit_policy_id,
            exploit_policy_version=record.exploit_policy_version,
            selected_policy_id=record.selected_policy_id,
            selected_policy_version=record.selected_policy_version,
            selected_policy=placeholder_cand,
            predicted_contribution_paise=record.predicted_contribution_paise,
            uncertainty=record.uncertainty,
            ucb_score_paise=record.ucb_score_paise,
            exposure_paise=getattr(record, "exposure_paise", 0) or 0,
            reason_code=ExplorationReasonCode(record.reason_code),
            safety_check_reference=record.safety_check_id,
            exploration_budget_state=record.budget_state_json,
            policy_exposure_state=record.policy_exposure_state_json,
            context_exposure_state=record.context_exposure_state_json,
            model_version=record.model_version,
            feature_version=record.feature_version,
            selection_version=record.selection_version,
            exploration_version=record.exploration_version,
            config_version=cfg_ver,
            decision_timestamp=record.created_at
        )
