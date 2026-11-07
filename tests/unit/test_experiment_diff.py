"""Unit tests for PolicyDiffEngine in Phase 7."""

import pytest
from services.experiments.diff import PolicyDiffEngine


def test_diff_single_product_vs_value_bundle():
    """PolicyDiffEngine detects bundle expansion, accessory additions, and price deltas."""
    ctrl_snapshot = {
        "selected_candidate": {
            "strategy_type": "SINGLE_PRODUCT",
            "price_paise": 299900,
            "included_items": [],
            "warranty_months": 12,
            "economics": {
                "proposed_price_paise": 299900,
                "cogs_paise": 150000,
                "margin_percent": 49.98
            }
        }
    }

    treat_snapshot = {
        "selected_candidate": {
            "strategy_type": "VALUE_BUNDLE",
            "price_paise": 349900,
            "included_items": ["rain_cover", "laptop_sleeve"],
            "warranty_months": 24,
            "incentives": ["free_shipping"],
            "economics": {
                "proposed_price_paise": 349900,
                "cogs_paise": 170000,
                "margin_percent": 51.41
            }
        }
    }

    diff = PolicyDiffEngine.compute_diff(ctrl_snapshot, treat_snapshot)

    assert diff.control_strategy == "SINGLE_PRODUCT"
    assert diff.treatment_strategy == "VALUE_BUNDLE"
    assert diff.price_delta_paise == 50000  # +₹500.00
    assert diff.added_items == ["rain_cover", "laptop_sleeve"]
    assert diff.warranty_delta_months == 12
    assert diff.margin_delta_percent == 1.43
    assert "Strategy: SINGLE_PRODUCT -> VALUE_BUNDLE" in diff.summary
    assert "+₹500.00" in diff.summary
    assert "free_shipping" in diff.summary


def test_diff_identical_proposals():
    """PolicyDiffEngine reports no material difference when candidates are identical."""
    snapshot = {
        "selected_candidate": {
            "strategy_type": "SINGLE_PRODUCT",
            "price_paise": 299900,
            "included_items": [],
            "warranty_months": 12,
            "economics": {
                "proposed_price_paise": 299900,
                "margin_percent": 49.98
            }
        }
    }

    diff = PolicyDiffEngine.compute_diff(snapshot, snapshot)
    assert diff.price_delta_paise == 0
    assert diff.margin_delta_percent == 0.0
    assert diff.added_items == []
    assert diff.summary == "No material policy difference"
