"""FastAPI router for Phase 8.1 Merchant Policy Learning Evidence."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from apps.api.core.database import get_db
from domain.models import ExperimentRecord, ObservationRecord
from services.experiments.schemas import PolicyExperiment, ExperimentObservation, ExperimentStatus, VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    EvidenceFilter,
    IngestExperimentRequest
)
from services.learning.service import LearningEvidenceService
from services.learning.errors import (
    LearningError,
    InvalidEvidenceError,
    CrossTenantLearningError,
    SecurityBoundaryError
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/learning", tags=["Merchant Policy Learning Evidence"])


def get_learning_service() -> LearningEvidenceService:
    """Dependency provider for LearningEvidenceService."""
    return LearningEvidenceService()


@router.get("/evidence", response_model=List[PolicyLearningEvidence])
async def list_learning_evidence(
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    buyer_context_key: Optional[str] = Query(None, description="Filter by buyer context key"),
    policy_id: Optional[str] = Query(None, description="Filter by policy proposal ID"),
    learning_eligible_only: bool = Query(True, description="Filter for learning_eligible == True"),
    source: Optional[EvidenceSource] = Query(None, description="Filter by evidence source"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    service: LearningEvidenceService = Depends(get_learning_service)
) -> List[PolicyLearningEvidence]:
    """Retrieve filtered PolicyLearningEvidence records strictly scoped to merchant tenant."""
    filter_params = EvidenceFilter(
        merchant_id=merchant_id,
        buyer_context_key=buyer_context_key,
        policy_id=policy_id,
        learning_eligible_only=learning_eligible_only,
        source=source,
        limit=limit,
        offset=offset
    )
    return await service.list_evidence(db, filter_params)


@router.get("/evidence/{evidence_id}", response_model=PolicyLearningEvidence)
async def get_learning_evidence(
    evidence_id: str,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: LearningEvidenceService = Depends(get_learning_service)
) -> PolicyLearningEvidence:
    """Retrieve a single PolicyLearningEvidence record, enforcing tenant isolation."""
    evidence = await service.get_evidence(db, evidence_id, merchant_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Learning evidence '{evidence_id}' not found.")
    return evidence


@router.post("/evidence/ingest-experiment/{experiment_id}", response_model=List[PolicyLearningEvidence])
async def ingest_experiment_observations(
    experiment_id: str,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: LearningEvidenceService = Depends(get_learning_service)
) -> List[PolicyLearningEvidence]:
    """Authoritatively ingest observations from a completed Phase 7 experiment into PolicyLearningEvidence."""
    # 1. Verify Experiment Tenant Scoping
    stmt = select(ExperimentRecord).where(ExperimentRecord.id == experiment_id)
    exp_record = (await db.execute(stmt)).scalar_one_or_none()
    if not exp_record:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    if exp_record.merchant_id != merchant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied: experiment belongs to another merchant.")

    # Reconstitute PolicyExperiment
    exp = PolicyExperiment(
        experiment_id=exp_record.id,
        merchant_id=exp_record.merchant_id,
        name=exp_record.name,
        control_policy_id=exp_record.control_policy_id,
        treatment_policy_id=exp_record.treatment_policy_id,
        control_proposal_snapshot=exp_record.control_proposal_snapshot,
        treatment_proposal_snapshot=exp_record.treatment_proposal_snapshot,
        hypothesis=exp_record.hypothesis,
        primary_metric=exp_record.primary_metric,
        status=ExperimentStatus(exp_record.status)
    )

    # 2. Fetch observations
    obs_stmt = select(ObservationRecord).where(ObservationRecord.experiment_id == experiment_id)
    obs_records = (await db.execute(obs_stmt)).scalars().all()

    ingested = []
    for obs_rec in obs_records:
        obs = ExperimentObservation(
            observation_id=obs_rec.id,
            experiment_id=obs_rec.experiment_id,
            scenario_id=obs_rec.scenario_id,
            variant=VariantType(obs_rec.variant),
            outcome_type=obs_rec.outcome_type,
            buyer_selection_result_id=obs_rec.buyer_selection_result_id,
            selected_offer_id=obs_rec.selected_offer_id,
            is_selected=obs_rec.is_selected,
            execution_id=obs_rec.execution_id,
            order_id=obs_rec.order_id,
            razorpay_order_id=obs_rec.razorpay_order_id,
            payment_outcome=obs_rec.payment_outcome,
            revenue_paise=obs_rec.revenue_paise,
            contribution_paise=obs_rec.contribution_paise,
            margin_percent=float(obs_rec.margin_percent),
            guardrail_violations=obs_rec.guardrail_violations or [],
            idempotency_key=obs_rec.idempotency_key,
            observed_at=obs_rec.observed_at
        )

        evi = await service.ingest_observation(
            db=db,
            observation=obs,
            experiment=exp
        )
        ingested.append(evi)

    return ingested
