"""Unit tests for LearningEvidenceService idempotency, deduplication, and immutability."""

from datetime import datetime, timezone
import pytest
from domain.models import Merchant, ExperimentRecord, ObservationRecord, LearningEvidenceRecord
from domain.intent_schemas import BuyerIntent, BudgetConstraint, AttributeRequirement, OperatorType
from services.experiments.schemas import PolicyExperiment, ExperimentObservation, ExperimentHypothesis, ExperimentStatus, VariantType
from services.learning.service import LearningEvidenceService


@pytest.fixture
async def setup_experiment_data(db_session):
    """Seed merchant, experiment, and observation records in the database."""
    m = Merchant(id="merch_atlas_travel", name="Atlas Travel Gear", currency="INR", status="ACTIVE")
    exp_rec = ExperimentRecord(
        id="exp_immu_01",
        merchant_id="merch_atlas_travel",
        name="Immutability Exp",
        control_policy_id="p_ctrl",
        treatment_policy_id="p_treat",
        control_proposal_snapshot={"merchant_id": "merch_atlas_travel"},
        treatment_proposal_snapshot={"merchant_id": "merch_atlas_travel"},
        hypothesis={
            "population_description": "Target",
            "control_description": "Ctrl",
            "treatment_description": "Treat",
            "expected_direction": "HIGHER",
            "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
            "rationale": "Rationale"
        },
        status="COMPLETED"
    )
    obs_rec = ObservationRecord(
        id="obs_immu_01",
        experiment_id="exp_immu_01",
        scenario_id="scen_immu_01",
        variant="TREATMENT",
        outcome_type="SIMULATED",
        is_selected=True,
        revenue_paise=349900,
        contribution_paise=179900,
        margin_percent=51.41,
        guardrail_violations=[],
        idempotency_key="obs_exp_immu_01_scen_immu_01_TREATMENT"
    )
    db_session.add_all([m, exp_rec, obs_rec])
    await db_session.commit()
    return exp_rec, obs_rec


@pytest.mark.asyncio
async def test_observation_ingestion_idempotency_and_deduplication(db_session, setup_experiment_data):
    """Replaying or re-ingesting an observation returns the existing record without duplicate insertion."""
    service = LearningEvidenceService()
    exp_rec, obs_rec = setup_experiment_data

    exp = PolicyExperiment(
        experiment_id=exp_rec.id,
        merchant_id=exp_rec.merchant_id,
        name=exp_rec.name,
        control_policy_id=exp_rec.control_policy_id,
        treatment_policy_id=exp_rec.treatment_policy_id,
        control_proposal_snapshot=exp_rec.control_proposal_snapshot,
        treatment_proposal_snapshot=exp_rec.treatment_proposal_snapshot,
        hypothesis=ExperimentHypothesis(**exp_rec.hypothesis),
        status=ExperimentStatus.COMPLETED
    )

    obs = ExperimentObservation(
        observation_id=obs_rec.id,
        experiment_id=obs_rec.experiment_id,
        scenario_id=obs_rec.scenario_id,
        variant=VariantType.TREATMENT,
        outcome_type=obs_rec.outcome_type,
        is_selected=obs_rec.is_selected,
        revenue_paise=obs_rec.revenue_paise,
        contribution_paise=obs_rec.contribution_paise,
        margin_percent=float(obs_rec.margin_percent),
        idempotency_key=obs_rec.idempotency_key,
        observed_at=datetime.now(timezone.utc)
    )

    intent = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=400000, currency="INR"),
        requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6)]
    )

    # 1. First Ingestion -> Creates record
    evi_1 = await service.ingest_observation(db_session, obs, exp, intent=intent)
    assert evi_1.evidence_id.startswith("evi_")
    assert evi_1.learning_eligible is True

    # 2. Duplicate Ingestion Attempt -> Returns existing record with same ID
    evi_2 = await service.ingest_observation(db_session, obs, exp, intent=intent)
    assert evi_2.evidence_id == evi_1.evidence_id
    assert evi_2.idempotency_key == evi_1.idempotency_key

    # 3. Verify exactly 1 record exists in DB
    from sqlalchemy import select, func
    count_stmt = select(func.count(LearningEvidenceRecord.id)).where(
        LearningEvidenceRecord.experiment_id == "exp_immu_01"
    )
    total_count = (await db_session.execute(count_stmt)).scalar()
    assert total_count == 1
