"""Contextual Linear Upper Confidence Bound (LinUCB) implementation for Phase 8.4.

Contract Version: learning-algorithm/v1
Algorithm: Merchant-Specific Contextual Linear UCB
"""

import math
from typing import Dict, Any, Tuple, List, Optional
from services.learning.features import FEATURE_DIMENSION, FEATURE_SCHEMA_VERSION
from services.learning.model_errors import (
    CorruptedModelStateError,
    IncompatibleFeatureSchemaError
)
from services.learning.linalg import (
    eye,
    zeros,
    dot,
    cholesky_solve,
    compute_uncertainty
)

ALGORITHM_VERSION = "learning-algorithm/v1"
DEFAULT_LAMBDA = 1.0
DEFAULT_ALPHA_PAISE = 10000  # ₹100 uncertainty multiplier in paise
REWARD_SCALE_FACTOR = 100.0  # 1 unit in model space = 100 paise = ₹1.0


class ContextualLinearUCB:
    """Merchant-specific contextual linear model estimating expected contribution and uncertainty.
    
    Model formulation:
        E[R | x] ≈ xᵀθ*
    
    Maintains sufficient statistics:
        A = λI + ∑ x_i x_iᵀ
        b = ∑ x_i r_i
    
    Predicts:
        predicted_reward_paise = round((xᵀ θ̂) * 100)
        uncertainty = sqrt(xᵀ A⁻¹ x)
        ucb_score_paise = predicted_reward_paise + round(alpha_paise * uncertainty)
    """

    def __init__(
        self,
        merchant_id: str,
        dimension: int = FEATURE_DIMENSION,
        lambda_reg: float = DEFAULT_LAMBDA,
        alpha_paise: int = DEFAULT_ALPHA_PAISE
    ):
        if dimension <= 0:
            raise CorruptedModelStateError(f"Invalid dimension {dimension}. Must be > 0.")
        if lambda_reg <= 0:
            raise CorruptedModelStateError(f"Invalid lambda_reg {lambda_reg}. Must be > 0.")

        self.merchant_id = merchant_id
        self.dimension = dimension
        self.lambda_reg = float(lambda_reg)
        self.alpha_paise = int(alpha_paise)
        self.algorithm_version = ALGORITHM_VERSION
        self.feature_version = FEATURE_SCHEMA_VERSION

        # Sufficient statistics (pure-Python 2D and 1D lists)
        self.A: List[List[float]] = eye(self.dimension, self.lambda_reg)
        self.b: List[float] = zeros(self.dimension)
        self.theta: List[float] = zeros(self.dimension)
        self.observation_count = 0

    def update(self, x: List[float], reward_paise: int) -> None:
        """Incrementally update sufficient statistics with an authoritative observation.
        
        Preserves negative contribution, zero contribution, and positive contribution.
        """
        self._validate_feature_vector(x)
        if not isinstance(reward_paise, int):
            raise CorruptedModelStateError(f"reward_paise must be an integer, got {type(reward_paise)}.")

        # Scale reward from integer paise to model units (rupees)
        r_model = float(reward_paise) / REWARD_SCALE_FACTOR

        # Rank-1 update: A ← A + x xᵀ, b ← b + x r
        for i in range(self.dimension):
            xi = x[i]
            self.b[i] += xi * r_model
            for j in range(self.dimension):
                self.A[i][j] += xi * x[j]

        self.observation_count += 1

        # Stable linear solve: A θ = b
        self._recompute_theta()

    def batch_update(self, X: List[List[float]], rewards_paise: List[int]) -> None:
        """Batch update or rebuild sufficient statistics deterministically."""
        if len(X) != len(rewards_paise):
            raise CorruptedModelStateError(
                f"Feature matrix rows {len(X)} != rewards count {len(rewards_paise)}."
            )

        for x, r in zip(X, rewards_paise):
            self.update(x, r)

    def predict(self, x: List[float]) -> Tuple[int, float, int]:
        """Predict expected contribution, uncertainty, and diagnostic UCB score.
        
        Returns:
            (predicted_contribution_paise, uncertainty_sigma, ucb_score_paise)
        """
        self._validate_feature_vector(x)

        # Expected reward in model units (rupees)
        pred_model = dot(x, self.theta)
        predicted_paise = int(round(pred_model * REWARD_SCALE_FACTOR))

        # Numerically stable uncertainty via Cholesky decomposition: ||L⁻¹ x||₂
        uncertainty = compute_uncertainty(self.A, x)
        ucb_score_paise = int(round(predicted_paise + (self.alpha_paise * uncertainty)))

        return predicted_paise, uncertainty, ucb_score_paise

    def reset_cold_start(self) -> None:
        """Reset the model to the deterministic cold-start state."""
        self.A = eye(self.dimension, self.lambda_reg)
        self.b = zeros(self.dimension)
        self.theta = zeros(self.dimension)
        self.observation_count = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize model state to JSON-compatible dictionary."""
        return {
            "merchant_id": self.merchant_id,
            "algorithm_version": self.algorithm_version,
            "feature_version": self.feature_version,
            "dimension": self.dimension,
            "lambda_reg": self.lambda_reg,
            "alpha_paise": self.alpha_paise,
            "observation_count": self.observation_count,
            "matrix_a": self.A,
            "vector_b": self.b,
            "theta": self.theta
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextualLinearUCB":
        """Deserialize model from dictionary, performing strict validation."""
        dim = data.get("dimension", FEATURE_DIMENSION)
        if dim != FEATURE_DIMENSION:
            raise IncompatibleFeatureSchemaError(
                f"Model dimension {dim} incompatible with feature schema ({FEATURE_DIMENSION})."
            )

        model = cls(
            merchant_id=data["merchant_id"],
            dimension=dim,
            lambda_reg=float(data.get("lambda_reg", DEFAULT_LAMBDA)),
            alpha_paise=int(data.get("alpha_paise", DEFAULT_ALPHA_PAISE))
        )

        matrix_a = data["matrix_a"]
        vector_b = data["vector_b"]
        theta = data["theta"]

        # Validate finite values and dimensions
        if len(matrix_a) != dim or any(len(row) != dim for row in matrix_a):
            raise CorruptedModelStateError("Deserialized Matrix A has invalid dimensions.")
        if len(vector_b) != dim or len(theta) != dim:
            raise CorruptedModelStateError("Deserialized vector b or theta has invalid dimension.")

        for row in matrix_a:
            if any(math.isnan(v) or math.isinf(v) for v in row):
                raise CorruptedModelStateError("Matrix A contains NaN or infinite values.")

        if any(math.isnan(v) or math.isinf(v) for v in vector_b):
            raise CorruptedModelStateError("Vector b contains NaN or infinite values.")

        if any(math.isnan(v) or math.isinf(v) for v in theta):
            raise CorruptedModelStateError("Vector theta contains NaN or infinite values.")

        model.A = matrix_a
        model.b = vector_b
        model.theta = theta
        model.observation_count = int(data.get("observation_count", 0))
        return model

    def _recompute_theta(self) -> None:
        """Solve A θ = b using Cholesky decomposition."""
        try:
            self.theta = cholesky_solve(self.A, self.b)
        except Exception as e:
            raise CorruptedModelStateError(f"Failed to solve A θ = b: {str(e)}")

        if any(math.isnan(v) or math.isinf(v) for v in self.theta):
            raise CorruptedModelStateError("Recomputed parameter vector theta contains NaN or Inf.")

    def _validate_feature_vector(self, x: List[float]) -> None:
        """Ensure feature vector is finite and matches dimension."""
        if len(x) != self.dimension:
            raise IncompatibleFeatureSchemaError(
                f"Feature vector dimension {len(x)} != expected ({self.dimension})."
            )
        if any(math.isnan(v) or math.isinf(v) for v in x):
            raise IncompatibleFeatureSchemaError("Feature vector contains NaN or infinite values.")
