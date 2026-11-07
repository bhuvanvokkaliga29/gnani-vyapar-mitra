"""Authoritative Service Layer for Phase 8.9 Closed-Loop Learning Evaluation.

Contracts:
- closed-loop-evaluation/v1

Guarantees:
- Database persistence for immutable evaluation runs.
- Idempotent evaluation dispatch and retrieval.
- Multi-tenant boundary enforcement.
- Deterministic error propagation.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from domain.models import Merchant, ClosedLoopEvaluationRecord
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.evaluation.schemas import (
    EVALUATION_SCHEMA_VERSION,
    ClosedLoopEvaluationRequest,
    ClosedLoopEvaluationResult,
    ClosedLoopEvaluationConfig,
    LearningCurveCheckpoint,
    EvaluationStatus,
    EvaluationOutcome,
    BaselineDefinition,
    PopulationDefinition,
    EvaluationMetricSet,
    HoldoutMetricSet,
    EvaluationDiagnostics
)
from services.evaluation.errors import (
    ClosedLoopEvaluationError,
    IncompatibleEvaluationVersionError,
    EvaluationNotFoundError,
    EvaluationTenantViolationError,
    EvaluationStateConflictError
)
from services.evaluation.orchestrator import ClosedLoopEvaluationOrchestrator


class ClosedLoopEvaluationService:
    """Service managing closed-loop learning evaluation runs and records."""

    @classmethod
    async def run_evaluation(
        cls,
        db: AsyncSession,
        request: ClosedLoopEvaluationRequest
    ) -> ClosedLoopEvaluationResult:
        """Initialize, execute, and persist an immutable closed-loop learning evaluation run."""
        # 1. Validate Schema Version
        if request.evaluation_version != EVALUATION_SCHEMA_VERSION:
            raise IncompatibleEvaluationVersionError(
                f"Unsupported evaluation_version '{request.evaluation_version}'. Expected '{EVALUATION_SCHEMA_VERSION}'."
            )

        # 2. Verify Merchant Tenant Exists
        merch_res = await db.execute(select(Merchant).where(Merchant.id == request.merchant_id))
        merchant = merch_res.scalar_one_or_none()
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{request.merchant_id}' not found.")

        config = request.config or ClosedLoopEvaluationConfig(mode=request.mode)

        # 3. Idempotency Check
        if request.idempotency_key:
            stmt_idemp = select(ClosedLoopEvaluationRecord).where(
                and_(
                    ClosedLoopEvaluationRecord.merchant_id == request.merchant_id,
                    ClosedLoopEvaluationRecord.id == request.idempotency_key
                )
            )
            existing_row = (await db.execute(stmt_idemp)).scalar_one_or_none()
            if existing_row:
                return cls._record_to_result(existing_row)

        evaluation_id = request.idempotency_key or f"eval_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # 4. Initialize Evaluation Record in DB
        eval_record = ClosedLoopEvaluationRecord(
            id=evaluation_id,
            merchant_id=request.merchant_id,
            mode=config.mode.value,
            status=EvaluationStatus.RUNNING.value,
            overall_outcome=EvaluationOutcome.INCONCLUSIVE.value,
            dataset_id=request.dataset_id,
            baseline_definition_json={"baseline_policy_id": config.baseline_policy_id, "baseline_name": "NO_OFFER"},
            training_definition_json={"count": config.training_sample_size},
            evaluation_definition_json={"count": config.training_sample_size},
            holdout_definition_json={"count": config.holdout_sample_size},
            config_json=config.model_dump(mode="json"),
            seed=config.randomization_seed,
            summary_metrics_json={},
            learning_curve_json=[],
            holdout_metrics_json={},
            diagnostics_json={},
            warnings_json=[],
            failure_reasons_json=[],
            contract_versions_json={"closed_loop_evaluation": EVALUATION_SCHEMA_VERSION},
            created_at=now
        )
        db.add(eval_record)
        await db.commit()
        await db.refresh(eval_record)

        # 5. Execute Evaluation via Orchestrator
        orchestrator = ClosedLoopEvaluationOrchestrator()
        result = await orchestrator.run_closed_loop(
            db=db,
            evaluation_id=evaluation_id,
            merchant_id=request.merchant_id,
            config=config,
            dataset_id=request.dataset_id
        )

        # 6. Update and Finalize Record
        eval_record.status = result.status.value
        eval_record.overall_outcome = result.overall_outcome.value
        eval_record.baseline_definition_json = result.baseline_definition.model_dump(mode="json")
        eval_record.training_definition_json = result.training_definition.model_dump(mode="json")
        eval_record.evaluation_definition_json = result.evaluation_definition.model_dump(mode="json")
        eval_record.holdout_definition_json = result.holdout_definition.model_dump(mode="json")
        eval_record.config_json = result.config.model_dump(mode="json")
        eval_record.summary_metrics_json = result.summary_metrics.model_dump(mode="json")
        eval_record.learning_curve_json = [c.model_dump(mode="json") for c in result.learning_curve]
        eval_record.holdout_metrics_json = result.holdout_metrics.model_dump(mode="json")
        eval_record.diagnostics_json = result.diagnostics.model_dump(mode="json")
        eval_record.warnings_json = result.warnings
        eval_record.failure_reasons_json = result.failure_reasons
        eval_record.contract_versions_json = result.contract_versions
        eval_record.completed_at = result.completed_at

        await db.commit()
        await db.refresh(eval_record)

        return result

    @classmethod
    async def get_evaluation(
        cls,
        db: AsyncSession,
        evaluation_id: str,
        merchant_id: str
    ) -> ClosedLoopEvaluationResult:
        """Fetch an immutable evaluation result by ID with strict tenant isolation."""
        stmt = select(ClosedLoopEvaluationRecord).where(ClosedLoopEvaluationRecord.id == evaluation_id)
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            raise EvaluationNotFoundError(f"Evaluation '{evaluation_id}' not found.")

        if record.merchant_id != merchant_id:
            raise EvaluationTenantViolationError(
                f"Merchant '{merchant_id}' unauthorized to access evaluation of merchant '{record.merchant_id}'."
            )

        return cls._record_to_result(record)

    @classmethod
    async def get_learning_curve(
        cls,
        db: AsyncSession,
        evaluation_id: str,
        merchant_id: str
    ) -> List[LearningCurveCheckpoint]:
        """Fetch learning curve checkpoints for an evaluation run."""
        result = await cls.get_evaluation(db, evaluation_id, merchant_id)
        return result.learning_curve

    @classmethod
    def _record_to_result(cls, record: ClosedLoopEvaluationRecord) -> ClosedLoopEvaluationResult:
        """Convert database record to typed ClosedLoopEvaluationResult."""
        cfg = ClosedLoopEvaluationConfig(**record.config_json)
        base_def = BaselineDefinition(**record.baseline_definition_json)
        train_def = PopulationDefinition(**record.training_definition_json)
        eval_def = PopulationDefinition(**record.evaluation_definition_json)
        hold_def = PopulationDefinition(**record.holdout_definition_json)
        summary = EvaluationMetricSet(**record.summary_metrics_json)
        holdout_m = HoldoutMetricSet(**record.holdout_metrics_json)
        diag = EvaluationDiagnostics(**record.diagnostics_json)
        curve = [LearningCurveCheckpoint(**c) for c in (record.learning_curve_json or [])]

        created_at = record.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        completed_at = record.completed_at
        if completed_at and completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        return ClosedLoopEvaluationResult(
            evaluation_id=record.id,
            merchant_id=record.merchant_id,
            mode=record.mode,
            status=EvaluationStatus(record.status),
            overall_outcome=EvaluationOutcome(record.overall_outcome),
            dataset_id=record.dataset_id,
            baseline_definition=base_def,
            training_definition=train_def,
            evaluation_definition=eval_def,
            holdout_definition=hold_def,
            config=cfg,
            seed=record.seed,
            summary_metrics=summary,
            learning_curve=curve,
            holdout_metrics=holdout_m,
            diagnostics=diag,
            warnings=record.warnings_json or [],
            failure_reasons=record.failure_reasons_json or [],
            contract_versions=record.contract_versions_json or {},
            created_at=created_at,
            completed_at=completed_at
        )
