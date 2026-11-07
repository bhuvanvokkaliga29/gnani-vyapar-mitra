"""Assertion Evaluator for Phase 11.1 Canonical Benchmark Harness.

Evaluates declarative expectations against an ObservedStateSnapshot across:
- EXACT_VALUE
- EXACT_STATE
- INVARIANT
- RELATIONAL
- NO_SIDE_EFFECT
- MONOTONICITY
- ISOLATION
- CONSERVATION

Classifies failure reasons into structured FailureClass categories.
"""

from typing import Any, List, Optional
from services.benchmark.schemas import (
    BenchmarkExpectation,
    ExpectationType,
    FailureClass,
    ObservedStateSnapshot,
    AssertionDiagnostic,
)


class AssertionEvaluator:
    """Evaluates benchmark expectations without duplicating production decision logic."""

    @classmethod
    def evaluate_all(
        cls,
        expectations: List[BenchmarkExpectation],
        observed: ObservedStateSnapshot,
    ) -> List[AssertionDiagnostic]:
        """Evaluate a list of expectations against an observed state snapshot."""
        diagnostics = []
        for exp in expectations:
            diag = cls.evaluate(exp, observed)
            diagnostics.append(diag)
        return diagnostics

    @classmethod
    def evaluate(
        cls,
        expectation: BenchmarkExpectation,
        observed: ObservedStateSnapshot,
    ) -> AssertionDiagnostic:
        """Evaluate a single expectation and return structured diagnostic."""
        field_val = cls._resolve_field(expectation.field_path, observed)
        op = (expectation.operator or "eq").lower()
        expected = expectation.expected_value

        passed = False
        msg = ""

        try:
            if op == "eq":
                passed = field_val == expected
                if not passed:
                    msg = f"Expected {expectation.field_path} == {expected!r}, observed {field_val!r}"
            elif op == "ne":
                passed = field_val != expected
                if not passed:
                    msg = f"Expected {expectation.field_path} != {expected!r}, observed {field_val!r}"
            elif op == "gt":
                passed = (field_val is not None) and (field_val > expected)
                if not passed:
                    msg = f"Expected {expectation.field_path} > {expected!r}, observed {field_val!r}"
            elif op == "gte":
                passed = (field_val is not None) and (field_val >= expected)
                if not passed:
                    msg = f"Expected {expectation.field_path} >= {expected!r}, observed {field_val!r}"
            elif op == "lt":
                passed = (field_val is not None) and (field_val < expected)
                if not passed:
                    msg = f"Expected {expectation.field_path} < {expected!r}, observed {field_val!r}"
            elif op == "lte":
                passed = (field_val is not None) and (field_val <= expected)
                if not passed:
                    msg = f"Expected {expectation.field_path} <= {expected!r}, observed {field_val!r}"
            elif op == "in":
                passed = field_val in expected
                if not passed:
                    msg = f"Expected {expectation.field_path} in {expected!r}, observed {field_val!r}"
            elif op == "is_none":
                passed = field_val is None
                if not passed:
                    msg = f"Expected {expectation.field_path} to be None, observed {field_val!r}"
            elif op == "is_not_none":
                passed = field_val is not None
                if not passed:
                    msg = f"Expected {expectation.field_path} to not be None, observed None"
            else:
                passed = False
                msg = f"Unsupported operator '{op}'"
        except Exception as ex:
            passed = False
            msg = f"Evaluation exception for operator '{op}': {str(ex)}"

        if passed:
            msg = f"Assertion passed: {expectation.description}"

        return AssertionDiagnostic(
            expectation_id=expectation.expectation_id,
            expectation_type=expectation.expectation_type,
            passed=passed,
            failure_class=None if passed else expectation.failure_class,
            target_domain=expectation.target_domain,
            field_path=expectation.field_path,
            expected=expected,
            observed=field_val,
            message=msg,
        )

    @classmethod
    def _resolve_field(cls, path: Optional[str], observed: ObservedStateSnapshot) -> Any:
        """Resolve a dot-separated field path on the ObservedStateSnapshot."""
        if not path:
            return None
        parts = path.split(".")
        val: Any = observed
        for part in parts:
            if hasattr(val, part):
                val = getattr(val, part)
            elif isinstance(val, dict) and part in val:
                val = val[part]
            else:
                return None
        return val
