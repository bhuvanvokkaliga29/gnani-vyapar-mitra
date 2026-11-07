"""Typed Pydantic Schemas for Phase 8.9 Closed-Loop Learning Evaluation.

Contract: closed-loop-evaluation/v1

Enforces:
- Deterministic Evaluation contract representation.
- Strict population separation (Training, Evaluation, Holdout).
- Immutable snapshot semantics.
- Authoritative reporting across SIMULATION, CONTROLLED_TEST_MODE, and REPLAY modes.
- Strict semantic hygiene: no equating simulation to live commerce transactions or selection to payment.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

EVALUATION_SCHEMA_VERSION = "closed-loop-evaluation/v1"


class EvaluationMode(str, Enum):
    """Execution modality of the closed-loop evaluation."""
    SIMULATION = "SIMULATION"
    CONTROLLED_TEST_MODE = "CONTROLLED_TEST_MODE"
    REPLAY = "REPLAY"


class EvaluationStatus(str, Enum):
    """Operational state of an evaluation run."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvaluationOutcome(str, Enum):
    """Definitive scientific outcome of the evaluation run."""
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PopulationDefinition(BaseModel):
    """Specification of an evaluated scenario/opportunity population partition."""
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(description="Unique dataset or scenario suite identifier")
    count: int = Field(ge=0, description="Total opportunities in this partition")
    scenario_ids: List[str] = Field(default_factory=list, description="Ordered scenario keys in partition")
    description: Optional[str] = Field(default=None, description="Human-readable description of partition")


class BaselineDefinition(BaseModel):
    """Authoritative deterministic non-learning baseline specification."""
    model_config = ConfigDict(extra="forbid")

    baseline_policy_id: str = Field(default="cand_base_no_offer", description="Baseline policy ID")
    baseline_name: str = Field(default="NO_OFFER", description="Canonical name of baseline strategy")
    description: str = Field(default="Zero-incentive reservation price fallback", description="Baseline rationale")


class EvaluationMetricSet(BaseModel):
    """Aggregated quantitative performance indicators over the training/evaluation dataset."""
    model_config = ConfigDict(extra="forbid")

    sample_size: int = Field(ge=0, description="Evaluated opportunities count")
    total_opportunities: int = Field(ge=0, description="Total opportunities offered")
    baseline_ecps_paise: int = Field(description="Baseline Expected Contribution per AI Shopper in integer paise")
    learned_ecps_paise: int = Field(description="Learned Policy Expected Contribution per AI Shopper in integer paise")
    absolute_delta_paise: int = Field(description="Learned ECPS - Baseline ECPS in integer paise")
    relative_delta: Optional[float] = Field(default=None, description="Percentage uplift over baseline if baseline > 0")
    selection_rate: float = Field(ge=0.0, le=1.0, description="Fraction of opportunities where AI buyer selected merchant offer")
    conversion_rate: float = Field(ge=0.0, le=1.0, description="Fraction of orders successfully executed/paid")
    exploration_rate: float = Field(ge=0.0, le=1.0, description="Fraction of decisions made in EXPLORE mode")
    exposure_paise_consumed: int = Field(ge=0, description="Total pre-decision economic exposure consumed in paise")
    safety_rejection_rate: float = Field(ge=0.0, le=1.0, description="Fraction of decisions rejected by Phase 8.6 safety gate")
    fallback_to_exploit_rate: float = Field(ge=0.0, le=1.0, description="Fraction of exploratory attempts falling back to exploit")
    model_updates_count: int = Field(ge=0, description="Total incremental LinUCB parameter updates performed")
    std_deviation_paise: float = Field(ge=0.0, description="Sample standard deviation of observed contribution in paise")
    confidence_interval_95_paise: Tuple[float, float] = Field(description="95% confidence interval of mean contribution (lower, upper)")


class LearningCurveCheckpoint(BaseModel):
    """Snapshot of learning progress at deterministic evidence accumulation intervals."""
    model_config = ConfigDict(extra="forbid")

    checkpoint_index: int = Field(ge=0, description="Sequence index of checkpoint")
    progress_percent: int = Field(ge=0, le=100, description="Completion percentage (0, 25, 50, 75, 100)")
    opportunities_evaluated: int = Field(ge=0, description="Cumulative opportunities processed up to this point")
    cumulative_ecps_paise: int = Field(description="Cumulative ECPS in integer paise at this checkpoint")
    cumulative_selection_rate: float = Field(ge=0.0, le=1.0, description="Cumulative AI buyer selection rate")
    cumulative_exploration_rate: float = Field(ge=0.0, le=1.0, description="Cumulative exploration decision rate")
    model_observation_count: int = Field(ge=0, description="Model internal observation count")
    timestamp: datetime = Field(description="Timestamp of checkpoint snapshot")


class HoldoutMetricSet(BaseModel):
    """Generalization metrics on unseen holdout opportunities evaluated with a frozen model."""
    model_config = ConfigDict(extra="forbid")

    holdout_sample_size: int = Field(ge=0, description="Holdout opportunities evaluated")
    holdout_ecps_paise: int = Field(description="Holdout ECPS in integer paise under frozen model")
    baseline_ecps_paise: int = Field(description="Baseline ECPS in integer paise on holdout set")
    absolute_delta_paise: int = Field(description="Holdout ECPS - Baseline ECPS in integer paise")
    relative_delta: Optional[float] = Field(default=None, description="Holdout percentage uplift over baseline")
    holdout_selection_rate: float = Field(ge=0.0, le=1.0, description="Holdout AI buyer selection rate")
    holdout_safety_rejection_rate: float = Field(ge=0.0, le=1.0, description="Holdout safety rejection rate")


