"""Unit tests for PreferenceEvaluator and deterministic tie-breaking."""

import pytest
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    AttributePreference,
    PreferenceStrength
)
from services.buyer_lab.schemas import (
    BuyerOffer,
    BuyerPersonaType,
    SelectionTaxonomy
)
from services.buyer_lab.evaluator import PreferenceEvaluator


@pytest.fixture
def evaluator():
    return PreferenceEvaluator()


def test_sole_eligible_offer_selected(evaluator):
    """When only one eligible offer exists, it is selected with clear rationale."""
    offer = BuyerOffer(
        offer_id="off_sole",
        merchant_id="merch_atlas",
        merchant_label="Atlas",
        product_id="prod_1",
        product_name="Atlas Pack",
        price_paise=299900
    )
    intent = BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR"))
    winner, reasons, rationale, satisfied, unmet = evaluator.evaluate_and_rank(intent, [offer])

    assert winner.offer_id == "off_sole"
    assert SelectionTaxonomy.HARD_REQUIREMENT_MATCH in reasons
    assert SelectionTaxonomy.BUDGET_MATCH in reasons


def test_preference_satisfaction_beats_lower_satisfaction(evaluator):
    """Offer satisfying explicit warranty preference beats offer with standard warranty."""
    off_standard = BuyerOffer(
        offer_id="off_std",
        merchant_id="merch_1",
        merchant_label="M1",
        product_id="p1",
        product_name="Standard Pack",
        price_paise=300000,
        warranty_months=12
    )
    off_premium = BuyerOffer(
        offer_id="off_prem",
        merchant_id="merch_2",
        merchant_label="M2",
        product_id="p2",
        product_name="Premium Pack",
        price_paise=320000,
        warranty_months=36
    )
    intent = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=400000, currency="INR"),
        preferences=[AttributePreference(attribute="warranty", preference="long warranty", strength=PreferenceStrength.EXPLICIT)]
    )

    winner, reasons, rationale, satisfied, unmet = evaluator.evaluate_and_rank(
        intent, [off_standard, off_premium], persona=BuyerPersonaType.WARRANTY_SERVICE
    )
    assert winner.offer_id == "off_prem"
    assert len(satisfied) == 1
    assert SelectionTaxonomy.WARRANTY_VALUE in reasons


def test_price_sensitive_persona_chooses_lower_price(evaluator):
    """PRICE_SENSITIVE persona prioritizes price efficiency among compliant offers."""
    off_cheap = BuyerOffer(
        offer_id="off_cheap",
        merchant_id="merch_1",
        merchant_label="M1",
        product_id="p1",
        product_name="Pack Cheap",
        price_paise=200000
    )
    off_expensive = BuyerOffer(
        offer_id="off_exp",
        merchant_id="merch_2",
        merchant_label="M2",
        product_id="p2",
        product_name="Pack Exp",
        price_paise=300000
    )
    intent = BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR"))

    winner, reasons, _, _, _ = evaluator.evaluate_and_rank(
        intent, [off_cheap, off_expensive], persona=BuyerPersonaType.PRICE_SENSITIVE
    )
    assert winner.offer_id == "off_cheap"
    assert SelectionTaxonomy.LOWER_PRICE_AMONG_ELIGIBLE in reasons


def test_deterministic_alphabetical_tie_break(evaluator):
    """When offers are identically equivalent on all dimensions, stable alphabetical ID breaks tie."""
    off_b = BuyerOffer(
        offer_id="off_beta",
        merchant_id="merch_1",
        merchant_label="M1",
        product_id="p1",
        product_name="Pack",
        price_paise=250000
    )
    off_a = BuyerOffer(
        offer_id="off_alpha",
        merchant_id="merch_2",
        merchant_label="M2",
        product_id="p2",
        product_name="Pack",
        price_paise=250000
    )
    intent = BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR"))

    # Whether passed [off_b, off_a] or [off_a, off_b], off_alpha MUST win deterministically
    winner1, _, _, _, _ = evaluator.evaluate_and_rank(intent, [off_b, off_a])
    winner2, _, _, _, _ = evaluator.evaluate_and_rank(intent, [off_a, off_b])

    assert winner1.offer_id == "off_alpha"
    assert winner2.offer_id == "off_alpha"
