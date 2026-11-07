"""Synthetic Competitor Fixtures for AI Buyer Lab.

These offers represent standardized synthetic competitor alternatives used strictly
for benchmark evaluation.
Core Invariant: All synthetic fixtures are explicitly tagged with `is_synthetic = True`
and are completely separate from live merchant production data.
"""

from typing import List
from services.buyer_lab.schemas import BuyerOffer


def get_synthetic_competitor_offers() -> List[BuyerOffer]:
    """Return a standard suite of synthetic competitor benchmark offers."""
    return [
        # Competitor 1: Apex Luggage (Premium, high warranty, high price)
        BuyerOffer(
            offer_id="off_synth_apex_executive",
            merchant_id="merch_synth_apex",
            merchant_label="Apex Luggage (Synthetic)",
            product_id="prod_synth_apex_exec",
            product_name="Apex Executive Flight Pack",
            category="travel_backpack",
            price_paise=450000,  # ₹4,500
            currency="INR",
            availability=True,
            relevant_attributes={
                "laptop_size": 16.0,
                "capacity_liters": 30.0,
                "material": "cordura_nylon",
                "color": "matte_black",
                "weight_kg": 1.1,
                "water_resistant": True
            },
            included_items=["padded_laptop_sleeve", "luggage_strap"],
            warranty_months=36,  # 3 years
            delivery_days=2,
            service_information="Lifetime zipper guarantee with door-to-door replacement",
            incentives=["free_express_shipping"],
            provenance="synthetic_benchmark_v1",
            is_synthetic=True
        ),

        # Competitor 2: Budget Pack Tech (Cheap, but smaller laptop compartment, no warranty)
        BuyerOffer(
            offer_id="off_synth_budget_basic",
            merchant_id="merch_synth_budget",
            merchant_label="Budget Pack Tech (Synthetic)",
            product_id="prod_synth_budget_pack",
            product_name="Budget Commuter Pack",
            category="travel_backpack",
            price_paise=150000,  # ₹1,500
            currency="INR",
            availability=True,
            relevant_attributes={
                "laptop_size": 14.0,  # Fails 15.6" or 16" laptop requirements!
                "capacity_liters": 20.0,
                "material": "polyester",
                "color": "gray",
                "weight_kg": 0.8,
                "water_resistant": False
            },
            included_items=[],
            warranty_months=6,
            delivery_days=5,
            service_information=None,
            incentives=[],
            provenance="synthetic_benchmark_v1",
            is_synthetic=True
        ),

        # Competitor 3: Nordic Gear (Balanced, waterproof, fast delivery)
        BuyerOffer(
            offer_id="off_synth_nordic_urban",
            merchant_id="merch_synth_nordic",
            merchant_label="Nordic Gear (Synthetic)",
            product_id="prod_synth_nordic_pack",
            product_name="Nordic Urban Voyager",
            category="travel_backpack",
            price_paise=320000,  # ₹3,200
            currency="INR",
            availability=True,
            relevant_attributes={
                "laptop_size": 15.6,
                "capacity_liters": 28.0,
                "material": "ballistic_nylon",
                "color": "navy_blue",
                "weight_kg": 1.0,
                "water_resistant": True
            },
            included_items=["rain_cover", "cable_organizer"],
            warranty_months=24,
            delivery_days=2,
            service_information="24-hour priority email support",
            incentives=["free_shipping"],
            provenance="synthetic_benchmark_v1",
            is_synthetic=True
        ),

        # Competitor 4: Classic Heritage (Heavily discounted, but genuine leather)
        BuyerOffer(
            offer_id="off_synth_classic_leather",
            merchant_id="merch_synth_classic",
            merchant_label="Classic Leatherworks (Synthetic)",
            product_id="prod_synth_leather_bag",
            product_name="Classic Heritage Leather Pack",
            category="travel_backpack",
            price_paise=280000,  # ₹2,800
            currency="INR",
            availability=True,
            relevant_attributes={
                "laptop_size": 15.6,
                "capacity_liters": 25.0,
                "material": "genuine_leather",  # Fails 'no leather' exclusion!
                "color": "brown",
                "weight_kg": 1.8,
                "water_resistant": False
            },
            included_items=["leather_conditioner"],
            warranty_months=12,
            delivery_days=4,
            service_information=None,
            incentives=["free_shipping"],
            provenance="synthetic_benchmark_v1",
            is_synthetic=True
        )
    ]