class EvaluationDiagnostics(BaseModel):
    """Structural invariant verifications confirming architectural compliance."""
    model_config = ConfigDict(extra="forbid")

    cold_start_verified: bool = Field(description="Cold start state verified with zero prior observations")
    exploration_bounds_verified: bool = Field(description="Exploration opportunities and exposure adhered to budget limits")
    safety_invariants_verified: bool = Field(description="Phase 8.6 safety gate was invoked for all opportunities")
    promotion_audit_verified: bool = Field(description="Promotion criteria evaluated without evaluator fiat")
    determinism_verified: bool = Field(description="Deterministic reproducibility confirmed with fixed seed")
    tenant_isolation_verified: bool = Field(description="Multi-tenant boundary strictly maintained")
    failure_injection_verified: bool = Field(description="System recovered cleanly under simulated failures")
    zero_leakage_verified: bool = Field(description="Pre-update scoring confirmed; holdout remained completely unseen")


class ClosedLoopEvaluationConfig(BaseModel):
    """Authoritative evaluation configuration envelope."""
    model_config = ConfigDict(extra="forbid")

    mode: EvaluationMode = Field(default=EvaluationMode.SIMULATION, description="SIMULATION, CONTROLLED_TEST_MODE, or REPLAY")
    baseline_policy_id: str = Field(default="cand_base_no_offer", description="Baseline policy ID")
    training_sample_size: int = Field(default=40, ge=10, description="Number of training opportunities")
    holdout_sample_size: int = Field(default=10, ge=1, description="Number of unseen holdout opportunities")
    checkpoints_count: int = Field(default=5, ge=2, description="Number of learning curve checkpoints")
    randomization_seed: int = Field(default=42, description="Randomization seed for determinism")
    min_ecps_improvement_paise: int = Field(default=0, description="Minimum absolute ECPS uplift required for PASS")
    max_tolerated_safety_rejections_percent: float = Field(default=20.0, ge=0.0, le=100.0, description="Max tolerated safety rejection rate")
    require_holdout_non_negative: bool = Field(default=True, description="Whether holdout delta must be >= 0 for PASS")
    config_version: str = Field(default=EVALUATION_SCHEMA_VERSION, description="Configuration schema version")


class ClosedLoopEvaluationRequest(BaseModel):
    """Input payload to launch or replay a closed-loop learning evaluation."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=1, max_length=64, description="Merchant tenant ID")
    mode: EvaluationMode = Field(default=EvaluationMode.SIMULATION, description="Evaluation modality")
    dataset_id: str = Field(default="default_benchmark_v1", description="Dataset or scenario suite identifier")
    config: Optional[ClosedLoopEvaluationConfig] = Field(default=None, description="Optional custom evaluation config")
    idempotency_key: Optional[str] = Field(default=None, description="Optional idempotency key")
    evaluation_version: str = Field(default=EVALUATION_SCHEMA_VERSION, description="Contract version")


class ClosedLoopEvaluationResult(BaseModel):
    """Authoritative immutable outcome of a closed-loop learning evaluation run."""
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(description="Unique evaluation identifier (eval_...)")
    merchant_id: str = Field(description="Merchant tenant ID")
    mode: EvaluationMode = Field(description="Evaluation modality executed")
    status: EvaluationStatus = Field(description="RUNNING, COMPLETED, or FAILED")
    overall_outcome: EvaluationOutcome = Field(description="PASS, FAIL, INCONCLUSIVE, or INSUFFICIENT_EVIDENCE")
    dataset_id: str = Field(description="Evaluated scenario set identifier")
    baseline_definition: BaselineDefinition = Field(description="Baseline definition applied")
    training_definition: PopulationDefinition = Field(description="Training set partition specification")
    evaluation_definition: PopulationDefinition = Field(description="Evaluation partition specification")
    holdout_definition: PopulationDefinition = Field(description="Holdout partition specification")
    config: ClosedLoopEvaluationConfig = Field(description="Configuration applied")
    seed: int = Field(description="Randomization seed applied")
    summary_metrics: EvaluationMetricSet = Field(description="Aggregate training & evaluation metrics")
    learning_curve: List[LearningCurveCheckpoint] = Field(description="Sequential learning curve checkpoints")
    holdout_metrics: HoldoutMetricSet = Field(description="Generalization metrics on unseen holdout set")
    diagnostics: EvaluationDiagnostics = Field(description="Architectural invariant verification results")
    warnings: List[str] = Field(default_factory=list, description="Methodological caveats or diagnostic warnings")
    failure_reasons: List[str] = Field(default_factory=list, description="Detailed failure causes if not PASS")
    contract_versions: Dict[str, str] = Field(description="Frozen versions of all constituent service contracts")
    created_at: datetime = Field(description="Timestamp evaluation was initialized")
    completed_at: Optional[datetime] = Field(default=None, description="Timestamp evaluation concluded")
