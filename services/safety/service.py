"""Orchestration Service for Deterministic Policy Safety & Admissibility Gate.

Contract Version: policy-safety/v1
Orchestrates:
- Request version validation.
- Fresh database state retrieval via CommerceService.
- Deterministic candidate evaluation via PolicySafetyValidator.
- Persistence to policy_safety_records for auditability and idempotency.
- Multi-tenant isolation enforcement.
"""

import uuid
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from domain.models import PolicySafetyRecord
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.policy.schemas import CandidateEconomics
from services.safety.schemas import (
    SAFETY_SCHEMA_VERSION,
    PolicySafetyRequest,
    PolicySafetyResult,
    PolicySafetyStatus,
    PolicySafetyFailureCode
)
from services.safety.validator import PolicySafetyValidator
from services.safety.errors import (
    IncompatibleSafetyVersionError,
    MerchantSafetyIsolationError,
    SafetyCheckNotFoundError
)

logger = structlog.get_logger()


class PolicySafetyService:
    """Authoritative service for Phase 8.6 commercial safety validation."""

    @classmethod
    async def validate_policy(
        cls,
        db: AsyncSession,
        request: PolicySafetyRequest
    ) -> PolicySafetyResult:
        """Validate candidate policy admissibility against fresh merchant state."""
        # 1. Version Check
        if request.safety_version != SAFETY_SCHEMA_VERSION:
            raise IncompatibleSafetyVersionError(
                f"Incompatible safety version '{request.safety_version}'. Expected '{SAFETY_SCHEMA_VERSION}'."
            )

        policy_id = request.proposed_policy.candidate_id

        # 2. Retrieve Authoritative Fresh Context
        commerce_service = CommerceService()
        try:
            fresh_context = await commerce_service.get_merchant_commerce_context(db, request.merchant_id)
        except MerchantNotFoundError:
            # Merchant not found -> fail closed with STALE_CONTEXT
            check_id = f"safe_{uuid.uuid4().hex[:12]}"
            return PolicySafetyResult(
                safety_check_id=check_id,
                merchant_id=request.merchant_id,
                opportunity_id=request.opportunity_id,
                policy_id=policy_id,
                policy_version=request.proposed_policy_version,
                status=PolicySafetyStatus.REJECTED,
                failure_codes=[PolicySafetyFailureCode.STALE_CONTEXT],
                validation_reason=PolicySafetyFailureCode.STALE_CONTEXT.value,
                policy_safety_version=SAFETY_SCHEMA_VERSION
            )

        # 3. Compute Authoritative State Fingerprint for This Policy Proposal
        state_fingerprint = PolicySafetyValidator.compute_state_fingerprint(
            candidate=request.proposed_policy,
            fresh_context=fresh_context,
            proposed_policy_version=request.proposed_policy_version
        )

        # 4. State-Aware Idempotency Check:
        # Same opportunity + same policy ID + same policy version + same authoritative state -> return idempotent result
        stmt = select(PolicySafetyRecord).where(
            and_(
                PolicySafetyRecord.merchant_id == request.merchant_id,
                PolicySafetyRecord.opportunity_id == request.opportunity_id,
                PolicySafetyRecord.policy_id == policy_id,
                PolicySafetyRecord.policy_version == request.proposed_policy_version,
                PolicySafetyRecord.merchant_context_version == state_fingerprint
            )
        ).order_by(PolicySafetyRecord.created_at.desc())
        existing = (await db.execute(stmt)).scalars().first()
        if existing:
            failure_codes = [PolicySafetyFailureCode(c) for c in existing.failure_codes_json]
            econ = None
            if existing.recalculated_economics_json:
                econ = CandidateEconomics.model_validate(existing.recalculated_economics_json)

            return PolicySafetyResult(
                safety_check_id=existing.id,
                merchant_id=existing.merchant_id,
                opportunity_id=existing.opportunity_id,
                policy_id=existing.policy_id,
                policy_version=existing.policy_version,
                status=PolicySafetyStatus(existing.status),
                failure_codes=failure_codes,
                validated_at=existing.created_at,
                merchant_context_version=existing.merchant_context_version,
                recalculated_economics=econ,
                policy_safety_version=existing.safety_version,
                validation_reason=existing.validation_reason
            )

        # 5. Authoritative State Changed or First Check -> Perform Fresh Validation
        status, failures, recalculated_econ, reason = PolicySafetyValidator.validate_admissibility(
            candidate=request.proposed_policy,
            fresh_context=fresh_context,
            merchant_id=request.merchant_id,
            proposed_policy_version=request.proposed_policy_version,
            intent=request.intent
        )

        check_id = f"safe_{uuid.uuid4().hex[:12]}"

        # 6. Persist Immutable Audit Record
        record = PolicySafetyRecord(
            id=check_id,
            merchant_id=request.merchant_id,
            opportunity_id=request.opportunity_id,
            buyer_context_key=request.buyer_context_key,
            policy_id=policy_id,
            policy_version=request.proposed_policy_version,
            selection_id=request.selection_id,
            status=status.value,
            failure_codes_json=[f.value for f in failures],
            recalculated_economics_json=recalculated_econ.model_dump(mode="json") if recalculated_econ else None,
            validation_reason=reason,
            merchant_context_version=state_fingerprint,
            safety_version=SAFETY_SCHEMA_VERSION
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return PolicySafetyResult(
            safety_check_id=record.id,
            merchant_id=record.merchant_id,
            opportunity_id=record.opportunity_id,
            policy_id=record.policy_id,
            policy_version=record.policy_version,
            status=status,
            failure_codes=failures,
            validated_at=record.created_at,
            merchant_context_version=state_fingerprint,
            recalculated_economics=recalculated_econ,
            policy_safety_version=SAFETY_SCHEMA_VERSION,
            validation_reason=reason
        )

    @classmethod
    async def get_safety_check(
        cls,
        db: AsyncSession,
        check_id: str,
        merchant_id: str
    ) -> PolicySafetyResult:
        """Fetch historical safety validation outcome by ID with merchant tenant isolation."""
        stmt = select(PolicySafetyRecord).where(PolicySafetyRecord.id == check_id)
        record = (await db.execute(stmt)).scalar_one_or_none()

        if not record:
            raise SafetyCheckNotFoundError(f"Safety check '{check_id}' not found.")

        if record.merchant_id != merchant_id:
            raise MerchantSafetyIsolationError(
                f"Access denied: check '{check_id}' belongs to a different merchant."
            )

        failures = [PolicySafetyFailureCode(c) for c in record.failure_codes_json]
        econ = None
        if record.recalculated_economics_json:
            econ = CandidateEconomics.model_validate(record.recalculated_economics_json)

        return PolicySafetyResult(
            safety_check_id=record.id,
            merchant_id=record.merchant_id,
            opportunity_id=record.opportunity_id,
            policy_id=record.policy_id,
            policy_version=record.policy_version,
            status=PolicySafetyStatus(record.status),
            failure_codes=failures,
            validated_at=record.created_at,
            merchant_context_version=record.merchant_context_version,
            recalculated_economics=econ,
            policy_safety_version=record.safety_version,
            validation_reason=record.validation_reason
        )
