"""FastAPI router for Controlled Policy Experiments (Phase 7)."""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from domain.intent_schemas import BuyerIntent
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentResult,
    ExperimentObservation,
    CreateExperimentRequest,
    StartExperimentRequest,
    RunExperimentRequest
)
from services.experiments.service import ExperimentService
from services.experiments.errors import (
    ExperimentError,
    CrossTenantViolationError,
    InvalidExperimentStateError,
    InvalidPolicyError,
    GuardrailViolationError
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/experiments", tags=["Controlled Policy Experiments"])


def get_experiment_service() -> ExperimentService:
    """Dependency provider for ExperimentService."""
    return ExperimentService()


@router.post("", response_model=PolicyExperiment, status_code=201)
async def create_experiment(
    request: CreateExperimentRequest,
    db: AsyncSession = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service)
) -> PolicyExperiment:
    """Create a new controlled policy experiment draft.
    
    Validates control and treatment proposals, ensures merchant tenant isolation,
    and isolates policy differences.
    """
    try:
        # For mock/demo purposes when running in standalone API mode, if snapshots not supplied,
        # synthesize standard compliant baseline snapshots
        ctrl_snapshot = {
            "proposal_id": request.control_policy_id,
            "merchant_id": request.merchant_id,
            "status": "APPROVED",
            "selected_candidate": {
                "candidate_id": f"cand_{request.control_policy_id}",
                "strategy_type": "SINGLE_PRODUCT",
                "product_id": "prod_atlas_pack",
                "product_name": "Atlas Travel Pack",
                "category": "travel_backpack",
                "price_paise": 299900,
                "currency": "INR",
                "availability": True,
                "relevant_attributes": {"laptop_size": 15.6, "capacity_liters": 28.0, "water_resistant": True},
                "included_items": [],
                "warranty_months": 12,
                "delivery_days": 2,
                "economics": {
                    "proposed_price_paise": 299900,
                    "cogs_paise": 150000,
                    "margin_percent": 49.98
                }
            }
        }
        treat_snapshot = {
            "proposal_id": request.treatment_policy_id,
            "merchant_id": request.merchant_id,
            "status": "APPROVED",
            "selected_candidate": {
                "candidate_id": f"cand_{request.treatment_policy_id}",
                "strategy_type": "VALUE_BUNDLE",
                "product_id": "prod_atlas_pack",
                "product_name": "Atlas Travel Pack",
                "category": "travel_backpack",
                "price_paise": 349900,
                "currency": "INR",
                "availability": True,
                "relevant_attributes": {"laptop_size": 15.6, "capacity_liters": 28.0, "water_resistant": True},
                "included_items": ["rain_cover"],
                "warranty_months": 24,
                "delivery_days": 2,
                "economics": {
                    "proposed_price_paise": 349900,
                    "cogs_paise": 170000,
                    "margin_percent": 51.41
                }
            }
        }

        return await service.create_experiment(
            db=db,
            request=request,
            control_proposal=ctrl_snapshot,
            treatment_proposal=treat_snapshot
        )
    except (CrossTenantViolationError, InvalidPolicyError, GuardrailViolationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("create_experiment_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create experiment: {str(e)}")


@router.get("/{experiment_id}", response_model=PolicyExperiment)
async def get_experiment(
    experiment_id: str,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service)
) -> PolicyExperiment:
    """Retrieve an experiment by ID, enforcing tenant isolation."""
    exp = await service.get_experiment(db, experiment_id, merchant_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return exp


@router.post("/{experiment_id}/start", response_model=PolicyExperiment)
async def start_experiment(
    experiment_id: str,
    request: StartExperimentRequest,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service)
) -> PolicyExperiment:
    """Transition an experiment from DRAFT to RUNNING status."""
    try:
        return await service.start_experiment(db, experiment_id, merchant_id)
    except CrossTenantViolationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidExperimentStateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/run", response_model=ExperimentResult)
async def run_experiment_population(
    experiment_id: str,
    request: RunExperimentRequest,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service)
) -> ExperimentResult:
    """Execute the experiment across its assigned population scenarios."""
    try:
        exp = await service.get_experiment(db, experiment_id, merchant_id)
        if not exp:
            raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

        scenarios = {}
        for sid in exp.population_scenarios:
            if request.population_intents and sid in request.population_intents:
                scenarios[sid] = BuyerIntent(**request.population_intents[sid])
            else:
                # Default travel pack scenario: 15.6" laptop, capacity >= 26L, long warranty, budget ₹4,000
                scenarios[sid] = BuyerIntent(
                    budget={"max_amount_paise": 400000, "currency": "INR"},
                    requirements=[
                        {"attribute": "laptop_size", "operator": "GTE", "value": 15.6},
                        {"attribute": "capacity_liters", "operator": "GTE", "value": 26.0}
                    ],
                    preferences=[{"attribute": "warranty", "preference": "long warranty"}]
                )

        return await service.run_experiment_population(
            db=db,
            experiment_id=experiment_id,
            merchant_id=merchant_id,
            scenarios=scenarios,
            execute_test_mode_orders=request.execute_test_mode_orders
        )
    except CrossTenantViolationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("run_experiment_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{experiment_id}/result", response_model=ExperimentResult)
async def get_experiment_result(
    experiment_id: str,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service)
) -> ExperimentResult:
    """Calculate and return authoritative experiment results and metrics."""
    try:
        return await service.get_experiment_result(db, experiment_id, merchant_id)
    except CrossTenantViolationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/observe", response_model=ExperimentObservation)
async def record_observation(
    experiment_id: str,
    observation: ExperimentObservation,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service)
) -> ExperimentObservation:
    """Record an individual decision observation idempotently."""
    exp = await service.get_experiment(db, experiment_id, merchant_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    if observation.experiment_id != experiment_id:
        raise HTTPException(status_code=400, detail="Observation experiment_id does not match URL path.")

    return await service.record_observation(db, observation)
