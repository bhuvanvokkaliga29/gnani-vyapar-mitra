"""Deterministic Seed Script for Phase 2 Demo Merchant: Atlas Travel Gear.

Creates a coherent, realistic travel and laptop accessory merchant catalog with:
- Strict integer minor unit pricing (paise)
- Unit COGS
- Inventory stock
- Deterministic product affinity relationships
- Merchant objectives and financial constraints
"""

import sys
import asyncio
from decimal import Decimal
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.core.database import init_db, AsyncSessionLocal
from services.commerce_service import CommerceService
from domain.models import Merchant, MerchantActivePolicy, MerchantPolicyVersionRecord
from datetime import datetime, timezone
import uuid
from domain.commerce_schemas import (
    MerchantCreateRequest,
    ProductCreateRequest,
    RelationshipCreateRequest,
    PrioritiesUpdateRequest
)


async def seed_atlas_travel():
    print("=" * 70)
    print("SEEDING PHASE 2 MERCHANT COMMERCE MODEL: ATLAS TRAVEL GEAR")
    print("=" * 70)

    await init_db()
    commerce_svc = CommerceService()

    async with AsyncSessionLocal() as db:
        merchant_id = "merch_atlas_travel"

        # 1. Create or verify merchant
        existing = await commerce_svc.get_merchant(db, merchant_id)
        if not existing:
            print("\n[Step 1] Creating Merchant: Atlas Travel Gear...")
            merchant_req = MerchantCreateRequest(
                id=merchant_id,
                name="Atlas Travel Gear",
                currency="INR",
                business_objective="BALANCE_REVENUE_AND_MARGIN",
                minimum_margin_percent=Decimal("25.00"),
                maximum_discount_percent=Decimal("8.00"),
                target_aov_paise=400000  # ₹4,000
            )
            merchant = await commerce_svc.create_merchant(db, merchant_req)
            print(f"[OK] Merchant created: {merchant.name} (ID: {merchant.id})")
        else:
            print(f"\n[Step 1] Merchant '{merchant_id}' already exists.")

        # 2. Seed Catalog Products
        products_data = [
            ProductCreateRequest(
                id="prod_travel_backpack",
                sku="SKU-BACKPACK-01",
                name="Atlas All-Weather Travel Backpack (35L)",
                description="Waterproof modular backpack with ergonomic harness and dedicated laptop sleeve compartment.",
                category="Bags & Luggage",
                price_paise=299900,  # ₹2,999.00
                cost_paise=180000,   # ₹1,800.00 (COGS)
                currency="INR",
                inventory_quantity=30,
                attributes={"volume_liters": 35, "material": "Cordura 500D", "laptop_compat_inches": 16}
            ),
            ProductCreateRequest(
                id="prod_laptop_sleeve",
                sku="SKU-SLEEVE-02",
                name="Shock-Resistant 16-Inch Laptop Sleeve",
                description="Memory foam padded protective sleeve matching the travel backpack interior.",
                category="Electronics Accessories",
                price_paise=79900,   # ₹799.00
                cost_paise=35000,    # ₹350.00 (COGS)
                currency="INR",
                inventory_quantity=50,
                attributes={"size_inches": 16, "water_resistant": True}
            ),
            ProductCreateRequest(
                id="prod_wireless_mouse",
                sku="SKU-MOUSE-03",
                name="Ergonomic Multi-Device Bluetooth Mouse",
                description="Silent-switch wireless travel mouse with USB-C quick charge.",
                category="Computer Peripherals",
                price_paise=99900,   # ₹999.00
                cost_paise=50000,    # ₹500.00 (COGS)
                currency="INR",
                inventory_quantity=40,
                attributes={"dpi": 4000, "connectivity": ["Bluetooth", "2.4Ghz USB"]}
            ),
            ProductCreateRequest(
                id="prod_usbc_hub",
                sku="SKU-HUB-04",
                name="7-in-1 Aluminum USB-C Travel Hub",
                description="4K HDMI, 100W Power Delivery, SD card reader, and 3 USB 3.0 ports.",
                category="Computer Peripherals",
                price_paise=149900,  # ₹1,499.00
                cost_paise=70000,    # ₹700.00 (COGS)
                currency="INR",
                inventory_quantity=25,
                attributes={"ports": 7, "hdmi": "4K@60Hz", "pd_wattage": 100}
            ),
            ProductCreateRequest(
                id="prod_premium_backpack",
                sku="SKU-BACKPACK-PRO",
                name="Atlas Executive Ballistic Nylon Pack (42L)",
                description="Heavy-duty ballistic nylon pack with TSA checkpoint-friendly fold-out section.",
                category="Bags & Luggage",
                price_paise=499900,  # ₹4,999.00
                cost_paise=280000,   # ₹2,800.00 (COGS)
                currency="INR",
                inventory_quantity=15,
                attributes={"volume_liters": 42, "material": "1680D Ballistic Nylon", "tsa_friendly": True}
            )
        ]

        print("\n[Step 2] Seeding Catalog Products...")
        for p_req in products_data:
            existing_p = await commerce_svc.get_product(db, p_req.id)
            if not existing_p:
                p = await commerce_svc.create_product(db, merchant_id, p_req)
                margin = ((Decimal(p.price_paise - p.cost_paise) / Decimal(p.price_paise)) * Decimal(100)).quantize(Decimal("0.01"))
                print(f"  + [{p.sku}] {p.name}: Price INR {p.price_paise/100:.2f} | COGS INR {p.cost_paise/100:.2f} | Margin {margin}% | Stock {p.inventory_quantity}")
            else:
                print(f"  - Product '{p_req.id}' already exists.")

        # 3. Seed Deterministic Relationships
        relationships_data = [
            RelationshipCreateRequest(
                primary_product_id="prod_travel_backpack",
                related_product_id="prod_laptop_sleeve",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.85"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_travel_backpack",
                related_product_id="prod_premium_backpack",
                relationship_type="SUBSTITUTE",
                affinity_score=Decimal("0.70"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_laptop_sleeve",
                related_product_id="prod_travel_backpack",
                relationship_type="BUNDLE_COMPONENT",
                affinity_score=Decimal("0.90"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_wireless_mouse",
                related_product_id="prod_usbc_hub",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.75"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_travel_backpack",
                related_product_id="prod_premium_backpack",
                relationship_type="UPSELL",
                affinity_score=Decimal("0.65"),
                source="merchant_defined"
            )
        ]

        print("\n[Step 3] Seeding Product Affinity Relationships...")
        for r_req in relationships_data:
            try:
                rel = await commerce_svc.create_product_relationship(db, merchant_id, r_req)
                print(f"  + {rel.primary_product_id} <-> {rel.related_product_id} [{rel.relationship_type}] (Affinity: {rel.affinity_score})")
            except Exception as e:
                print(f"  - Relationship {r_req.primary_product_id} <-> {r_req.related_product_id} already exists or skipped ({e})")

        # 4. Set Priorities
        print("\n[Step 4] Setting Merchant Catalog Priorities...")
        priorities_req = PrioritiesUpdateRequest(
            priority_product_ids=["prod_travel_backpack", "prod_laptop_sleeve"],
            priority_categories=["Bags & Luggage"],
            clearance_product_ids=["prod_wireless_mouse"]
        )
        await commerce_svc.set_merchant_priorities(db, merchant_id, priorities_req)
        print("[OK] Priorities configured: Priority Products = ['prod_travel_backpack', 'prod_laptop_sleeve'], Clearance = ['prod_wireless_mouse']")

        # 5. Verify Unified Context
        print("\n[Step 5] Generating Unified MerchantCommerceContext...")
        context = await commerce_svc.get_merchant_commerce_context(db, merchant_id)
        print(f"[OK] Context successfully generated for '{context.merchant_name}':")
        print(f"  * Total Products: {len(context.products)}")
        print(f"  * Total Relationships: {len(context.relationships)}")
        print(f"  * Objective: {context.business_objective}")
        print(f"  * Min Margin Floor: {context.constraints['minimum_margin_percent']}%")
        print(f"  * Max Discount Ceiling: {context.constraints['maximum_discount_percent']}%")

    print("\n" + "=" * 70)
    print("ATLAS TRAVEL GEAR SEED COMPLETED")
    print("=" * 70)


async def seed_alpha_outfitters():
    print("\n" + "=" * 70)
    print("SEEDING PRESET MERCHANT: ALPHA OUTFITTERS (merch_alpha)")
    print("=" * 70)

    commerce_svc = CommerceService()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        merchant_id = "merch_alpha"

        existing = await commerce_svc.get_merchant(db, merchant_id)
        if not existing:
            merchant_req = MerchantCreateRequest(
                id=merchant_id,
                name="Alpha Outfitters",
                currency="INR",
                business_objective="MAXIMIZE_CONTRIBUTION",
                minimum_margin_percent=Decimal("30.00"),
                maximum_discount_percent=Decimal("5.00"),
                target_aov_paise=500000
            )
            merchant = await commerce_svc.create_merchant(db, merchant_req)
            print(f"[OK] Merchant created: {merchant.name} (ID: {merchant.id})")
        else:
            print(f"[OK] Merchant '{merchant_id}' already exists.")

        products = [
            ProductCreateRequest(
                id="prod_alpha_tent",
                sku="SKU-TENT-01",
                name="Alpha 4-Person Ultralight Backpacking Tent",
                description="Double-wall all-season tent with ripstop nylon rainfly and aluminum poles.",
                category="Outdoor Equipment",
                price_paise=899900,
                cost_paise=520000,
                currency="INR",
                inventory_quantity=20,
                attributes={"capacity": 4, "weight_kg": 2.8}
            ),
            ProductCreateRequest(
                id="prod_alpha_poles",
                sku="SKU-POLES-02",
                name="Carbon Fiber Shock-Absorbing Trekking Poles",
                description="Ultra-lightweight collapsible poles with natural cork grips and carbide tips.",
                category="Hiking Gear",
                price_paise=149900,
                cost_paise=75000,
                currency="INR",
                inventory_quantity=45,
                attributes={"material": "Carbon Fiber", "adjustable": True}
            ),
            ProductCreateRequest(
                id="prod_alpha_sleeping_bag",
                sku="SKU-BAG-03",
                name="Sub-Zero Thermal Down Sleeping Bag",
                description="800-fill power goose down sleeping bag rated for -10C alpine expeditions.",
                category="Outdoor Equipment",
                price_paise=349900,
                cost_paise=190000,
                currency="INR",
                inventory_quantity=30,
                attributes={"temp_rating_c": -10, "insulation": "Goose Down"}
            ),
            ProductCreateRequest(
                id="prod_alpha_dry_bag",
                sku="SKU-DRY-04",
                name="20L Roll-Top Waterproof Dry Bag",
                description="Heavy duty 500D PVC dry sack for kayaking, rafting, and wet-weather hikes.",
                category="Outdoor Accessories",
                price_paise=89900,
                cost_paise=40000,
                currency="INR",
                inventory_quantity=50,
                attributes={"volume_liters": 20, "waterproof_rating": "IPX6"}
            )
        ]

        for p_req in products:
            existing_p = await commerce_svc.get_product(db, p_req.id)
            if not existing_p:
                await commerce_svc.create_product(db, merchant_id, p_req)
                print(f"  + Added product: {p_req.name}")

        relationships = [
            RelationshipCreateRequest(
                primary_product_id="prod_alpha_tent",
                related_product_id="prod_alpha_sleeping_bag",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.85"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_alpha_tent",
                related_product_id="prod_alpha_dry_bag",
                relationship_type="BUNDLE_COMPONENT",
                affinity_score=Decimal("0.75"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_alpha_poles",
                related_product_id="prod_alpha_tent",
                relationship_type="UPSELL",
                affinity_score=Decimal("0.60"),
                source="merchant_defined"
            )
        ]

        for r_req in relationships:
            try:
                await commerce_svc.create_product_relationship(db, merchant_id, r_req)
            except Exception:
                pass

        priorities_req = PrioritiesUpdateRequest(
            priority_product_ids=["prod_alpha_tent", "prod_alpha_sleeping_bag"],
            priority_categories=["Outdoor Equipment"],
            clearance_product_ids=["prod_alpha_dry_bag"]
        )
        await commerce_svc.set_merchant_priorities(db, merchant_id, priorities_req)

        # Ensure active policy exists
        active_p = await db.get(MerchantActivePolicy, merchant_id)
        if not active_p:
            pol_id = "pol_alpha_v0_conservative"
            db.add(MerchantPolicyVersionRecord(
                id=f"pver_alpha_{uuid.uuid4().hex[:8]}",
                merchant_id=merchant_id,
                policy_id=pol_id,
                policy_version="merchant-policy/v1",
                lifecycle_status="ACTIVE",
                strategy_type="SINGLE_PRODUCT",
                product_ids_json=["prod_alpha_tent"],
                rationale="Conservative launch policy for outdoor gear catalog",
                provenance_json={"author": "System Default"},
                created_at=now,
                updated_at=now
            ))
            db.add(MerchantActivePolicy(
                merchant_id=merchant_id,
                policy_id=pol_id,
                policy_version="merchant-policy/v1",
                activated_at=now,
                promotion_id=f"prom_alpha_{uuid.uuid4().hex[:6]}"
            ))
            await db.commit()
            print("[OK] Active policy initialized: pol_alpha_v0_conservative")

    print("[PASS] ALPHA OUTFITTERS SEED COMPLETED")


async def seed_alpha_electronics():
    print("\n" + "=" * 70)
    print("SEEDING PRESET MERCHANT: ALPHA ELECTRONICS (merch_95_alpha)")
    print("=" * 70)

    commerce_svc = CommerceService()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        merchant_id = "merch_95_alpha"

        existing = await commerce_svc.get_merchant(db, merchant_id)
        if not existing:
            merchant_req = MerchantCreateRequest(
                id=merchant_id,
                name="Alpha Electronics",
                currency="INR",
                business_objective="MAXIMIZE_REVENUE",
                minimum_margin_percent=Decimal("18.00"),
                maximum_discount_percent=Decimal("12.00"),
                target_aov_paise=750000
            )
            merchant = await commerce_svc.create_merchant(db, merchant_req)
            print(f"[OK] Merchant created: {merchant.name} (ID: {merchant.id})")
        else:
            print(f"[OK] Merchant '{merchant_id}' already exists.")

        products = [
            ProductCreateRequest(
                id="prod_alpha_anc_headphones",
                sku="SKU-ANC-01",
                name="Alpha Studio Wireless Active Noise Cancelling Headphones",
                description="Premium 40mm beryllium drivers with hybrid ANC and 45-hour battery life.",
                category="Audio",
                price_paise=699900,
                cost_paise=450000,
                currency="INR",
                inventory_quantity=25,
                attributes={"battery_hours": 45, "anc": True, "codec": "LDAC"}
            ),
            ProductCreateRequest(
                id="prod_alpha_tw_earbuds",
                sku="SKU-TWS-02",
                name="True Wireless IPX7 Waterproof Sport Earbuds",
                description="Ergonomic sport earbuds with secure ear hooks and wireless charging case.",
                category="Audio",
                price_paise=299900,
                cost_paise=180000,
                currency="INR",
                inventory_quantity=60,
                attributes={"waterproof": "IPX7", "battery_hours": 32}
            ),
            ProductCreateRequest(
                id="prod_alpha_bt_speaker",
                sku="SKU-SPK-03",
                name="Rugged 360-Degree Portable Bluetooth Speaker",
                description="IP67 floating waterproof bluetooth speaker with deep bass radiators.",
                category="Audio",
                price_paise=399900,
                cost_paise=260000,
                currency="INR",
                inventory_quantity=35,
                attributes={"waterproof": "IP67", "power_watts": 30}
            ),
            ProductCreateRequest(
                id="prod_alpha_wireless_charger",
                sku="SKU-CHG-04",
                name="15W Fast Qi Magnetic Wireless Charging Station",
                description="3-in-1 magnetic charging stand for phone, earbuds, and smartwatch.",
                category="Accessories",
                price_paise=129900,
                cost_paise=70000,
                currency="INR",
                inventory_quantity=40,
                attributes={"wattage": 15, "magnetic": True}
            )
        ]

        for p_req in products:
            existing_p = await commerce_svc.get_product(db, p_req.id)
            if not existing_p:
                await commerce_svc.create_product(db, merchant_id, p_req)
                print(f"  + Added product: {p_req.name}")

        relationships = [
            RelationshipCreateRequest(
                primary_product_id="prod_alpha_anc_headphones",
                related_product_id="prod_alpha_wireless_charger",
                relationship_type="COMPLEMENTARY",
                affinity_score=Decimal("0.80"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_alpha_tw_earbuds",
                related_product_id="prod_alpha_wireless_charger",
                relationship_type="BUNDLE_COMPONENT",
                affinity_score=Decimal("0.70"),
                source="merchant_defined"
            ),
            RelationshipCreateRequest(
                primary_product_id="prod_alpha_tw_earbuds",
                related_product_id="prod_alpha_anc_headphones",
                relationship_type="UPSELL",
                affinity_score=Decimal("0.65"),
                source="merchant_defined"
            )
        ]

        for r_req in relationships:
            try:
                await commerce_svc.create_product_relationship(db, merchant_id, r_req)
            except Exception:
                pass

        priorities_req = PrioritiesUpdateRequest(
            priority_product_ids=["prod_alpha_anc_headphones", "prod_alpha_tw_earbuds"],
            priority_categories=["Audio"],
            clearance_product_ids=["prod_alpha_wireless_charger"]
        )
        await commerce_svc.set_merchant_priorities(db, merchant_id, priorities_req)

        # Ensure active policy exists
        active_p = await db.get(MerchantActivePolicy, merchant_id)
        if not active_p:
            pol_id = "pol_95_alpha_v0_conservative"
            db.add(MerchantPolicyVersionRecord(
                id=f"pver_95alpha_{uuid.uuid4().hex[:8]}",
                merchant_id=merchant_id,
                policy_id=pol_id,
                policy_version="merchant-policy/v1",
                lifecycle_status="ACTIVE",
                strategy_type="SINGLE_PRODUCT",
                product_ids_json=["prod_alpha_anc_headphones"],
                rationale="Conservative baseline policy for consumer electronics",
                provenance_json={"author": "System Default"},
                created_at=now,
                updated_at=now
            ))
            db.add(MerchantActivePolicy(
                merchant_id=merchant_id,
                policy_id=pol_id,
                policy_version="merchant-policy/v1",
                activated_at=now,
                promotion_id=f"prom_95alpha_{uuid.uuid4().hex[:6]}"
            ))
            await db.commit()
            print("[OK] Active policy initialized: pol_95_alpha_v0_conservative")

    print("[PASS] ALPHA ELECTRONICS SEED COMPLETED")


async def seed_all():
    await seed_atlas_travel()
    await seed_alpha_outfitters()
    await seed_alpha_electronics()
    print("\n" + "=" * 70)
    print("ALL PRESET MERCHANTS SEEDED SUCCESSFULLY (PASS)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(seed_all())
