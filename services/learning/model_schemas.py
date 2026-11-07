"""Typed Pydantic schemas for Phase 8.4 Merchant Policy Learning Model.

Contract Version: learning-model/v1
Algorithm Version: learning-algorithm/v1
Feature Version: feature-schema/v1
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import PolicyCandidate

MODEL_CONTRACT_VERSION = "learning-model/v1"


class LearningModelStateSchema(BaseModel):
    """Full typed representation of a merchant's contextual learning model state."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Model state record ID (lms_...)")
    merchant_id: str = Field(..., description="Merchant tenant ID")
    model_version: str = Field(default=MODEL_CONTRACT_VERSION)
    algorithm_version: str = Field(default="learning-algorithm/v1")
    feature_version: str = Field(default="feature-schema/v1")
    reward_version: str = Field(default="merchant-reward/v1")
    formula_version: str = Field(default="contribution-formula/v1")
    dimension: int = Field(default=19, description="Feature vector dimension")
    lambda_reg: float = Field(default=1.0, description="L2 ridge regularization parameter")
    alpha_paise: int = Field(default=10000, description="Exploration confidence multiplier in paise")
    observation_count: int = Field(default=0, description="Number of eligible observations trained")
    version: int = Field(default=1, description="Optimistic locking version")
    last_updated_at: datetime = Field(..., description="Timestamp of last update")


class ModelPredictionSchema(BaseModel):
    """Authoritative prediction output from the contextual linear learning model.
    
    CRITICAL: Contains mathematical predictions and diagnostics ONLY.
    Does NOT contain 'recommended', 'winner', 'execute', or 'approved' flags.
    """
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., description="Merchant tenant ID")
    policy_id: str = Field(..., description="Evaluated policy ID")
    policy_version: str = Field(default="merchant-policy/v1")
    buyer_context_key: str = Field(..., description="Commercial intent context fingerprint")
    
    # Statistical Outputs
    predicted_contribution_paise: int = Field(..., description="Expected merchant contribution in integer paise (can be negative)")
    uncertainty: float = Field(..., description="Predictive standard deviation multiplier sqrt(xᵀ A⁻¹ x)")
    ucb_score_paise: int = Field(..., description="Diagnostic upper confidence bound score in paise")
    
    # Provenance & Versioning
    model_version: str = Field(default=MODEL_CONTRACT_VERSION)
    algorithm_version: str = Field(default="learning-algorithm/v1")
    feature_version: str = Field(default="feature-schema/v1")
    observation_count: int = Field(..., description="Observations seen by this merchant model")
    prediction_timestamp: datetime = Field(default_factory=datetime.utcnow)


class CandidatePredictionRequestSchema(BaseModel):
    """Request payload to predict expected contribution for a candidate policy under a context."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., description="Merchant tenant ID")
    policy_id: str = Field(..., description="Candidate policy ID")
    policy_version: Optional[str] = Field(default="merchant-policy/v1")
    buyer_context_key: str = Field(..., description="Target buyer context key")
    intent: Optional[BuyerIntent] = Field(default=None, description="Pre-decision buyer intent if available")
    candidate: Optional[PolicyCandidate] = Field(default=None, description="Pre-decision candidate proposal if available")
    candidate_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="Proposal snapshot dict")


class ModelRebuildRequestSchema(BaseModel):
    """Request payload to rebuild the merchant's model from Phase 8.3 historical memory."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., description="Merchant tenant ID")
    cutoff_time: Optional[datetime] = Field(default=None, description="Optional historical cutoff timestamp (T)")
    lambda_reg: Optional[float] = Field(default=1.0, gt=0, description="Regularization parameter")
    alpha_paise: Optional[int] = Field(default=10000, ge=0, description="Exploration multiplier in paise")


class ModelRebuildResponseSchema(BaseModel):
    """Response payload following a deterministic model rebuild."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., description="Merchant tenant ID")
    observation_count: int = Field(..., description="Number of current-effective observations incorporated")
    rebuilt_at: datetime = Field(default_factory=datetime.utcnow)
    dimension: int = Field(default=19)
    model_version: str = Field(default=MODEL_CONTRACT_VERSION)
