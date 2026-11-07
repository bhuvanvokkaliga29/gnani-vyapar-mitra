"""Reproducibility tests for Phase 3 Buyer Intent Engine.

Runs each golden case 5 consecutive times and asserts 100% semantic
identity and deterministic output, proving the engine produces stable
results on identical input.
"""

import json
import os
import pytest
from services.intent.extractor import IntentExtractor


FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "intent_cases.json")


@pytest.fixture(scope="module")
def golden_cases():
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def extractor():
    return IntentExtractor()


REPETITIONS = 5


class TestReproducibility:
    """Verify deterministic output: same input → byte-identical output across N runs."""

    def test_all_golden_cases_reproduce_5x(self, golden_cases, extractor):
        """Run each golden case 5 times and assert identical model_dump output."""
        failures = []

        for case in golden_cases:
            case_id = case["id"]
            # Multi-turn cases have 'turns', single-turn have 'input'
            if "input" in case:
                message = case["input"]
            elif "turns" in case:
                # For multi-turn, test reproducibility on the first turn only
                message = case["turns"][0]["input"] if isinstance(case["turns"][0], dict) else case["turns"][0]
            else:
                continue

            results = []
            for run in range(REPETITIONS):
                intent = extractor.parse_utterance(message)
                results.append(intent.model_dump())

            # Compare each subsequent run to the first
            baseline = results[0]
            for run_idx in range(1, REPETITIONS):
                if results[run_idx] != baseline:
                    failures.append(
                        f"Case {case_id}: Run {run_idx + 1} differed from Run 1.\n"
                        f"  Baseline: {baseline}\n"
                        f"  Run {run_idx + 1}: {results[run_idx]}"
                    )

        assert len(failures) == 0, (
            f"{len(failures)} reproducibility failure(s):\n" + "\n".join(failures)
        )

    def test_schema_version_stable(self, golden_cases, extractor):
        """Verify schema_version is always 'buyer-intent/v1' across all runs."""
        for case in golden_cases:
            if "input" in case:
                msg = case["input"]
            elif "turns" in case:
                msg = case["turns"][0]["input"] if isinstance(case["turns"][0], dict) else case["turns"][0]
            else:
                continue
            for _ in range(REPETITIONS):
                intent = extractor.parse_utterance(msg)
                assert intent.schema_version == "buyer-intent/v1", (
                    f"Case {case['id']}: schema_version was {intent.schema_version}"
                )

    def test_prompt_version_stable(self, golden_cases, extractor):
        """Verify prompt_version is always 'intent-extractor/v1' across all runs."""
        for case in golden_cases:
            if "input" in case:
                msg = case["input"]
            elif "turns" in case:
                msg = case["turns"][0]["input"] if isinstance(case["turns"][0], dict) else case["turns"][0]
            else:
                continue
            for _ in range(REPETITIONS):
                intent = extractor.parse_utterance(msg)
                assert intent.prompt_version == "intent-extractor/v1", (
                    f"Case {case['id']}: prompt_version was {intent.prompt_version}"
                )
