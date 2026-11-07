"""Automated Benchmark Runner for Policy Agent Golden Cases (30+ scenarios)."""

import json
import os
import pytest
from decimal import Decimal
from domain.intent_schemas import BuyerIntent
from services.policy.agent import MerchantPolicyAgent
from services.policy.schemas import CandidateValidationStatus
from tests.fixtures.commerce_fixtures import build_test_commerce_context

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "policy_cases.json")


@pytest.fixture(scope="module")
def policy_cases():
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def agent():
    return MerchantPolicyAgent()


@pytest.fixture(scope="module")
def context():
    return build_test_commerce_context()


def test_policy_golden_suite_comprehensive(policy_cases, agent, context):
    """Run all 32 golden policy cases and verify contract properties."""
    assert len(policy_cases) >= 30, f"Expected at least 30 policy cases, found {len(policy_cases)}"

    total_candidates_generated = 0
    total_valid_candidates = 0
    total_exclusion_checks = 0
    exclusion_violations = 0
    grounded_evidence_candidates = 0

    for case in policy_cases:
        case_id = case["id"]
        intent = BuyerIntent.model_validate(case["intent"])
        expected = case["expected"]

        proposal = agent.generate_policy(intent, context)

        total_candidates_generated += proposal.total_candidates
        total_valid_candidates += proposal.valid_candidates_count

        # 1. Status verification
        if "expected_status" in expected:
            assert proposal.status.value == expected["expected_status"], (
                f"Case {case_id}: Expected status {expected['expected_status']}, got {proposal.status.value}"
            )

        # 2. Strategy type verification
        if "expected_strategy_type" in expected and proposal.selected_candidate:
            assert proposal.selected_candidate.strategy_type.value == expected["expected_strategy_type"], (
                f"Case {case_id}: Expected strategy {expected['expected_strategy_type']}, got {proposal.selected_candidate.strategy_type.value}"
            )

        # 3. Forbidden products check (Exclusion & Stock)
        if "forbidden_products" in expected:
            forbidden_set = set(expected["forbidden_products"])
            for cand in proposal.candidates:
                if cand.validation_status == CandidateValidationStatus.APPROVED:
                    total_exclusion_checks += 1
                    intersect = set(cand.product_ids).intersection(forbidden_set)
                    if intersect:
                        exclusion_violations += 1
                    assert not intersect, (
                        f"Case {case_id}: Candidate {cand.candidate_id} contains forbidden product(s): {intersect}"
                    )

        # 4. Budget cap check
        if "max_budget_paise" in expected and proposal.selected_candidate:
            econ = proposal.selected_candidate.deterministic_economics
            if econ:
                assert econ.net_revenue_paise <= expected["max_budget_paise"], (
                    f"Case {case_id}: Net revenue {econ.net_revenue_paise} exceeds budget {expected['max_budget_paise']}"
                )

        # 5. Margin floor check
        if "min_margin_percent" in expected:
            floor = Decimal(expected["min_margin_percent"])
            for cand in proposal.candidates:
                if cand.validation_status == CandidateValidationStatus.APPROVED and cand.deterministic_economics:
                    assert cand.deterministic_economics.gross_margin_percent >= floor, (
                        f"Case {case_id}: Candidate margin {cand.deterministic_economics.gross_margin_percent}% violates floor {floor}%"
                    )

        # 6. Discount ceiling check
        if "max_discount_percent" in expected:
            ceiling = Decimal(expected["max_discount_percent"])
            for cand in proposal.candidates:
                if cand.validation_status == CandidateValidationStatus.APPROVED and cand.deterministic_economics:
                    assert cand.deterministic_economics.effective_discount_percent <= ceiling, (
                        f"Case {case_id}: Discount {cand.deterministic_economics.effective_discount_percent}% exceeds ceiling {ceiling}%"
                    )

        # 7. Candidate bounding check
        if "min_candidates" in expected and "max_candidates" in expected:
            assert expected["min_candidates"] <= proposal.total_candidates <= expected["max_candidates"], (
                f"Case {case_id}: Total candidates {proposal.total_candidates} outside bounds [{expected['min_candidates']}, {expected['max_candidates']}]"
            )

        # 8. Evidence check
        for cand in proposal.candidates:
            if cand.evidence:
                grounded_evidence_candidates += 1

    # Quality Metrics Assertions
    valid_rate = total_valid_candidates / max(1, total_candidates_generated)
    assert valid_rate > 0.60, f"Valid candidate rate {valid_rate:.2%} below 60% threshold"
    assert exclusion_violations == 0, f"Found {exclusion_violations} exclusion violations (expected 0)"
