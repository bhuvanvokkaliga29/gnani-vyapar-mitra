"""Phase 8.2 Learning Objective & Reward Layer: Mathematical Definition & Contract.

Contracts:
- merchant-reward/v1
- contribution-formula/v1
"""

from services.reward.schemas import (
    RewardState,
    ObjectiveMetricType,
    PolicyOpportunityReward,
    AggregatedRewardObjective,
    RewardEvaluationRequest,
    RewardAggregationRequest
)
from services.reward.errors import (
    RewardError,
    IneligibleRewardError,
    RewardDataUnavailableError,
    ZeroDenominatorError,
    RewardAttributionError,
    RewardLeakageError
)
from services.reward.calculator import (
    ContributionCalculator,
    RewardSignalEvaluator
)
from services.reward.aggregator import (
    ObjectiveAggregator
)

__all__ = [
    "RewardState",
    "ObjectiveMetricType",
    "PolicyOpportunityReward",
    "AggregatedRewardObjective",
    "RewardEvaluationRequest",
    "RewardAggregationRequest",
    "RewardError",
    "IneligibleRewardError",
    "RewardDataUnavailableError",
    "ZeroDenominatorError",
    "RewardAttributionError",
    "RewardLeakageError",
    "ContributionCalculator",
    "RewardSignalEvaluator",
    "ObjectiveAggregator"
]
