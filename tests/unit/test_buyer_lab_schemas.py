"""Unit tests for Phase 6 AI Buyer Lab schemas and contracts."""

import pytest
from pydantic import ValidationError
from services.buyer_lab.schemas import (
    BuyerOffer,
    BuyerSelectionResult,
    OfferRejectionCode,
    SelectionTaxonomy,
    BuyerPersonaType
)


def test_buyer_offer_valid_instantiation():
    """BuyerOffer accepts valid buyer-visible attributes."""
    offer = BuyerOffer(
        offer_id="off_test_01",
        merchant_id="merch_atlas",
        merchant_label="Atlas Gear",
        product_id="prod_backpack",
        product_name="Atlas Pack",
        price_paise=299900,
        currency="INR",
        availability=True,
        relevant_attributes={"laptop_size": 15.6, "water_resistant": True},
        included_items=["sleeve"],
        warranty_months=12,
        delivery_days=3,
        incentives=["free_shipping"]
    )
    assert offer.offer_id == "off_test_01"
    assert offer.price_paise == 299900
    assert offer.currency == "INR"


def test_buyer_offer_forbids_internal_merchant_financials():
    """Security Invariant: BuyerOffer strictly forbids internal merchant economics (COGS, margins, objective)."""
    # Attempting to leak cogs_paise
    with pytest.raises(ValidationError):
        BuyerOffer(
            offer_id="off_test_cogs",
            merchant_id="merch_atlas",
            merchant_label="Atlas",
            product_id="prod_01",
            product_name="Pack",
            price_paise=299900,
            cogs_paise=120000  # FORBIDDEN!
        )

    # Attempting to leak margin_percent
    with pytest.raises(ValidationError):
        BuyerOffer(
            offer_id="off_test_margin",
            merchant_id="merch_atlas",
            merchant_label="Atlas",
            product_id="prod_01",
            product_name="Pack",
            price_paise=299900,
            margin_percent=0.45  # FORBIDDEN!
        )

    # Attempting to leak merchant_objective
    with pytest.raises(ValidationError):
        BuyerOffer(
            offer_id="off_test_obj",
            merchant_id="merch_atlas",
            merchant_label="Atlas",
            product_id="prod_01",
            product_name="Pack",
            price_paise=299900,
            merchant_objective="MAXIMIZE_MARGIN"  # FORBIDDEN!
        )


def test_buyer_selection_result_invariants():
    """BuyerSelectionResult validates member consistency between selected_offer_id and eligible_offer_ids."""
    # Selected offer must be in eligible_offer_ids
    with pytest.raises(ValidationError):
        BuyerSelectionResult(
            result_version="buyer-selection/v1",
            selected_offer_id="off_winner",
            eligible_offer_ids=["off_other"],  # Mismatch!
            selection_rationale="Test"
        )

    # NO_ELIGIBLE_OFFER automatically present when selected_offer_id is None
    result = BuyerSelectionResult(
        result_version="buyer-selection/v1",
        selected_offer_id=None,
        eligible_offer_ids=[],
        selection_rationale="No offers"
    )
    assert SelectionTaxonomy.NO_ELIGIBLE_OFFER in result.selection_reasons
