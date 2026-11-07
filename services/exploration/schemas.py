"""Typed Pydantic Schemas for Constrained Exploration / Exploitation Engine.

Contract: policy-exploration/v1
Enforces strict schema validation, extra="forbid", and zero float currency.
Preserves explicit separation of concerns:
- Exploitation path preserves Phase 8.5 selection.
- Exploration path chooses uncertainty-aware alternatives under strict budget and exposure limits.
- Every decision must pass Phase 8.6 safety gate.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

from domain.intent_schemas import BuyerIntent
from services.policy.schemas import PolicyCandidate
from services.selection.schemas import PolicySelectionResult

EXPLORATION_SCHEMA_VERSION = "policy-exploration/v1"


class ExplorationMode(str, Enum):
    """Decision mode: exploitation of learned preference or bounded exploration."""
    EXPLOIT = "EXPLOIT"
    EXPLORE = "EXPLORE"


class ExplorationReasonCode(str, Enum):
    """Deterministic, auditable explanation for the exploration / exploitation decision."""
    # Exploitation reasons
    EXPLOIT_DEFAULT = "EXPLOIT_DEFAULT"
    EXPLOIT_DISABLED = "EXPLOIT_DISABLED"
    EXPLOIT_NO_ALTERNATIVES = "EXPLOIT_NO_ALTERNATIVES"
    EXPLOIT_BUDGET_EXHAUSTED = "EXPLOIT_BUDGET_EXHAUSTED"
    EXPLOIT_EXPOSURE_LIMIT_REACHED = "EXPLOIT_EXPOSURE_LIMIT_REACHED"
    EXPLOIT_POLICY_CAP_REACHED = "EXPLOIT_POLICY_CAP_REACHED"
    EXPLOIT_CONTEXT_CAP_REACHED = "EXPLOIT_CONTEXT_CAP_REACHED"
    EXPLOIT_CONSECUTIVE_LIMIT_REACHED = "EXPLOIT_CONSECUTIVE_LIMIT_REACHED"
    EXPLOIT_TRIGGER_NOT_SATISFIED = "EXPLOIT_TRIGGER_NOT_SATISFIED"
    EXPLOIT_FALLBACK_EXPLORATION_UNSAFE = "EXPLOIT_FALLBACK_EXPLORATION_UNSAFE"

    # Exploration reasons
    EXPLORE_UNCERTAINTY_ADVANTAGE = "EXPLORE_UNCERTAINTY_ADVANTAGE"
    EXPLORE_UNDER_OBSERVED_POLICY = "EXPLORE_UNDER_OBSERVED_POLICY"
    EXPLORE_CONTEXT_GAP = "EXPLORE_CONTEXT_GAP"


class MerchantExplorationConfig(BaseModel):
    """Authoritative merchant risk and exploration control envelope."""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(default=True, description="Master switch enabling exploration for this merchant")
    max_exploration_opportunities: int = Field(default=20, ge=0, description="Max exploratory opportunities in window")
    max_consecutive_explorations: int = Field(default=3, ge=0, description="Max consecutive explorations before forced exploit")
    max_policy_exploration_count: int = Field(default=5, ge=0, description="Max times a single policy can be explored")
    max_context_exploration_count: int = Field(default=10, ge=0, description="Max explorations in a single buyer context class")
    max_exposure_paise: int = Field(default=500000, ge=0, description="Max cumulative economic exposure paise (₹5,000)")
    max_exposure_per_decision_paise: int = Field(default=150000, ge=0, description="Max exposure paise for a single decision (₹1,500)")
    max_underobserved_deficit_paise: int = Field(default=100000, ge=0, description="Max deficit paise below baseline permitted for under-observed exploration (₹1,000)")
    min_uncertainty_gap: float = Field(default=0.20, ge=0.0, description="Required uncertainty gap vs exploit candidate")
    min_observations_threshold: int = Field(default=5, ge=0, description="Threshold below which policy is under-observed")
    alpha_paise: int = Field(default=10000, ge=0, description="Uncertainty weight multiplier in integer paise")
    window_id: str = Field(default="daily", description="Audit window identifier (daily = win_YYYY-MM-DD)")
    config_version: str = Field(default="exp-config/v1", description="Configuration schema version")

    def resolve_window_id(self, dt: Optional[datetime] = None) -> str:
        """Resolve canonical UTC daily window identity win_YYYY-MM-DD."""
        if self.window_id and self.window_id not in ("daily", "window_default"):
            return self.window_id
        target_dt = dt or datetime.now(timezone.utc)
        return f"win_{target_dt.strftime('%Y-%m-%d')}"


class ExplorationDecision(BaseModel):
    """Authoritative decision output conforming to policy-exploration/v1."""
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(description="Unique decision ID (exp_...)")
    merchant_id: str = Field(description="Merchant tenant ID")
    opportunity_id: str = Field(description="Canonical opportunity identifier")
    buyer_context_key: str = Field(description="Buyer context key")
    mode: ExplorationMode = Field(description="EXPLOIT or EXPLORE")
    exploit_policy_id: str = Field(description="Phase 8.5 chosen exploitation policy ID")
    exploit_policy_version: str = Field(description="Exploit policy contract version")
    selected_policy_id: str = Field(description="Final chosen policy ID (exploit or explore)")
    selected_policy_version: str = Field(description="Final chosen policy contract version")
    selected_policy: PolicyCandidate = Field(description="Full payload of the chosen candidate policy")
    predicted_contribution_paise: int = Field(description="Predicted contribution in integer paise")
    uncertainty: float = Field(description="Predictive uncertainty of the chosen policy")
    ucb_score_paise: int = Field(description="UCB score in integer paise")
    exposure_paise: int = Field(default=0, ge=0, description="Exact pre-decision economic exposure consumed in paise")
    exploration_trigger: Optional[str] = Field(default=None, description="Trigger rule that fired if explored")
    reason_code: ExplorationReasonCode = Field(description="Canonical deterministic reason code")
    safety_check_reference: Optional[str] = Field(default=None, description="Phase 8.6 safety check ID reference")
    exploration_budget_state: Dict[str, Any] = Field(description="Snapshot of budget state at decision time")
    policy_exposure_state: Dict[str, Any] = Field(description="Snapshot of per-policy exposure at decision time")
    context_exposure_state: Dict[str, Any] = Field(description="Snapshot of per-context exposure at decision time")
    model_version: str = Field(default="learning-model/v1", description="Phase 8.4 model version")
    feature_version: str = Field(default="feature-schema/v1", description="Phase 8.4 feature version")
    selection_version: str = Field(default="policy-selection/v1", description="Phase 8.5 selection version")
    exploration_version: str = Field(default=EXPLORATION_SCHEMA_VERSION, description="Contract version")
    config_version: str = Field(default="exp-config/v1", description="Configuration version applied")
    decision_timestamp: datetime = Field(description="Timestamp when decision was made")


class ExplorationRequest(BaseModel):
    """Input payload for exploration/exploitation decision."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=1, max_length=64, description="Merchant tenant ID")
    opportunity_id: str = Field(min_length=1, max_length=128, description="Opportunity identifier")
    buyer_context_key: str = Field(min_length=1, max_length=128, description="Buyer context key")
    intent: BuyerIntent = Field(description="Buyer intent")
    candidates: List[PolicyCandidate] = Field(min_length=1, description="Candidate slate from Phase 4")
    selection_result: Optional[PolicySelectionResult] = Field(default=None, description="Optional pre-computed Phase 8.5 result")
    config: Optional[MerchantExplorationConfig] = Field(default=None, description="Optional merchant risk configuration")
    exploration_version: str = Field(default=EXPLORATION_SCHEMA_VERSION, description="Contract version")
