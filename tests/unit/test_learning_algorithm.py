"""Unit tests for Phase 8.4 Contextual Linear UCB Algorithm (Pure Python)."""

import math
import pytest
from services.learning.algorithm import (
    ContextualLinearUCB,
    ALGORITHM_VERSION,
    DEFAULT_LAMBDA,
    DEFAULT_ALPHA_PAISE,
    REWARD_SCALE_FACTOR
)
from services.learning.features import FEATURE_DIMENSION, FEATURE_SCHEMA_VERSION
from services.learning.model_errors import (
    CorruptedModelStateError,
    IncompatibleFeatureSchemaError
)


def test_cold_start_initialization():
    """Test cold-start state: A = λI, b = 0, θ = 0."""
    model = ContextualLinearUCB(merchant_id="merch_test_1", dimension=FEATURE_DIMENSION, lambda_reg=1.0)
    assert model.merchant_id == "merch_test_1"
    assert model.dimension == FEATURE_DIMENSION
    assert model.observation_count == 0
    
    for i in range(FEATURE_DIMENSION):
        assert model.b[i] == 0.0
        assert model.theta[i] == 0.0
        for j in range(FEATURE_DIMENSION):
            expected = 1.0 if i == j else 0.0
            assert model.A[i][j] == expected

    # Prediction at cold start
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0  # bias
    pred_paise, uncertainty, ucb_paise = model.predict(x)
    assert pred_paise == 0
    assert uncertainty > 0.0
    # UCB at cold start is purely the exploration bonus
    assert ucb_paise == int(round(model.alpha_paise * uncertainty))


def test_single_update_positive_reward():
    """Test updating model with a single positive observation."""
    model = ContextualLinearUCB(merchant_id="merch_test_1", dimension=FEATURE_DIMENSION)
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0  # bias
    x[1] = 0.5  # budget tier

    reward_paise = 10000  # ₹100
    model.update(x, reward_paise)

    assert model.observation_count == 1
    # Check A matrix rank-1 update: A[0][0] = 1 + 1*1 = 2.0
    assert model.A[0][0] == 2.0
    assert model.A[0][1] == 0.5
    assert model.A[1][1] == 1.0 + 0.25

    # Check b vector
    r_model = reward_paise / REWARD_SCALE_FACTOR  # 100.0
    assert model.b[0] == 100.0
    assert model.b[1] == 50.0

    # Prediction along x should now be strictly positive
    pred_paise, unc, ucb = model.predict(x)
    assert pred_paise > 0
    assert ucb > pred_paise


def test_signed_negative_reward_preserved():
    """Test that negative contribution is preserved and NOT clamped to zero."""
    model = ContextualLinearUCB(merchant_id="merch_test_1", dimension=FEATURE_DIMENSION)
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0

    neg_reward_paise = -20000  # -₹200
    model.update(x, neg_reward_paise)

    assert model.observation_count == 1
    pred_paise, unc, ucb = model.predict(x)
    assert pred_paise < 0  # Strictly negative!


def test_zero_reward_update_is_valid():
    """Test that zero contribution is a valid informative reward."""
    model = ContextualLinearUCB(merchant_id="merch_test_1", dimension=FEATURE_DIMENSION)
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0

    model.update(x, 0)
    assert model.observation_count == 1
    # A is updated with xx^T even though reward was 0
    assert model.A[0][0] == 2.0  # 1.0 + 1.0
    # b remains 0
    assert all(val == 0.0 for val in model.b)


def test_batch_update_equals_incremental_updates():
    """Deterministic Replay Invariant: Batch update must equal identical sequential updates."""
    m_seq = ContextualLinearUCB("m1")
    m_batch = ContextualLinearUCB("m1")

    # Deterministic pseudo-features
    X = []
    for i in range(10):
        row = [1.0] + [((i * 7 + j * 13) % 100) / 100.0 for j in range(1, FEATURE_DIMENSION)]
        X.append(row)
    rewards = [10000, -5000, 0, 25000, 15000, -10000, 5000, 0, 8000, 12000]

    for x, r in zip(X, rewards):
        m_seq.update(x, r)

    m_batch.batch_update(X, rewards)

    for i in range(FEATURE_DIMENSION):
        assert abs(m_seq.b[i] - m_batch.b[i]) < 1e-9
        assert abs(m_seq.theta[i] - m_batch.theta[i]) < 1e-9
        for j in range(FEATURE_DIMENSION):
            assert abs(m_seq.A[i][j] - m_batch.A[i][j]) < 1e-9

    assert m_seq.observation_count == m_batch.observation_count == 10


def test_uncertainty_decreases_with_more_observations():
    """Information Gain: Predicting on x after observing x should decrease uncertainty."""
    model = ContextualLinearUCB("m1")
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0
    x[6] = 1.0  # single product

    _, unc_initial, _ = model.predict(x)

    for _ in range(5):
        model.update(x, 15000)

    _, unc_after, _ = model.predict(x)
    assert unc_after < unc_initial


def test_rejection_of_nan_and_inf_features():
    """Model must reject NaN or infinite feature vectors."""
    model = ContextualLinearUCB("m1")
    x_nan = [0.0] * FEATURE_DIMENSION
    x_nan[3] = float("nan")

    with pytest.raises(IncompatibleFeatureSchemaError):
        model.update(x_nan, 10000)

    with pytest.raises(IncompatibleFeatureSchemaError):
        model.predict(x_nan)


def test_rejection_of_dimension_mismatch():
    """Model must reject wrong dimensions."""
    model = ContextualLinearUCB("m1")
    x_wrong = [0.0] * 10

    with pytest.raises(IncompatibleFeatureSchemaError):
        model.update(x_wrong, 10000)


def test_serialization_round_trip():
    """Serialization to dict and deserialization from dict preserves exact state."""
    model = ContextualLinearUCB("m_serialize", lambda_reg=2.5, alpha_paise=15000)
    x = [1.0 / math.sqrt(FEATURE_DIMENSION)] * FEATURE_DIMENSION
    model.update(x, 50000)

    d = model.to_dict()
    restored = ContextualLinearUCB.from_dict(d)

    assert restored.merchant_id == model.merchant_id
    assert restored.lambda_reg == model.lambda_reg
    assert restored.alpha_paise == model.alpha_paise
    assert restored.observation_count == model.observation_count

    for i in range(FEATURE_DIMENSION):
        assert abs(restored.b[i] - model.b[i]) < 1e-9
        assert abs(restored.theta[i] - model.theta[i]) < 1e-9
        for j in range(FEATURE_DIMENSION):
            assert abs(restored.A[i][j] - model.A[i][j]) < 1e-9
