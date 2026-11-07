"""Reproducibility & Stability tests for Policy Agent (5 runs per case)."""

import json
import os
import pytest
from domain.intent_schemas import BuyerIntent
from services.policy.agent import MerchantPolicyAgent
from tests.fixtures.commerce_fixtures import build_test_commerce_context

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "policy_cases.json")
REPETITIONS = 5


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


def test_policy_reproducibility_across_5_runs(policy_cases, agent, context):
    """Run each golden policy case 5 times and verify structural and semantic stability."""
    for case in policy_cases:
        case_id = case["id"]
        intent = BuyerIntent.model_validate(case["intent"])

        runs = []
        for _ in range(REPETITIONS):
            proposal = agent.generate_policy(intent, context)
            runs.append(proposal)

        # Baseline is Run 1
        baseline = runs[0]

        for idx, r in enumerate(runs[1:], start=2):
            # 1. Schema version stability
            assert r.policy_version == "merchant-policy/v1"
            assert r.prompt_version == "merchant-policy-agent/v1"

            # 2. Status stability
            assert r.status == baseline.status, (
                f"Case {case_id}: Run {idx} status {r.status} != Run 1 status {baseline.status}"
            )

            # 3. Candidate count stability
            assert r.total_candidates == baseline.total_candidates, (
                f"Case {case_id}: Run {idx} total_candidates {r.total_candidates} != Run 1 {baseline.total_candidates}"
            )

            # 4. Valid candidate count stability
            assert r.valid_candidates_count == baseline.valid_candidates_count, (
                f"Case {case_id}: Run {idx} valid_candidates_count {r.valid_candidates_count} != Run 1 {baseline.valid_candidates_count}"
            )

            # 5. Selected strategy stability
            if baseline.selected_candidate:
                assert r.selected_candidate is not None
                assert r.selected_candidate.strategy_type == baseline.selected_candidate.strategy_type
                assert r.selected_candidate.product_ids == baseline.selected_candidate.product_ids
