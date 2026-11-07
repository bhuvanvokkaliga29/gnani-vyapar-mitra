"""Experiment Service: Lifecycle state management, persistent storage, and tenant isolation."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from domain.models import ExperimentRecord, ObservationRecord, Merchant
from domain.intent_schemas import BuyerIntent
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentObservation,
    ExperimentResult,
    ExperimentStatus,
    CreateExperimentRequest,
    VariantType
)
from services.experiments.errors import (
    ExperimentError,
    InvalidExperimentStateError,
    CrossTenantViolationError,
    DuplicateObservationError
)
from services.experiments.diff import PolicyDiffEngine
from services.experiments.validator import ExperimentValidator
from services.experiments.assignment import AssignmentEngine
from services.experiments.metrics import ExperimentMetricEngine
from services.experiments.evaluator import ExperimentEvaluator
from services.experiments.runner import ExperimentRunner

logger = structlog.get_logger()


class ExperimentService:
    """Orchestrates experiment creation, execution, metrics aggregation, and evaluation."""

    def __init__(self, runner: Optional[ExperimentRunner] = None):
        self.runner = runner or ExperimentRunner()
        self.validator = ExperimentValidator()

    async def create_experiment(
        self,
        db: AsyncSession,
        request: CreateExperimentRequest,
        control_proposal: Dict[str, Any],
        treatment_proposal: Dict[str, Any]
    ) -> PolicyExperiment:
        """Create a new experiment in DRAFT status after computing policy diff and initial pre-flight check."""
        exp_id = f"exp_{uuid.uuid4().hex[:12]}"

        # Compute isolated policy diff
        diff = PolicyDiffEngine.compute_diff(
            control_snapshot=control_proposal,
            treatment_snapshot=treatment_proposal
        )

        experiment = PolicyExperiment(
            experiment_id=exp_id,
            experiment_version="policy-experiment/v1",
            merchant_id=request.merchant_id,
            name=request.name,
            population_scenarios=request.population_scenarios,
            control_policy_id=request.control_policy_id,
            treatment_policy_id=request.treatment_policy_id,
            control_proposal_snapshot=control_proposal,
            treatment_proposal_snapshot=treatment_proposal,
            policy_diff=diff,
            hypothesis=request.hypothesis,
            primary_metric=request.primary_metric,
            secondary_metrics=request.secondary_metrics,
            guardrails=request.guardrails,
            randomization_seed=request.randomization_seed,
            assignment_strategy=request.assignment_strategy,
            status=ExperimentStatus.DRAFT,
            created_at=datetime.now(timezone.utc)
        )

        # Pre-flight check
        self.validator.validate_preflight(experiment)

        # Persist to database
        db_exp = ExperimentRecord(
            id=experiment.experiment_id,
            merchant_id=experiment.merchant_id,
            name=experiment.name,
            status=experiment.status.value,
            control_policy_id=experiment.control_policy_id,
            treatment_policy_id=experiment.treatment_policy_id,
            control_proposal_snapshot=experiment.control_proposal_snapshot,
            treatment_proposal_snapshot=experiment.treatment_proposal_snapshot,
            hypothesis=experiment.hypothesis.model_dump(),
            guardrails=[g.model_dump() for g in experiment.guardrails],
            primary_metric=experiment.primary_metric,
            secondary_metrics=experiment.secondary_metrics,
            randomization_seed=experiment.randomization_seed,
            assignment_strategy=experiment.assignment_strategy.value,
            population_scenarios=experiment.population_scenarios,
            policy_diff=experiment.policy_diff.model_dump() if experiment.policy_diff else None,
            sample_size_target=experiment.sample_size_target
        )
        db.add(db_exp)
        await db.commit()

        return experiment

    async def get_experiment(
        self,
        db: AsyncSession,
        experiment_id: str,
        merchant_id: str
    ) -> Optional[PolicyExperiment]:
        """Retrieve an experiment, enforcing tenant isolation."""
        stmt = select(ExperimentRecord).where(
            and_(
                ExperimentRecord.id == experiment_id,
                ExperimentRecord.merchant_id == merchant_id
            )
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            return None

        return PolicyExperiment(
            experiment_id=record.id,
            experiment_version="policy-experiment/v1",
            merchant_id=record.merchant_id,
            name=record.name,
            population_scenarios=record.population_scenarios,
            control_policy_id=record.control_policy_id,
            treatment_policy_id=record.treatment_policy_id,
            control_proposal_snapshot=record.control_proposal_snapshot,
            treatment_proposal_snapshot=record.treatment_proposal_snapshot,
            policy_diff=record.policy_diff,
            hypothesis=record.hypothesis,
            primary_metric=record.primary_metric,
            secondary_metrics=record.secondary_metrics,
            guardrails=record.guardrails,
            randomization_seed=record.randomization_seed,
            assignment_strategy=record.assignment_strategy,
            status=ExperimentStatus(record.status),
            sample_size_target=record.sample_size_target,
            created_at=record.created_at,
            start_at=record.start_at,
            end_at=record.end_at
        )

    async def start_experiment(
        self,
        db: AsyncSession,
        experiment_id: str,
        merchant_id: str
    ) -> PolicyExperiment:
        """Validate and transition an experiment from DRAFT to RUNNING."""
        exp = await self.get_experiment(db, experiment_id, merchant_id)
        if not exp:
            raise CrossTenantViolationError(f"Experiment '{experiment_id}' not found for merchant '{merchant_id}'.")

        self.validator.validate_preflight(exp)
        self.validator.validate_state_transition(exp.status, ExperimentStatus.RUNNING)

        stmt = select(ExperimentRecord).where(ExperimentRecord.id == experiment_id)
        record = (await db.execute(stmt)).scalar_one()
        record.status = ExperimentStatus.RUNNING.value
        record.start_at = datetime.now(timezone.utc)
        await db.commit()

        exp.status = ExperimentStatus.RUNNING
        exp.start_at = record.start_at
        return exp

    async def record_observation(
        self,
        db: AsyncSession,
        observation: ExperimentObservation
    ) -> ExperimentObservation:
        """Record an observation idempotently into the audit database."""
        # Check idempotency
        stmt = select(ObservationRecord).where(ObservationRecord.idempotency_key == observation.idempotency_key)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            # Return existing record idempotently
            return ExperimentObservation(
                observation_id=existing.id,
                experiment_id=existing.experiment_id,
                scenario_id=existing.scenario_id,
                variant=VariantType(existing.variant),
                outcome_type=existing.outcome_type,
                buyer_selection_result_id=existing.buyer_selection_result_id,
                selected_offer_id=existing.selected_offer_id,
                is_selected=existing.is_selected,
                execution_id=existing.execution_id,
                order_id=existing.order_id,
                razorpay_order_id=existing.razorpay_order_id,
                payment_outcome=existing.payment_outcome,
                revenue_paise=existing.revenue_paise,
                contribution_paise=existing.contribution_paise,
                margin_percent=float(existing.margin_percent),
                guardrail_violations=existing.guardrail_violations,
                observed_at=existing.observed_at,
                idempotency_key=existing.idempotency_key
            )

        db_obs = ObservationRecord(
            id=observation.observation_id,
            experiment_id=observation.experiment_id,
            scenario_id=observation.scenario_id,
            variant=observation.variant.value,
            outcome_type=observation.outcome_type.value,
            buyer_selection_result_id=observation.buyer_selection_result_id,
            selected_offer_id=observation.selected_offer_id,
            is_selected=observation.is_selected,
            execution_id=observation.execution_id,
            order_id=observation.order_id,
            razorpay_order_id=observation.razorpay_order_id,
            payment_outcome=observation.payment_outcome,
            revenue_paise=observation.revenue_paise,
            contribution_paise=observation.contribution_paise,
            margin_percent=observation.margin_percent,
            guardrail_violations=observation.guardrail_violations,
            idempotency_key=observation.idempotency_key
        )
        db.add(db_obs)
        await db.commit()
        return observation

    async def run_experiment_population(
        self,
        db: AsyncSession,
        experiment_id: str,
        merchant_id: str,
        scenarios: Dict[str, BuyerIntent],
        execute_test_mode_orders: bool = False
    ) -> ExperimentResult:
        """Run all population scenarios through assigned arms, record observations, and compute result."""
        exp = await self.get_experiment(db, experiment_id, merchant_id)
        if not exp:
            raise CrossTenantViolationError(f"Experiment '{experiment_id}' not found for merchant '{merchant_id}'.")

        if exp.status != ExperimentStatus.RUNNING:
            # Auto-start if validated/ready
            exp = await self.start_experiment(db, experiment_id, merchant_id)

        # Assign scenarios deterministically
        assignments = AssignmentEngine.assign_population(
            experiment_id=exp.experiment_id,
            scenario_ids=exp.population_scenarios,
            randomization_seed=exp.randomization_seed,
            strategy=exp.assignment_strategy
        )

        # Execute each scenario
        for scenario_id, variant in assignments:
            intent = scenarios.get(scenario_id, BuyerIntent())
            obs = await self.runner.run_scenario(
                experiment=exp,
                scenario_id=scenario_id,
                intent=intent,
                assigned_variant=variant,
                db=db,
                execute_test_mode_orders=execute_test_mode_orders
            )
            await self.record_observation(db, obs)

        # Compute result
        result = await self.get_experiment_result(db, experiment_id, merchant_id)

        # Mark completed
        stmt = select(ExperimentRecord).where(ExperimentRecord.id == experiment_id)
        rec = (await db.execute(stmt)).scalar_one()
        rec.status = ExperimentStatus.COMPLETED.value
        rec.end_at = datetime.now(timezone.utc)
        await db.commit()

        return result

    async def get_experiment_result(
        self,
        db: AsyncSession,
        experiment_id: str,
        merchant_id: str
    ) -> ExperimentResult:
        """Compute aggregated metrics, evaluate guardrails, and determine winner."""
        exp = await self.get_experiment(db, experiment_id, merchant_id)
        if not exp:
            raise CrossTenantViolationError(f"Experiment '{experiment_id}' not found for merchant '{merchant_id}'.")

        # Fetch observations
        stmt = select(ObservationRecord).where(ObservationRecord.experiment_id == experiment_id)
        records = (await db.execute(stmt)).scalars().all()

        ctrl_obs = []
        treat_obs = []
        for r in records:
            obs = ExperimentObservation(
                observation_id=r.id,
                experiment_id=r.experiment_id,
                scenario_id=r.scenario_id,
                variant=VariantType(r.variant),
                outcome_type=r.outcome_type,
                buyer_selection_result_id=r.buyer_selection_result_id,
                selected_offer_id=r.selected_offer_id,
                is_selected=r.is_selected,
                execution_id=r.execution_id,
                order_id=r.order_id,
                razorpay_order_id=r.razorpay_order_id,
                payment_outcome=r.payment_outcome,
                revenue_paise=r.revenue_paise,
                contribution_paise=r.contribution_paise,
                margin_percent=float(r.margin_percent),
                guardrail_violations=r.guardrail_violations,
                idempotency_key=r.idempotency_key,
                observed_at=r.observed_at
            )
            if obs.variant == VariantType.CONTROL:
                ctrl_obs.append(obs)
            else:
                treat_obs.append(obs)

        # Aggregate metrics
        ctrl_metrics = ExperimentMetricEngine.aggregate_variant_metrics(ctrl_obs)
        treat_metrics = ExperimentMetricEngine.aggregate_variant_metrics(treat_obs)

        # Deltas
        deltas = ExperimentMetricEngine.compute_metric_deltas(ctrl_metrics, treat_metrics)

        # Guardrails
        diff_margin = exp.policy_diff.treatment_margin_percent if exp.policy_diff else 0.0
        guardrail_res = ExperimentMetricEngine.evaluate_guardrails(
            guardrails=exp.guardrails,
            treatment_metrics=treat_metrics,
            policy_diff_margin=diff_margin
        )

        # Winner & Evidence Synthesis
        return ExperimentEvaluator.evaluate_experiment(
            experiment=exp,
            control_metrics=ctrl_metrics,
            treatment_metrics=treat_metrics,
            metric_deltas=deltas,
            guardrail_results=guardrail_res
        )
