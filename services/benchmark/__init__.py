"""Phase 11.1 Canonical Benchmark Harness Package.

Contracts:
- benchmark-scenario/v1
- benchmark-result/v1
- benchmark-summary/v1
"""

from services.benchmark.schemas import (
    BENCHMARK_SCENARIO_VERSION,
    BENCHMARK_RESULT_VERSION,
    BENCHMARK_SUMMARY_VERSION,
    ScenarioCategory,
    BenchmarkStatus,
    FailureClass,
    ExpectationType,
    BenchmarkExecutionMode,
    BenchmarkExpectation,
    InitialProductSpec,
    InitialMerchantSpec,
    InitialStateSpec,
    BuyerContextInput,
    ExpectedTerminalState,
    BenchmarkScenario,
    ObservedStateSnapshot,
    AssertionDiagnostic,
    BenchmarkResult,
    BenchmarkSummary,
)
from services.benchmark.observer import BenchmarkObserver
from services.benchmark.assertions import AssertionEvaluator
from services.benchmark.runner import CanonicalBenchmarkRunner
from services.benchmark.registry import (
    BenchmarkRegistry,
    SCENARIO_SMOKE_HAPPY_PATH,
    SCENARIO_SMOKE_PAYMENT_FAILURE,
    SCENARIO_SMOKE_NO_OFFER,
    SCENARIO_SMOKE_REPLAY_IDEMPOTENCY,
)
from services.benchmark.reporter import BenchmarkReporter
from services.benchmark.golden_scenarios import (
    GOLDEN_SCENARIO_SUITE,
    SCENARIO_1_PAYMENT_FAILURE_TRUTH,
    SCENARIO_2_NO_OFFER_SHORT_CIRCUIT,
    SCENARIO_3_SAFETY_REJECTION_BLOCK,
    SCENARIO_4_STALE_STATE_REJECTION,
    SCENARIO_5_DUPLICATE_OUTCOME_ONCE,
    SCENARIO_6_LUCKY_PURCHASE_GATE,
    SCENARIO_7_LEARNING_NO_PROMOTION,
    SCENARIO_8_MERCHANT_BOUNDARY_ATTACK,
    SCENARIO_9_NEGATIVE_CONTRIBUTION,
    SCENARIO_10_EXECUTION_FAILURE_SHIELD,
)
from services.benchmark.economic_scenarios import (
    ECONOMIC_SCENARIOS,
    SCENARIO_ECON_ZERO_CONTRIBUTION,
    SCENARIO_ECON_NEGATIVE_CONTRIBUTION,
    SCENARIO_ECON_REVENUE_NOT_EQUAL_CONTRIBUTION,
    SCENARIO_ECON_BUNDLE_MULTI_ITEM_MATH,
    SCENARIO_ECON_MULTI_UNIT_QUANTITY,
    SCENARIO_ECON_INVENTORY_BARRIER,
    SCENARIO_ECON_NO_OFFER_BASELINE,
    SCENARIO_ECON_EXPECTED_VS_OBSERVED,
    SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS,
    SCENARIO_ECON_PROMOTION_GATING,
    SCENARIO_ECON_CROSS_MERCHANT_ISOLATION,
)
from services.benchmark.adaptive_scenarios import (
    ADAPTIVE_SCENARIOS,
    SCENARIO_ADAPT_EXPLORATION_BUDGET_EXHAUSTED,
    SCENARIO_ADAPT_DUPLICATE_LEARNING_REPLAY,
    SCENARIO_ADAPT_FUTURE_EVIDENCE_REJECTED,
)
from services.benchmark.governance_security_scenarios import (
    GOVERNANCE_SECURITY_SCENARIOS,
    SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT,
    SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK,
    SCENARIO_REC_FAILURE_RETRY_RECOVERY,
)

__all__ = [
    "BENCHMARK_SCENARIO_VERSION",
    "BENCHMARK_RESULT_VERSION",
    "BENCHMARK_SUMMARY_VERSION",
    "ScenarioCategory",
    "BenchmarkStatus",
    "FailureClass",
    "ExpectationType",
    "BenchmarkExecutionMode",
    "BenchmarkExpectation",
    "InitialProductSpec",
    "InitialMerchantSpec",
    "InitialStateSpec",
    "BuyerContextInput",
    "ExpectedTerminalState",
    "BenchmarkScenario",
    "ObservedStateSnapshot",
    "AssertionDiagnostic",
    "BenchmarkResult",
    "BenchmarkSummary",
    "BenchmarkObserver",
    "AssertionEvaluator",
    "CanonicalBenchmarkRunner",
    "BenchmarkRegistry",
    "BenchmarkReporter",
    "SCENARIO_SMOKE_HAPPY_PATH",
    "SCENARIO_SMOKE_PAYMENT_FAILURE",
    "SCENARIO_SMOKE_NO_OFFER",
    "SCENARIO_SMOKE_REPLAY_IDEMPOTENCY",
    "GOLDEN_SCENARIO_SUITE",
    "SCENARIO_1_PAYMENT_FAILURE_TRUTH",
    "SCENARIO_2_NO_OFFER_SHORT_CIRCUIT",
    "SCENARIO_3_SAFETY_REJECTION_BLOCK",
    "SCENARIO_4_STALE_STATE_REJECTION",
    "SCENARIO_5_DUPLICATE_OUTCOME_ONCE",
    "SCENARIO_6_LUCKY_PURCHASE_GATE",
    "SCENARIO_7_LEARNING_NO_PROMOTION",
    "SCENARIO_8_MERCHANT_BOUNDARY_ATTACK",
    "SCENARIO_9_NEGATIVE_CONTRIBUTION",
    "SCENARIO_10_EXECUTION_FAILURE_SHIELD",
    "ECONOMIC_SCENARIOS",
    "SCENARIO_ECON_ZERO_CONTRIBUTION",
    "SCENARIO_ECON_NEGATIVE_CONTRIBUTION",
    "SCENARIO_ECON_REVENUE_NOT_EQUAL_CONTRIBUTION",
    "SCENARIO_ECON_BUNDLE_MULTI_ITEM_MATH",
    "SCENARIO_ECON_MULTI_UNIT_QUANTITY",
    "SCENARIO_ECON_INVENTORY_BARRIER",
    "SCENARIO_ECON_NO_OFFER_BASELINE",
    "SCENARIO_ECON_EXPECTED_VS_OBSERVED",
    "SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS",
    "SCENARIO_ECON_PROMOTION_GATING",
    "SCENARIO_ECON_CROSS_MERCHANT_ISOLATION",
    "ADAPTIVE_SCENARIOS",
    "SCENARIO_ADAPT_EXPLORATION_BUDGET_EXHAUSTED",
    "SCENARIO_ADAPT_DUPLICATE_LEARNING_REPLAY",
    "SCENARIO_ADAPT_FUTURE_EVIDENCE_REJECTED",
    "GOVERNANCE_SECURITY_SCENARIOS",
    "SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT",
    "SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK",
    "SCENARIO_REC_FAILURE_RETRY_RECOVERY",
]

