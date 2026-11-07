"""Statistical validation and boundary audit suite for Phase 8.4 Contextual LinUCB (Pure Python)."""

import ast
import os
import pytest
from services.learning.algorithm import ContextualLinearUCB
from services.learning.features import FEATURE_DIMENSION


def test_dataset_a_higher_reward_produces_higher_expectation():
    """Dataset A:
    Context X + Policy A -> +10000 paise
    Context X + Policy A -> +10000 paise
    Context X + Policy B -> 0 paise
    Context X + Policy B -> 0 paise

    The model should estimate a higher expected contribution for Policy A.
    """
    model = ContextualLinearUCB("merch_stat_1")

    # Policy A features
    x_a = [0.0] * FEATURE_DIMENSION
    x_a[0] = 1.0  # bias
    x_a[1] = 0.5  # context tier
    x_a[6] = 1.0  # single product
    x_a[12] = 0.1 # discount 10%

    # Policy B features
    x_b = [0.0] * FEATURE_DIMENSION
    x_b[0] = 1.0  # bias
    x_b[1] = 0.5  # context tier
    x_b[7] = 1.0  # complementary bundle
    x_b[12] = 0.0 # discount 0%

    # Train on 2 observations of A with +10000 paise, and 2 of B with 0 paise
    model.update(x_a, 10000)
    model.update(x_a, 10000)
    model.update(x_b, 0)
    model.update(x_b, 0)

    pred_a, _, _ = model.predict(x_a)
    pred_b, _, _ = model.predict(x_b)

    assert pred_a > pred_b
    assert pred_a > 0
    assert pred_b <= pred_a


def test_dataset_b_signed_symmetric_rewards():
    """Dataset B:
    Context X + Policy A -> +10000 paise
    Context X + Policy A -> -10000 paise
    Context X + Policy A -> 0 paise

    The model must preserve signed information; expected contribution should hover near zero.
    """
    model = ContextualLinearUCB("merch_stat_2")
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0
    x[1] = 0.5

    model.update(x, 10000)
    model.update(x, -10000)
    model.update(x, 0)

    pred, unc, ucb = model.predict(x)
    assert pred == 0  # Exact balance!
    assert unc > 0


def test_dataset_c_deterministic_replay_produces_identical_state():
    """Dataset C: Identical sequence replayed twice must produce bitwise identical states."""
    m1 = ContextualLinearUCB("m_rep")
    m2 = ContextualLinearUCB("m_rep")

    # Deterministic pseudo-features
    X = []
    for i in range(15):
        row = [1.0] + [((i * 11 + j * 17) % 100) / 100.0 for j in range(1, FEATURE_DIMENSION)]
        X.append(row)
    R = [5000, 12000, -3000, 0, 8000, -5000, 20000, 0, 1000, -2000, 15000, 0, 7000, 9000, -1000]

    for x, r in zip(X, R):
        m1.update(x, r)

    for x, r in zip(X, R):
        m2.update(x, r)

    for i in range(FEATURE_DIMENSION):
        assert abs(m1.b[i] - m2.b[i]) < 1e-9
        assert abs(m1.theta[i] - m2.theta[i]) < 1e-9
        for j in range(FEATURE_DIMENSION):
            assert abs(m1.A[i][j] - m2.A[i][j]) < 1e-9


def test_dataset_d_merchant_isolation_independence():
    """Dataset D: Independent merchants produce completely independent states."""
    m_a = ContextualLinearUCB("merch_alpha")
    m_b = ContextualLinearUCB("merch_beta")

    x = [1.0] * FEATURE_DIMENSION
    m_a.update(x, 50000)

    pred_a, _, _ = m_a.predict(x)
    pred_b, _, _ = m_b.predict(x)

    assert pred_a > 0
    assert pred_b == 0


def test_static_ast_boundary_audit():
    """Verify that services/learning/ contains ZERO autonomous execution or mutation logic."""
    target_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "learning")
    
    forbidden_tokens = [
        "execute_order",
        "create_order",
        "capture_payment",
        "mutate_policy",
        "promote_policy",
        "deploy_policy",
        "exploration_budget",
        "n8n"
    ]

    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as source_file:
                    content = source_file.read()
                    parsed = ast.parse(content, filename=f)
                    for node in ast.walk(parsed):
                        if isinstance(node, ast.Name):
                            for tok in forbidden_tokens:
                                assert tok not in node.id.lower(), f"Forbidden token '{tok}' found in {f} (identifier: {node.id})"
                        elif isinstance(node, ast.FunctionDef):
                            for tok in forbidden_tokens:
                                assert tok not in node.name.lower(), f"Forbidden token '{tok}' found in {f} (function: {node.name})"
