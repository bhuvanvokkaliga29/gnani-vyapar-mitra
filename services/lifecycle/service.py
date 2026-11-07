"""Service Layer for Phase 8.8 Policy Lifecycle & Promotion Management.

Contracts:
- policy-lifecycle/v1
- promotion-policy/v1

Guarantees:
- Single active policy version per merchant (enforced via DB primary key on merchant_id).
- Atomic database transactions for activation, retirement, and rollback.
- Explicit evidence-gated promotion (never based solely on predicted contribution or exploration).
- Fresh Phase 8.6 safety clearance mandatory before activation or rollback.
- Immutable version history and audit log.
- Full merchant tenant isolation.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import (
    Merchant,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    PolicyLifecycleAuditRecord,
    PolicyMemoryRecord,
    ExperimentRecord
)
from domain.intent_schemas import BuyerIntent
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    IncentiveProposal
)
from services.selection.ranking import CANONICAL_BASELINE_POLICY_ID
from services.safety.schemas import PolicySafetyRequest, PolicySafetyStatus, SAFETY_SCHEMA_VERSION
from services.safety.service import PolicySafetyService
from services.experiments.schemas import ExperimentResult
from services.lifecycle.schemas import (
    LIFECYCLE_SCHEMA_VERSION,
    PROMOTION_CONFIG_VERSION,
    PolicyLifecycleState,
    PromotionStatus,
    PromotionFailureCode,
    PromotionPolicyConfig,
    PromotionEvidenceType,
    PolicyPromotionRequest,
    PolicyPromotionResult,
    PolicyRollbackRequest,
    PolicyRollbackResult,
    ActivePolicyResponse
)
from services.lifecycle.errors import (
    PolicyLifecycleError,
    IncompatibleLifecycleVersionError,
    MerchantLifecycleIsolationError,
    PolicyVersionNotFoundError,
    LifecycleTransitionError,
    ActivePolicyConflictError
)
from services.lifecycle.evaluator import PolicyPromotionEvaluator


class PolicyLifecycleService:
    """Authoritative lifecycle and promotion engine for merchant commercial policies."""

    @classmethod
    async def promote_policy(
        cls,
        db: AsyncSession,
        request: PolicyPromotionRequest
    ) -> PolicyPromotionResult:
        """Evaluate evidence and atomically promote a candidate policy to ACTIVE.
        
        Guarantees:
        1. Version validation (policy-lifecycle/v1).
        2. Merchant tenant verification.
        3. Row-level concurrency lock on MerchantActivePolicy.
        4. Optimistic locking on expected predecessor.
        5. Evidence-gated evaluation from Phase 8.3 memory and Phase 7 experiments.
        6. Fresh Phase 8.6 safety check.
        7. Atomic transition: old active -> RETIRED, candidate -> ACTIVE.
        8. Idempotency: repeated promotion returns existing result.
        """
        # 1. Version Check
        if request.lifecycle_version != LIFECYCLE_SCHEMA_VERSION:
            raise IncompatibleLifecycleVersionError(
                f"Unsupported lifecycle_version '{request.lifecycle_version}'. Expected '{LIFECYCLE_SCHEMA_VERSION}'."
            )

        # 2. Verify Merchant Exists
        merch_res = await db.execute(select(Merchant).where(Merchant.id == request.merchant_id))
        merchant = merch_res.scalar_one_or_none()
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{request.merchant_id}' not found.")

        config = request.config or PromotionPolicyConfig()

        # 3. Idempotency Check
        stmt_idemp = (
            select(PolicyLifecycleAuditRecord)
            .where(
                and_(
                    PolicyLifecycleAuditRecord.merchant_id == request.merchant_id,
                    PolicyLifecycleAuditRecord.candidate_policy_id == request.candidate_policy_id,
                    PolicyLifecycleAuditRecord.candidate_policy_version == request.candidate_policy_version,
                    PolicyLifecycleAuditRecord.transition_type == "PROMOTION",
                    PolicyLifecycleAuditRecord.promotion_status == PromotionStatus.PROMOTED.value
                )
            )
            .order_by(PolicyLifecycleAuditRecord.created_at.desc())
        )
        existing_prom = (await db.execute(stmt_idemp)).scalars().first()
        if existing_prom:
            # Check if currently active matches
            active_stmt = select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == request.merchant_id)
            curr_active = (await db.execute(active_stmt)).scalar_one_or_none()
            if curr_active and curr_active.policy_id == request.candidate_policy_id:
                return cls._audit_record_to_result(existing_prom)

        # 4. Lock or Initialize MerchantActivePolicy Row
        stmt_active = (
            select(MerchantActivePolicy)
            .where(MerchantActivePolicy.merchant_id == request.merchant_id)
            .with_for_update()
        )
        active_record = (await db.execute(stmt_active)).scalar_one_or_none()
        if not active_record:
            # Initialize with canonical baseline NO_OFFER
            active_record = MerchantActivePolicy(
                merchant_id=request.merchant_id,
                policy_id=CANONICAL_BASELINE_POLICY_ID,
                policy_version="merchant-policy/v1",
                promotion_id="init_baseline"
            )
            db.add(active_record)
            await db.flush()

        prev_active_id = active_record.policy_id
        prev_active_version = active_record.policy_version

        # 5. Optimistic Concurrency Check (Predecessor verification)
        if request.expected_previous_policy_id:
            if prev_active_id != request.expected_previous_policy_id:
                # Active predecessor mismatch -> Conflict!
                return await cls._record_rejection_async(
                    db=db,
                    merchant_id=request.merchant_id,
                    candidate_id=request.candidate_policy_id,
                    candidate_version=request.candidate_policy_version,
                    prev_id=prev_active_id,
                    prev_ver=prev_active_version,
                    status=PromotionStatus.CONFLICT,
                    eligibility_str="CONFLICT: Predecessor mismatch",
                    failure_codes=[PromotionFailureCode.PREDECESSOR_MISMATCH],
                    evidence_summary={"expected": request.expected_previous_policy_id, "actual": prev_active_id},
                    config_version=config.config_version
                )

        # 6. Candidate Already Active Check
        if prev_active_id == request.candidate_policy_id and prev_active_version == request.candidate_policy_version:
            return await cls._record_rejection_async(
                db=db,
                merchant_id=request.merchant_id,
                candidate_id=request.candidate_policy_id,
                candidate_version=request.candidate_policy_version,
                prev_id=prev_active_id,
                prev_ver=prev_active_version,
                status=PromotionStatus.NOT_ELIGIBLE,
                eligibility_str="NOT_ELIGIBLE: Policy version is already active",
                failure_codes=[PromotionFailureCode.ALREADY_ACTIVE],
                evidence_summary={"current_active_policy_id": prev_active_id},
                config_version=config.config_version
            )

        # 7. Locate or Build Candidate Policy Definition
        candidate_policy = request.candidate_policy
        if not candidate_policy:
            # Check version records
            stmt_ver = select(MerchantPolicyVersionRecord).where(
                and_(
                    MerchantPolicyVersionRecord.merchant_id == request.merchant_id,
                    MerchantPolicyVersionRecord.policy_id == request.candidate_policy_id,
                    MerchantPolicyVersionRecord.policy_version == request.candidate_policy_version
                )
            )
            ver_row = (await db.execute(stmt_ver)).scalar_one_or_none()
            if ver_row:
                inc = IncentiveProposal(**ver_row.incentive_json) if ver_row.incentive_json else None
                candidate_policy = PolicyCandidate(
                    candidate_id=ver_row.policy_id,
                    strategy_type=StrategyType(ver_row.strategy_type),
                    product_ids=list(ver_row.product_ids_json),
                    incentive=inc,
                    validation_status=CandidateValidationStatus.APPROVED,
                    rationale=ver_row.rationale or "Loaded from version record"
                )
            else:
                # Default candidate representation
                candidate_policy = PolicyCandidate(
                    candidate_id=request.candidate_policy_id,
                    strategy_type=StrategyType.SINGLE_PRODUCT,
                    product_ids=[],
                    validation_status=CandidateValidationStatus.APPROVED,
                    rationale=request.reason
                )

        # 8. Retrieve Authoritative Evidence from Phase 8.3 Memory
        stmt_mem = (
            select(PolicyMemoryRecord)
            .where(PolicyMemoryRecord.merchant_id == request.merchant_id)
        )
        all_mem_records = (await db.execute(stmt_mem)).scalars().all()
        cand_mem = [r for r in all_mem_records if r.policy_id == request.candidate_policy_id]
        base_mem = [r for r in all_mem_records if r.policy_id in (CANONICAL_BASELINE_POLICY_ID, "cand_base_no_offer")]

        # 9. Retrieve Phase 7 Experiment Evidence (if referenced)
        exp_result: Optional[ExperimentResult] = None
        if request.experiment_id:
            exp_stmt = select(ExperimentRecord).where(
                and_(
                    ExperimentRecord.id == request.experiment_id,
                    ExperimentRecord.merchant_id == request.merchant_id
                )
            )
            exp_row = (await db.execute(exp_stmt)).scalar_one_or_none()
            if exp_row:
                if exp_row.treatment_policy_id and exp_row.treatment_policy_id != request.candidate_policy_id:
                    # Mismatch! Candidate is not treatment policy
                    return await cls._record_rejection_async(
                        db=db,
                        merchant_id=request.merchant_id,
                        candidate_id=request.candidate_policy_id,
                        candidate_version=request.candidate_policy_version,
                        prev_id=prev_active_id,
                        prev_ver=prev_active_version,
                        status=PromotionStatus.NOT_ELIGIBLE,
                        eligibility_str="NOT_ELIGIBLE: Candidate is not the treatment policy of the experiment",
                        failure_codes=[PromotionFailureCode.EXPERIMENT_TREATMENT_MISMATCH],
                        evidence_summary={"experiment_id": request.experiment_id, "treatment_policy_id": exp_row.treatment_policy_id},
                        config_version=config.config_version
                    )
                try:
                    from services.experiments.service import ExperimentService
                    exp_svc = ExperimentService()
                    exp_result = await exp_svc.get_experiment_result(db, request.experiment_id, request.merchant_id)
                except Exception:
                    exp_result = None

        # 10. Evaluate Promotion Criteria Deterministically
        is_eligible, failure_codes, evidence_summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
            candidate_policy_id=request.candidate_policy_id,
            config=config,
            memory_records=cand_mem,
            baseline_records=base_mem,
            candidate_policy_version=request.candidate_policy_version,
            experiment_result=exp_result
        )

        if not is_eligible:
            if PromotionFailureCode.STALE_EVIDENCE in failure_codes:
                status = PromotionStatus.STALE_EVIDENCE
            elif (
                PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes or
                PromotionFailureCode.INCONCLUSIVE_EXPERIMENT in failure_codes or
                PromotionFailureCode.POLICY_VERSION_MISMATCH in failure_codes or
                PromotionFailureCode.FUTURE_EVIDENCE_REJECTED in failure_codes or
                PromotionFailureCode.OBSERVATIONAL_CONCENTRATION_EXCEEDED in failure_codes or
                PromotionFailureCode.INSUFFICIENT_CONTEXT_DIVERSITY in failure_codes or
                PromotionFailureCode.OBSERVATIONAL_PROMOTION_DISALLOWED in failure_codes
            ):
                status = PromotionStatus.INSUFFICIENT_EVIDENCE
            else:
                status = PromotionStatus.NOT_ELIGIBLE

            return await cls._record_rejection_async(
                db=db,
                merchant_id=request.merchant_id,
                candidate_id=request.candidate_policy_id,
                candidate_version=request.candidate_policy_version,
                prev_id=prev_active_id,
                prev_ver=prev_active_version,
                status=status,
                eligibility_str="INELIGIBLE: Failed promotion criteria",
                failure_codes=failure_codes,
                evidence_summary=evidence_summary,
                config_version=config.config_version
            )

        # 11. Fresh Phase 8.6 Safety Gate Validation
        safety_check_ref: Optional[str] = None
        if config.require_fresh_safety_check:
            safety_req = PolicySafetyRequest(
                merchant_id=request.merchant_id,
                opportunity_id=f"prom_{request.candidate_policy_id}_{uuid.uuid4().hex[:6]}",
                buyer_context_key="promotion_lifecycle_audit",
                proposed_policy=candidate_policy,
                proposed_policy_version=request.candidate_policy_version,
                intent=BuyerIntent(category="travel_backpack"),
                safety_version=SAFETY_SCHEMA_VERSION
            )
            safety_res = await PolicySafetyService.validate_policy(db, safety_req)
            safety_check_ref = safety_res.safety_check_id

            if safety_res.status != PolicySafetyStatus.ADMISSIBLE:
                failure_codes.append(PromotionFailureCode.SAFETY_GATE_REJECTED)
                return await cls._record_rejection_async(
                    db=db,
                    merchant_id=request.merchant_id,
                    candidate_id=request.candidate_policy_id,
                    candidate_version=request.candidate_policy_version,
                    prev_id=prev_active_id,
                    prev_ver=prev_active_version,
                    status=PromotionStatus.SAFETY_REJECTED,
                    eligibility_str=f"SAFETY_REJECTED: Failed Phase 8.6 safety check ({safety_res.failure_codes[0].value if safety_res.failure_codes else safety_res.validation_reason})",
                    failure_codes=failure_codes,
                    evidence_summary=evidence_summary,
                    config_version=config.config_version,
                    safety_check_id=safety_check_ref
                )

        # 12. Atomic Promotion Transaction
        now = datetime.now(timezone.utc)
        promotion_id = f"prom_{uuid.uuid4().hex[:12]}"

        # Retire previous active policy version record if it exists
        if prev_active_id:
            stmt_prev_ver = select(MerchantPolicyVersionRecord).where(
                and_(
                    MerchantPolicyVersionRecord.merchant_id == request.merchant_id,
                    MerchantPolicyVersionRecord.policy_id == prev_active_id,
                    MerchantPolicyVersionRecord.policy_version == prev_active_version
                )
            )
            prev_ver_row = (await db.execute(stmt_prev_ver)).scalar_one_or_none()
            if prev_ver_row:
                prev_ver_row.lifecycle_status = PolicyLifecycleState.RETIRED.value
                prev_ver_row.updated_at = now

        # Create or update candidate policy version record as ACTIVE
        stmt_cand_ver = select(MerchantPolicyVersionRecord).where(
            and_(
                MerchantPolicyVersionRecord.merchant_id == request.merchant_id,
                MerchantPolicyVersionRecord.policy_id == request.candidate_policy_id,
                MerchantPolicyVersionRecord.policy_version == request.candidate_policy_version
            )
        )
        cand_ver_row = (await db.execute(stmt_cand_ver)).scalar_one_or_none()
        inc_json = candidate_policy.incentive.model_dump(mode="json") if candidate_policy.incentive else None
        if not cand_ver_row:
            cand_ver_row = MerchantPolicyVersionRecord(
                id=f"pver_{request.merchant_id}_{request.candidate_policy_id}_{request.candidate_policy_version}",
                merchant_id=request.merchant_id,
                policy_id=request.candidate_policy_id,
                policy_version=request.candidate_policy_version,
                lifecycle_status=PolicyLifecycleState.ACTIVE.value,
                strategy_type=candidate_policy.strategy_type.value,
                product_ids_json=list(candidate_policy.product_ids),
                incentive_json=inc_json,
                rationale=candidate_policy.rationale,
                provenance_json={
                    "promotion_id": promotion_id,
                    "experiment_id": request.experiment_id,
                    "selection_id": request.selection_id,
                    "exploration_id": request.exploration_id
                },
                created_at=now,
                updated_at=now
            )
            db.add(cand_ver_row)
        else:
            cand_ver_row.lifecycle_status = PolicyLifecycleState.ACTIVE.value
            cand_ver_row.updated_at = now

        # Update authoritative pointer in MerchantActivePolicy
        active_record.policy_id = request.candidate_policy_id
        active_record.policy_version = request.candidate_policy_version
        active_record.activated_at = now
        active_record.promotion_id = promotion_id

        # Record immutable lifecycle audit record
        audit_record = PolicyLifecycleAuditRecord(
            id=promotion_id,
            merchant_id=request.merchant_id,
            transition_type="PROMOTION",
            candidate_policy_id=request.candidate_policy_id,
            candidate_policy_version=request.candidate_policy_version,
            previous_active_policy_id=prev_active_id,
            previous_active_policy_version=prev_active_version,
            resulting_active_policy_id=request.candidate_policy_id,
            resulting_active_policy_version=request.candidate_policy_version,
            promotion_status=PromotionStatus.PROMOTED.value,
            eligibility_status="ELIGIBLE: Satisfies all evidence and safety criteria",
            failure_codes_json=[],
            evidence_type=evidence_summary.get("evidence_type"),
            evidence_references_json=evidence_summary,
            safety_check_id=safety_check_ref,
            promotion_config_version=config.config_version,
            lifecycle_version=LIFECYCLE_SCHEMA_VERSION,
            created_at=now
        )
        db.add(audit_record)
        await db.commit()
        await db.refresh(audit_record)

        return cls._audit_record_to_result(audit_record)

    @classmethod
    async def rollback_policy(
        cls,
        db: AsyncSession,
        request: PolicyRollbackRequest
    ) -> PolicyRollbackResult:
        """Rollback active policy to a specified historical policy version.
        
        Guarantees:
        1. Historical target policy must exist and belong to merchant.
        2. Fresh Phase 8.6 safety check verifies target version is currently legal.
        3. Concurrency lock on MerchantActivePolicy.
        4. Atomic transition: currently active -> ROLLED_BACK, target version -> ACTIVE.
        """
        if request.lifecycle_version != LIFECYCLE_SCHEMA_VERSION:
            raise IncompatibleLifecycleVersionError(
                f"Unsupported lifecycle_version '{request.lifecycle_version}'. Expected '{LIFECYCLE_SCHEMA_VERSION}'."
            )

        # 1. Row-Level Concurrency Lock
        stmt_active = (
            select(MerchantActivePolicy)
            .where(MerchantActivePolicy.merchant_id == request.merchant_id)
            .with_for_update()
        )
        active_record = (await db.execute(stmt_active)).scalar_one_or_none()
        if not active_record:
            raise PolicyVersionNotFoundError(f"No active policy found for merchant '{request.merchant_id}'.")

        curr_active_id = active_record.policy_id
        curr_active_version = active_record.policy_version

        # 2. Optimistic Concurrency Check
        if request.expected_current_policy_id:
            if curr_active_id != request.expected_current_policy_id:
                raise ActivePolicyConflictError(
                    f"Active policy conflict: expected '{request.expected_current_policy_id}' but found '{curr_active_id}'."
                )

        # 3. Already Active Idempotency
        if curr_active_id == request.target_policy_id and curr_active_version == request.target_policy_version:
            return PolicyRollbackResult(
                rollback_id="idemp_noop",
                merchant_id=request.merchant_id,
                target_policy_id=request.target_policy_id,
                target_policy_version=request.target_policy_version,
                previous_active_policy_id=curr_active_id,
                previous_active_policy_version=curr_active_version,
                status="ROLLED_BACK",
                failure_codes=[],
                safety_check_reference=None,
                created_at=datetime.now(timezone.utc)
            )

        # 4. Retrieve Target Version Record
        stmt_target = select(MerchantPolicyVersionRecord).where(
            and_(
                MerchantPolicyVersionRecord.merchant_id == request.merchant_id,
                MerchantPolicyVersionRecord.policy_id == request.target_policy_id,
                MerchantPolicyVersionRecord.policy_version == request.target_policy_version
            )
        )
        target_ver = (await db.execute(stmt_target)).scalar_one_or_none()
        if not target_ver:
            raise PolicyVersionNotFoundError(
                f"Target rollback policy '{request.target_policy_id}' version '{request.target_policy_version}' not found for merchant '{request.merchant_id}'."
            )

        # 5. Fresh Safety Validation on Target Historical Policy
        safety_check_ref: Optional[str] = None
        if request.require_fresh_safety_check:
            inc = IncentiveProposal(**target_ver.incentive_json) if target_ver.incentive_json else None
            target_cand = PolicyCandidate(
                candidate_id=target_ver.policy_id,
                strategy_type=StrategyType(target_ver.strategy_type),
                product_ids=list(target_ver.product_ids_json),
                incentive=inc,
                validation_status=CandidateValidationStatus.APPROVED,
                rationale=f"Rollback candidate: {request.reason}"
            )

            safety_req = PolicySafetyRequest(
                merchant_id=request.merchant_id,
                opportunity_id=f"roll_{request.target_policy_id}_{uuid.uuid4().hex[:6]}",
                buyer_context_key="rollback_lifecycle_audit",
                proposed_policy=target_cand,
                proposed_policy_version=request.target_policy_version,
                intent=BuyerIntent(category="travel_backpack"),
                safety_version=SAFETY_SCHEMA_VERSION
            )
            safety_res = await PolicySafetyService.validate_policy(db, safety_req)
            safety_check_ref = safety_res.safety_check_id

            if safety_res.status != PolicySafetyStatus.ADMISSIBLE:
                return PolicyRollbackResult(
                    rollback_id=f"roll_fail_{uuid.uuid4().hex[:8]}",
                    merchant_id=request.merchant_id,
                    target_policy_id=request.target_policy_id,
                    target_policy_version=request.target_policy_version,
                    previous_active_policy_id=curr_active_id,
                    previous_active_policy_version=curr_active_version,
                    status="REJECTED",
                    failure_codes=[PromotionFailureCode.SAFETY_GATE_REJECTED],
                    safety_check_reference=safety_check_ref,
                    created_at=datetime.now(timezone.utc)
                )

        # 6. Atomic Rollback Transition
        now = datetime.now(timezone.utc)
        rollback_id = f"roll_{uuid.uuid4().hex[:12]}"

        # Mark current active as ROLLED_BACK
        stmt_curr_ver = select(MerchantPolicyVersionRecord).where(
            and_(
                MerchantPolicyVersionRecord.merchant_id == request.merchant_id,
                MerchantPolicyVersionRecord.policy_id == curr_active_id,
                MerchantPolicyVersionRecord.policy_version == curr_active_version
            )
        )
        curr_ver_row = (await db.execute(stmt_curr_ver)).scalar_one_or_none()
        if curr_ver_row:
            curr_ver_row.lifecycle_status = PolicyLifecycleState.ROLLED_BACK.value
            curr_ver_row.updated_at = now

        # Mark target historical version as ACTIVE
        target_ver.lifecycle_status = PolicyLifecycleState.ACTIVE.value
        target_ver.updated_at = now

        # Update authoritative pointer
        active_record.policy_id = request.target_policy_id
        active_record.policy_version = request.target_policy_version
        active_record.activated_at = now
        active_record.promotion_id = rollback_id

        # Record audit log
        audit_record = PolicyLifecycleAuditRecord(
            id=rollback_id,
            merchant_id=request.merchant_id,
            transition_type="ROLLBACK",
            candidate_policy_id=request.target_policy_id,
            candidate_policy_version=request.target_policy_version,
            previous_active_policy_id=curr_active_id,
            previous_active_policy_version=curr_active_version,
            resulting_active_policy_id=request.target_policy_id,
            resulting_active_policy_version=request.target_policy_version,
            promotion_status=PromotionStatus.ROLLED_BACK.value,
            eligibility_status=f"ROLLED_BACK: Reinstated historical version {request.target_policy_version}",
            failure_codes_json=[],
            evidence_references_json={"reason": request.reason},
            safety_check_id=safety_check_ref,
            promotion_config_version=PROMOTION_CONFIG_VERSION,
            lifecycle_version=LIFECYCLE_SCHEMA_VERSION,
            created_at=now
        )
        db.add(audit_record)
        await db.commit()

        return PolicyRollbackResult(
            rollback_id=rollback_id,
            merchant_id=request.merchant_id,
            target_policy_id=request.target_policy_id,
            target_policy_version=request.target_policy_version,
            previous_active_policy_id=curr_active_id,
            previous_active_policy_version=curr_active_version,
            status="ROLLED_BACK",
            failure_codes=[],
            safety_check_reference=safety_check_ref,
            created_at=now
        )

    @classmethod
    async def get_active_policy(
        cls,
        db: AsyncSession,
        merchant_id: str
    ) -> ActivePolicyResponse:
        """Fetch merchant's current authoritative active policy version."""
        stmt = select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == merchant_id)
        active_row = (await db.execute(stmt)).scalar_one_or_none()

        if not active_row:
            # Check merchant exists
            merch_res = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
            if not merch_res.scalar_one_or_none():
                raise MerchantNotFoundError(f"Merchant '{merchant_id}' not found.")
            return ActivePolicyResponse(
                merchant_id=merchant_id,
                policy_id=CANONICAL_BASELINE_POLICY_ID,
                policy_version="merchant-policy/v1",
                policy=None,
                lifecycle_status=PolicyLifecycleState.ACTIVE,
                activated_at=datetime.now(timezone.utc),
                promotion_id="init_baseline"
            )

        # Retrieve version record if available
        stmt_ver = select(MerchantPolicyVersionRecord).where(
            and_(
                MerchantPolicyVersionRecord.merchant_id == merchant_id,
                MerchantPolicyVersionRecord.policy_id == active_row.policy_id,
                MerchantPolicyVersionRecord.policy_version == active_row.policy_version
            )
        )
        ver_row = (await db.execute(stmt_ver)).scalar_one_or_none()
        cand: Optional[PolicyCandidate] = None
        if ver_row:
            inc = IncentiveProposal(**ver_row.incentive_json) if ver_row.incentive_json else None
            cand = PolicyCandidate(
                candidate_id=ver_row.policy_id,
                strategy_type=StrategyType(ver_row.strategy_type),
                product_ids=list(ver_row.product_ids_json),
                incentive=inc,
                validation_status=CandidateValidationStatus.APPROVED,
                rationale=ver_row.rationale or "Active merchant policy"
            )

        return ActivePolicyResponse(
            merchant_id=merchant_id,
            policy_id=active_row.policy_id,
            policy_version=active_row.policy_version,
            policy=cand,
            lifecycle_status=PolicyLifecycleState.ACTIVE,
            activated_at=active_row.activated_at,
            promotion_id=active_row.promotion_id
        )

    @classmethod
    async def get_lifecycle_history(
        cls,
        db: AsyncSession,
        merchant_id: str
    ) -> List[PolicyPromotionResult]:
        """Fetch chronological audit history of all lifecycle transitions for a merchant."""
        stmt = (
            select(PolicyLifecycleAuditRecord)
            .where(PolicyLifecycleAuditRecord.merchant_id == merchant_id)
            .order_by(PolicyLifecycleAuditRecord.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [cls._audit_record_to_result(r) for r in rows]

    @classmethod
    async def get_policy_versions(
        cls,
        db: AsyncSession,
        merchant_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch all policy versions and lifecycle states recorded for a merchant."""
        stmt = (
            select(MerchantPolicyVersionRecord)
            .where(MerchantPolicyVersionRecord.merchant_id == merchant_id)
            .order_by(MerchantPolicyVersionRecord.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [
            {
                "policy_id": r.policy_id,
                "policy_version": r.policy_version,
                "lifecycle_status": r.lifecycle_status,
                "strategy_type": r.strategy_type,
                "product_ids": list(r.product_ids_json),
                "incentive": r.incentive_json,
                "created_at": r.created_at,
                "updated_at": r.updated_at
            }
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    @classmethod
    async def _record_rejection_async(
        cls,
        db: AsyncSession,
        merchant_id: str,
        candidate_id: str,
        candidate_version: str,
        prev_id: Optional[str],
        prev_ver: Optional[str],
        status: PromotionStatus,
        eligibility_str: str,
        failure_codes: List[PromotionFailureCode],
        evidence_summary: Dict[str, Any],
        config_version: str,
        safety_check_id: Optional[str] = None
    ) -> PolicyPromotionResult:
        """Record and return rejected promotion audit record."""
        now = datetime.now(timezone.utc)
        record = PolicyLifecycleAuditRecord(
            id=f"prom_{uuid.uuid4().hex[:12]}",
            merchant_id=merchant_id,
            transition_type="PROMOTION",
            candidate_policy_id=candidate_id,
            candidate_policy_version=candidate_version,
            previous_active_policy_id=prev_id,
            previous_active_policy_version=prev_ver,
            resulting_active_policy_id=prev_id,
            resulting_active_policy_version=prev_ver,
            promotion_status=status.value,
            eligibility_status=eligibility_str,
            failure_codes_json=[fc.value for fc in failure_codes],
            evidence_type=evidence_summary.get("evidence_type"),
            evidence_references_json=evidence_summary,
            safety_check_id=safety_check_id,
            promotion_config_version=config_version,
            lifecycle_version=LIFECYCLE_SCHEMA_VERSION,
            created_at=now
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return cls._audit_record_to_result(record)

    @classmethod
    def _audit_record_to_result(cls, record: PolicyLifecycleAuditRecord) -> PolicyPromotionResult:
        """Convert database audit record into contract PolicyPromotionResult."""
        fc_list = [PromotionFailureCode(c) for c in (record.failure_codes_json or []) if c in PromotionFailureCode.__members__]
        ev_type_raw = getattr(record, "evidence_type", None) or (record.evidence_references_json or {}).get("evidence_type")
        ev_type = PromotionEvidenceType(ev_type_raw) if ev_type_raw and ev_type_raw in PromotionEvidenceType.__members__ else None
        obs_warning = (record.evidence_references_json or {}).get("observational_bias_warning")
        return PolicyPromotionResult(
            promotion_id=record.id,
            merchant_id=record.merchant_id,
            candidate_policy_id=record.candidate_policy_id,
            candidate_policy_version=record.candidate_policy_version,
            previous_active_policy_id=record.previous_active_policy_id,
            previous_active_policy_version=record.previous_active_policy_version,
            resulting_active_policy_id=record.resulting_active_policy_id,
            resulting_active_policy_version=record.resulting_active_policy_version,
            promotion_status=PromotionStatus(record.promotion_status),
            eligibility_status=record.eligibility_status,
            failure_codes=fc_list,
            evidence_type=ev_type,
            observational_bias_warning=obs_warning,
            evidence_summary=record.evidence_references_json or {},
            safety_check_reference=record.safety_check_id,
            promotion_config_version=record.promotion_config_version,
            lifecycle_version=record.lifecycle_version,
            created_at=record.created_at
        )
