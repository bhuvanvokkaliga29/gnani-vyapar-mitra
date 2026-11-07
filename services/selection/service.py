"""Policy Selection Service Layer.

Contract: policy-selection/v1
Orchestrates deterministic candidate evaluation, model inference, ranked slate generation,
database persistence, and idempotent retrieval.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from domain.models import PolicySelectionRecord
from services.learning.model_service import PolicyLearningModelService
from services.selection.schemas import (
    PolicySelectionRequest,
    PolicySelectionResult,
    CandidateSelectionScore,
    SELECTION_SCHEMA_VERSION
)
from services.selection.ranking import PolicyCandidateSelector
from services.selection.errors import (
    IncompatibleSelectionVersionError,
    SelectionNotFoundError,
    MerchantSelectionIsolationError
)


class PolicySelectionService:
    """Service handling deterministic policy candidate selection."""

    @classmethod
    async def select_policy(
        cls,
        db: AsyncSession,
        request: PolicySelectionRequest
    ) -> PolicySelectionResult:
        """Deterministically select the preferred policy candidate under current learning model.
        
        Guarantees:
        1. Idempotency: Repeated calls with same (merchant_id, opportunity_id) return the recorded decision.
        2. Contract version validation.
        3. Model isolation: strictly uses merchant's isolated learning model.
        4. Auditability: persists complete candidate slate and selection reason.
        """
        # Validate selection version
        if request.selection_version != SELECTION_SCHEMA_VERSION:
            raise IncompatibleSelectionVersionError(
                f"Unsupported selection_version '{request.selection_version}'. Expected '{SELECTION_SCHEMA_VERSION}'."
            )

        # 1. Idempotency check
        existing_stmt = select(PolicySelectionRecord).where(
            and_(
                PolicySelectionRecord.merchant_id == request.merchant_id,
                PolicySelectionRecord.opportunity_id == request.opportunity_id
            )
        )
        existing_res = await db.execute(existing_stmt)
        existing_record = existing_res.scalar_one_or_none()
        if existing_record:
            return cls._record_to_result(existing_record)

        # 2. Retrieve merchant isolated learning model
        model, _ = await PolicyLearningModelService.get_or_create_model(db, request.merchant_id)

        # 3. Deterministic candidate ranking and selection
        (
            selected_score,
            baseline_score,
            ranked_slate,
            selection_reason
        ) = PolicyCandidateSelector.evaluate_and_rank_candidates(
            candidates=request.candidates,
            intent=request.intent,
            buyer_context_key=request.buyer_context_key,
            model=model,
            commerce_context=request.commerce_context
        )

        now = request.decision_timestamp or datetime.now(timezone.utc)
        selection_id = f"sel_{uuid.uuid4().hex[:12]}"

        # 4. Persist selection record
        record = PolicySelectionRecord(
            id=selection_id,
            merchant_id=request.merchant_id,
            opportunity_id=request.opportunity_id,
            buyer_context_key=request.buyer_context_key,
            selected_policy_id=selected_score.policy_id,
            selected_policy_version=selected_score.policy_version,
            baseline_policy_id=baseline_score.policy_id,
            selected_predicted_contribution_paise=selected_score.predicted_contribution_paise,
            selected_uncertainty=Decimal(str(round(selected_score.uncertainty, 4))),
            baseline_predicted_contribution_paise=baseline_score.predicted_contribution_paise,
            ranked_candidates_json=[c.model_dump() for c in ranked_slate],
            model_version="learning-model/v1",
            feature_version="feature-schema/v1",
            selection_version=SELECTION_SCHEMA_VERSION,
            selection_reason=selection_reason,
            created_at=now
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return cls._record_to_result(record)

    @classmethod
    async def get_selection(
        cls,
        db: AsyncSession,
        selection_id: str,
        merchant_id: Optional[str] = None
    ) -> PolicySelectionResult:
        """Fetch historical selection by ID with tenant isolation enforcement."""
        stmt = select(PolicySelectionRecord).where(PolicySelectionRecord.id == selection_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise SelectionNotFoundError(f"Policy selection record '{selection_id}' not found.")

        if merchant_id and record.merchant_id != merchant_id:
            raise MerchantSelectionIsolationError(
                f"Selection '{selection_id}' belongs to merchant '{record.merchant_id}', access denied for '{merchant_id}'."
            )

        return cls._record_to_result(record)

    @staticmethod
    def _record_to_result(record: PolicySelectionRecord) -> PolicySelectionResult:
        """Convert database record to API response DTO."""
        candidates = [CandidateSelectionScore(**item) for item in record.ranked_candidates_json]
        return PolicySelectionResult(
            selection_id=record.id,
            merchant_id=record.merchant_id,
            opportunity_id=record.opportunity_id,
            buyer_context_key=record.buyer_context_key,
            selected_policy_id=record.selected_policy_id,
            selected_policy_version=record.selected_policy_version,
            baseline_policy_id=record.baseline_policy_id,
            selected_predicted_contribution_paise=record.selected_predicted_contribution_paise,
            selected_uncertainty=float(record.selected_uncertainty),
            baseline_predicted_contribution_paise=record.baseline_predicted_contribution_paise,
            ranked_candidates=candidates,
            model_version=record.model_version,
            feature_version=record.feature_version,
            selection_version=record.selection_version,
            selection_reason=record.selection_reason,
            selection_timestamp=record.created_at
        )
