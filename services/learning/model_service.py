"""Service implementation for managing merchant contextual learning models in Phase 8.4."""

from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from domain.models import PolicyLearningModelState, PolicyMemoryRecord, AppliedModelObservationRecord
from services.learning.algorithm import ContextualLinearUCB, DEFAULT_LAMBDA, DEFAULT_ALPHA_PAISE
from services.learning.features import PolicyFeatureExtractor, FEATURE_DIMENSION
from services.learning.model_schemas import (
    LearningModelStateSchema,
    ModelPredictionSchema,
    ModelRebuildResponseSchema
)
from services.learning.model_errors import (
    LearningModelError,
    ConcurrentModelUpdateError,
    MerchantModelIsolationError,
    CorruptedModelStateError
)
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import PolicyCandidate, CandidateEconomics


class PolicyLearningModelService:
    """Provides merchant-isolated persistence, updates, rebuilds, and predictions for Contextual LinUCB."""

    @classmethod
    async def get_or_create_model(
        cls,
        db: AsyncSession,
        merchant_id: str,
        lambda_reg: float = DEFAULT_LAMBDA,
        alpha_paise: int = DEFAULT_ALPHA_PAISE
    ) -> Tuple[ContextualLinearUCB, int]:
        """Fetch existing model state or create a clean cold-start model.
        
        Returns:
            (model_instance, current_version)
        """
        stmt = select(PolicyLearningModelState).where(PolicyLearningModelState.merchant_id == merchant_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            data = {
                "merchant_id": record.merchant_id,
                "dimension": record.dimension,
                "lambda_reg": float(record.lambda_reg),
                "alpha_paise": record.alpha_paise,
                "observation_count": record.observation_count,
                "matrix_a": record.matrix_a_json,
                "vector_b": record.vector_b_json,
                "theta": record.theta_json
            }
            model = ContextualLinearUCB.from_dict(data)
            return model, record.version

        # Create fresh cold-start model in DB
        model = ContextualLinearUCB(
            merchant_id=merchant_id,
            dimension=FEATURE_DIMENSION,
            lambda_reg=lambda_reg,
            alpha_paise=alpha_paise
        )
        rec_id = f"lms_{uuid.uuid4().hex[:12]}"
        db_record = PolicyLearningModelState(
            id=rec_id,
            merchant_id=merchant_id,
            model_version="learning-model/v1",
            algorithm_version="learning-algorithm/v1",
            feature_version="feature-schema/v1",
            reward_version="merchant-reward/v1",
            formula_version="contribution-formula/v1",
            dimension=FEATURE_DIMENSION,
            lambda_reg=lambda_reg,
            alpha_paise=alpha_paise,
            observation_count=0,
            matrix_a_json=model.A,
            vector_b_json=model.b,
            theta_json=model.theta,
            version=1
        )
        db.add(db_record)
        await db.commit()
        await db.refresh(db_record)
        return model, 1

    @classmethod
    async def save_model(
        cls,
        db: AsyncSession,
        model: ContextualLinearUCB,
        expected_version: int
    ) -> int:
        """Persist model state using optimistic concurrency control to prevent lost updates.
        
        Returns:
            new_version
        """
        stmt = (
            update(PolicyLearningModelState)
            .where(
                and_(
                    PolicyLearningModelState.merchant_id == model.merchant_id,
                    PolicyLearningModelState.version == expected_version
                )
            )
            .values(
                matrix_a_json=model.A,
                vector_b_json=model.b,
                theta_json=model.theta,
                observation_count=model.observation_count,
                version=PolicyLearningModelState.version + 1,
                last_updated_at=datetime.now(timezone.utc)
            )
        )
        res = await db.execute(stmt)
        if res.rowcount == 0:
            await db.rollback()
            raise ConcurrentModelUpdateError(
                f"Lost-update race condition detected for merchant '{model.merchant_id}'. Version {expected_version} stale."
            )
        await db.commit()
        return expected_version + 1

    @classmethod
    async def apply_observation_idempotent(
        cls,
        db: AsyncSession,
        merchant_id: str,
        evidence_id: str,
        x: Any,
        reward_paise: int,
        max_retries: int = 3
    ) -> Tuple[bool, int]:
        """Atomically and idempotently apply a learning observation to the merchant's model.
        
        Guarantees:
        1. Checks durable AppliedModelObservationRecord before applying.
        2. If already applied, returns (False, current_version) with ZERO updates to A/b matrices.
        3. Persists AppliedModelObservationRecord and model update atomically in the same transaction.
        4. Handles concurrent races: unique constraint violation on (merchant_id, evidence_id)
           means another worker applied it concurrently -> safely returns (False, current_version).
        5. Handles optimistic concurrency on version conflict with automatic retry.
        
        Returns:
            (was_applied: bool, model_version: int)
        """
        # 1. Fast check if already applied in durable storage
        stmt_check = select(AppliedModelObservationRecord).where(
            and_(
                AppliedModelObservationRecord.merchant_id == merchant_id,
                AppliedModelObservationRecord.evidence_id == evidence_id
            )
        )
        existing = (await db.execute(stmt_check)).scalar_one_or_none()
        if existing:
            _, curr_ver = await cls.get_or_create_model(db, merchant_id)
            return False, curr_ver

        # 2. Attempt atomic update with retry on optimistic concurrency conflict
        for attempt in range(max_retries):
            # Re-verify before each attempt
            stmt_recheck = select(AppliedModelObservationRecord).where(
                and_(
                    AppliedModelObservationRecord.merchant_id == merchant_id,
                    AppliedModelObservationRecord.evidence_id == evidence_id
                )
            )
            if (await db.execute(stmt_recheck)).scalar_one_or_none():
                _, curr_ver = await cls.get_or_create_model(db, merchant_id)
                return False, curr_ver

            model, curr_ver = await cls.get_or_create_model(db, merchant_id)
            model.update(x, reward_paise)

            applied_rec = AppliedModelObservationRecord(
                id=f"amo_{uuid.uuid4().hex[:12]}",
                merchant_id=merchant_id,
                evidence_id=evidence_id,
                model_version=curr_ver + 1
            )
            db.add(applied_rec)

            try:
                new_ver = await cls.save_model(db, model, expected_version=curr_ver)
                return True, new_ver
            except ConcurrentModelUpdateError:
                if attempt == max_retries - 1:
                    raise
                # Check if this exact observation was applied by the winning worker
                stmt_conflict_check = select(AppliedModelObservationRecord).where(
                    and_(
                        AppliedModelObservationRecord.merchant_id == merchant_id,
                        AppliedModelObservationRecord.evidence_id == evidence_id
                    )
                )
                if (await db.execute(stmt_conflict_check)).scalar_one_or_none():
                    _, final_ver = await cls.get_or_create_model(db, merchant_id)
                    return False, final_ver
            except Exception:
                await db.rollback()
                # Catch unique constraint violation if another worker committed applied_rec concurrently
                stmt_final = select(AppliedModelObservationRecord).where(
                    and_(
                        AppliedModelObservationRecord.merchant_id == merchant_id,
                        AppliedModelObservationRecord.evidence_id == evidence_id
                    )
                )
                if (await db.execute(stmt_final)).scalar_one_or_none():
                    _, final_ver = await cls.get_or_create_model(db, merchant_id)
                    return False, final_ver
                raise

        return False, curr_ver


    @classmethod
    async def rebuild_merchant_model(
        cls,
        db: AsyncSession,
        merchant_id: str,
        cutoff_time: Optional[datetime] = None,
        lambda_reg: float = DEFAULT_LAMBDA,
        alpha_paise: int = DEFAULT_ALPHA_PAISE
    ) -> ModelRebuildResponseSchema:
        """Batch replay authoritative current-effective observations from Phase 8.3 memory.
        
        Guarantees:
        1. Only is_current=True records (eliminates superseded records, 0 double counting).
        2. Only learning_eligible=True and is_admissible=True records.
        3. Deterministic canonical replay order: observed_at ASC, id ASC.
        4. Replay cutoff adherence: observed_at <= cutoff_time.
        """
        conditions = [
            PolicyMemoryRecord.merchant_id == merchant_id,
            PolicyMemoryRecord.is_current == True,
            PolicyMemoryRecord.learning_eligible == True,
            PolicyMemoryRecord.is_admissible == True
        ]
        if cutoff_time is not None:
            conditions.append(PolicyMemoryRecord.observed_at <= cutoff_time)

        stmt = (
            select(PolicyMemoryRecord)
            .where(and_(*conditions))
            .order_by(PolicyMemoryRecord.observed_at.asc(), PolicyMemoryRecord.id.asc())
        )
        res = await db.execute(stmt)
        memory_records = res.scalars().all()

        # Initialize clean model
        rebuilt_model = ContextualLinearUCB(
            merchant_id=merchant_id,
            dimension=FEATURE_DIMENSION,
            lambda_reg=lambda_reg,
            alpha_paise=alpha_paise
        )

        for rec in memory_records:
            x = PolicyFeatureExtractor.extract(
                buyer_context_key=rec.buyer_context_key
            )
            rebuilt_model.update(x, rec.reward_contribution_paise)

        # Persist rebuilt model state
        stmt_curr = select(PolicyLearningModelState).where(PolicyLearningModelState.merchant_id == merchant_id)
        res_curr = await db.execute(stmt_curr)
        db_record = res_curr.scalar_one_or_none()

        if db_record:
            await cls.save_model(db, rebuilt_model, expected_version=db_record.version)
        else:
            rec_id = f"lms_{uuid.uuid4().hex[:12]}"
            new_state = PolicyLearningModelState(
                id=rec_id,
                merchant_id=merchant_id,
                model_version="learning-model/v1",
                algorithm_version="learning-algorithm/v1",
                feature_version="feature-schema/v1",
                dimension=FEATURE_DIMENSION,
                lambda_reg=lambda_reg,
                alpha_paise=alpha_paise,
                observation_count=rebuilt_model.observation_count,
                matrix_a_json=rebuilt_model.A,
                vector_b_json=rebuilt_model.b,
                theta_json=rebuilt_model.theta,
                version=1
            )
            db.add(new_state)
            await db.commit()

        return ModelRebuildResponseSchema(
            merchant_id=merchant_id,
            observation_count=rebuilt_model.observation_count,
            dimension=FEATURE_DIMENSION,
            rebuilt_at=datetime.now(timezone.utc)
        )

    @classmethod
    async def predict_candidate(
        cls,
        db: AsyncSession,
        merchant_id: str,
        policy_id: str,
        policy_version: str = "merchant-policy/v1",
        buyer_context_key: Optional[str] = None,
        intent: Optional[BuyerIntent] = None,
        candidate: Optional[PolicyCandidate] = None,
        economics: Optional[CandidateEconomics] = None,
        candidate_snapshot: Optional[Dict[str, Any]] = None
    ) -> ModelPredictionSchema:
        """Predict expected contribution, uncertainty, and diagnostic UCB score for a candidate policy."""
        # 1. Fetch merchant model
        model, _ = await cls.get_or_create_model(db, merchant_id)

        # 2. Extract 19-dimensional feature vector
        x = PolicyFeatureExtractor.extract(
            intent=intent,
            candidate=candidate,
            economics=economics,
            buyer_context_key=buyer_context_key,
            candidate_snapshot=candidate_snapshot
        )

        # 3. Model Prediction
        pred_paise, uncertainty, ucb_paise = model.predict(x)

        return ModelPredictionSchema(
            merchant_id=merchant_id,
            policy_id=policy_id,
            policy_version=policy_version,
            buyer_context_key=buyer_context_key or "bck_unspecified",
            predicted_contribution_paise=pred_paise,
            uncertainty=uncertainty,
            ucb_score_paise=ucb_paise,
            model_version="learning-model/v1",
            algorithm_version="learning-algorithm/v1",
            feature_version="feature-schema/v1",
            observation_count=model.observation_count
        )
