import sqlite3
import json
from decimal import Decimal

def update_clothing():
    conn = sqlite3.connect('test.db')
    cur = conn.cursor()

    # 1. Update Merchant Name & Category
    cur.execute("""
        UPDATE merchants 
        SET name = 'Vastram', business_objective = 'BALANCE_REVENUE_AND_MARGIN' 
        WHERE id = 'merch_atlas_travel'
    """)

    # 2. Remove old backpack products for merch_atlas_travel
    cur.execute("DELETE FROM product_relationships WHERE merchant_id = 'merch_atlas_travel'")
    cur.execute("DELETE FROM merchant_priorities WHERE merchant_id = 'merch_atlas_travel'")
    cur.execute("DELETE FROM products WHERE merchant_id = 'merch_atlas_travel'")

    # 3. New Clothing Catalog (Shirts & Trousers)
    clothing_products = [
        # Shirts
        (
            "prod_vastram_shirt_white",
            "merch_atlas_travel",
            "VAST-SH-01",
            "Vastram Classic White Oxford Cotton Shirt",
            "100% Egyptian Giza cotton formal shirt with spread collar and mother-of-pearl buttons. Tailored slim fit.",
            "SHIRTS",
            189900,  # ₹1,899.00
            65000,   # ₹650.00
            "INR",
            85,
            json.dumps({
                "fabric": "Oxford Cotton",
                "fit": "Slim Fit",
                "color": "White",
                "refined_photo_url": "/clothing/white_oxford.jpg"
            }),
            1
        ),
        (
            "prod_vastram_shirt_navy",
            "merch_atlas_travel",
            "VAST-SH-02",
            "Vastram Signature Royal Navy Casual Shirt",
            "Pre-washed rich indigo dyed pure cotton casual shirt. Soft-brushed finish for all-day comfort.",
            "SHIRTS",
            199900,  # ₹1,999.00
            72000,   # ₹720.00
            "INR",
            60,
            json.dumps({
                "fabric": "Brushed Cotton",
                "fit": "Regular Fit",
                "color": "Navy Blue",
                "refined_photo_url": "/clothing/navy_shirt.jpg"
            }),
            1
        ),
        (
            "prod_vastram_shirt_linen",
            "merch_atlas_travel",
            "VAST-SH-03",
            "Vastram Pure Olive Linen Casual Shirt",
            "Breathable French flax pure linen casual shirt in earthy sage green. Relaxed weekend spread collar.",
            "SHIRTS",
            249900,  # ₹2,499.00
            92000,   # ₹920.00
            "INR",
            45,
            json.dumps({
                "fabric": "French Linen",
                "fit": "Relaxed Fit",
                "color": "Sage Olive",
                "refined_photo_url": "/clothing/linen_shirt.jpg"
            }),
            1
        ),
        # Trousers
        (
            "prod_vastram_trouser_khaki",
            "merch_atlas_travel",
            "VAST-TR-01",
            "Vastram Tailored Khaki Chino Trousers",
            "98% premium stretch twill cotton chinos. Clean flat front with tailored taper and reinforced pocketing.",
            "TROUSERS",
            229900,  # ₹2,299.00
            85000,   # ₹850.00
            "INR",
            70,
            json.dumps({
                "fabric": "Stretch Twill Cotton",
                "fit": "Tailored Fit",
                "color": "Beige Khaki",
                "refined_photo_url": "/clothing/khaki_chino.jpg"
            }),
            1
        ),
        (
            "prod_vastram_trouser_grey",
            "merch_atlas_travel",
            "VAST-TR-02",
            "Vastram Italian Wool Charcoal Grey Trousers",
            "Fine tropical wool blend formal trousers with sharp creases and internal shirt-gripper waistband.",
            "TROUSERS",
            279900,  # ₹2,799.00
            110000,  # ₹1,100.00
            "INR",
            40,
            json.dumps({
                "fabric": "Tropical Wool Blend",
                "fit": "Slim Formal",
                "color": "Charcoal Grey",
                "refined_photo_url": "/clothing/grey_trouser.jpg"
            }),
            1
        ),
        (
            "prod_vastram_trouser_black",
            "merch_atlas_travel",
            "VAST-TR-03",
            "Vastram Classic Jet Black Formal Trousers",
            "Deep fade-resistant black formal trousers. Non-crease poly-viscose blend with flexible comfort waistband.",
            "TROUSERS",
            219900,  # ₹2,199.00
            79000,   # ₹790.00
            "INR",
            6,       # Low stock for alert demonstration!
            json.dumps({
                "fabric": "Poly-Viscose",
                "fit": "Regular Fit",
                "color": "Jet Black",
                "refined_photo_url": "/clothing/black_trouser.jpg"
            }),
            1
        )
    ]

    cur.executemany("""
        INSERT INTO products (
            id, merchant_id, sku, name, description, category,
            price_paise, cost_paise, currency, inventory_quantity, reserved_quantity,
            attributes, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
    """, clothing_products)

    # 4. Priority Product
    cur.execute("""
        INSERT INTO merchant_priorities (merchant_id, priority_product_ids, priority_categories, clearance_product_ids)
        VALUES ('merch_atlas_travel', '["prod_vastram_shirt_white"]', '["SHIRTS", "TROUSERS"]', '[]')
    """)

    # 5. Product Relationships (Complementary pairings: Shirts + Trousers)
    relationships = [
        ("merch_atlas_travel", "prod_vastram_shirt_white", "prod_vastram_trouser_khaki", "COMPLEMENTARY", 0.90, "merchant_defined", 1.0),
        ("merch_atlas_travel", "prod_vastram_shirt_white", "prod_vastram_trouser_grey", "COMPLEMENTARY", 0.85, "merchant_defined", 1.0),
        ("merch_atlas_travel", "prod_vastram_shirt_navy", "prod_vastram_trouser_khaki", "COMPLEMENTARY", 0.92, "merchant_defined", 1.0),
        ("merch_atlas_travel", "prod_vastram_shirt_linen", "prod_vastram_trouser_khaki", "COMPLEMENTARY", 0.88, "merchant_defined", 1.0),
        ("merch_atlas_travel", "prod_vastram_trouser_grey", "prod_vastram_trouser_black", "SUBSTITUTE", 0.80, "merchant_defined", 1.0)
    ]
    cur.executemany("""
        INSERT INTO product_relationships (
            merchant_id, primary_product_id, related_product_id, relationship_type, affinity_score, source, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, relationships)

    conn.commit()
    conn.close()
    print("Successfully updated Vastram clothing catalog in test.db!")

if __name__ == '__main__':
    update_clothing()
