import sqlite3
import json

def enrich_products():
    conn = sqlite3.connect('test.db')
    cur = conn.cursor()

    products_data = [
        # 1. White Oxford Shirt
        (
            "prod_vastram_shirt_white",
            "Crafted from 100% extra-long staple Egyptian Giza cotton, the Vastram Classic White Oxford Cotton Shirt is the quintessential garment for executive wardrobes. Woven in an 80s two-ply pinpoint oxford construction, it balances substantial drape with natural breathability. Features a crisp semi-spread collar engineered to hold its structure with or without a tie, removable brass collar stays, and genuine Australian mother-of-pearl buttons. Tailored with a modern slim silhouette, curved split-yoke across the shoulders, and French-placket detailing for frictionless comfort from boardroom to dinner.",
            json.dumps({
                "fabric": "100% Long-Staple Egyptian Giza Cotton",
                "weave": "80s 2-Ply Pinpoint Oxford (145 GSM)",
                "fit": "Tailored Slim Fit (Split-Yoke Back)",
                "collar": "Semi-Spread English Collar (Brass Stays)",
                "cuff": "Rounded Double-Button Barrel Cuff",
                "care": "Machine wash cold with similar whites. Tumble dry low or line dry in shade. Warm steam iron.",
                "sizes": ["38 (S)", "40 (M)", "42 (L)", "44 (XL)", "46 (XXL)"],
                "color": "Pristine Crisp White",
                "origin": "Handcrafted in Coimbatore, Tamil Nadu",
                "refined_photo_url": "/clothing/white_oxford.jpg",
                "marketplaces": [
                    {
                        "name": "Amazon India",
                        "code": "AMAZON",
                        "status": "ACTIVE",
                        "listing_id": "ASIN: B0D8X72V1",
                        "price_paise": 189900,
                        "fee_percent": 15.0,
                        "fulfillment": "FBA Prime",
                        "orders_today": 8,
                        "rating": "4.7 ★ (312 reviews)"
                    },
                    {
                        "name": "Flipkart",
                        "code": "FLIPKART",
                        "status": "ACTIVE",
                        "listing_id": "FSN: SHRFT982XWHT",
                        "price_paise": 189900,
                        "fee_percent": 14.5,
                        "fulfillment": "Flipkart Assured",
                        "orders_today": 5,
                        "rating": "4.6 ★ (188 reviews)"
                    },
                    {
                        "name": "Meesho",
                        "code": "MEESHO",
                        "status": "NOT_LISTED",
                        "listing_id": "Ready for 0% Commission Setup",
                        "price_paise": 179900,
                        "fee_percent": 0.0,
                        "fulfillment": "Self-Ship",
                        "orders_today": 0,
                        "rating": "New"
                    },
                    {
                        "name": "Myntra",
                        "code": "MYNTRA",
                        "status": "ACTIVE",
                        "listing_id": "MYN-VAST-OXF-01",
                        "price_paise": 209900,
                        "fee_percent": 18.0,
                        "fulfillment": "Myntra Omni-Studio",
                        "orders_today": 3,
                        "rating": "4.8 ★"
                    },
                    {
                        "name": "Vastram Direct (WhatsApp)",
                        "code": "WHATSAPP",
                        "status": "ACTIVE (PRIMARY)",
                        "listing_id": "WA-CATALOG-01",
                        "price_paise": 189900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Express (BlueDart / Delhivery)",
                        "orders_today": 12,
                        "rating": "4.9 ★ (Instant UPI)"
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec_sh_01_channel",
                        "type": "CHANNEL_SHIFT",
                        "badge": "CHANNEL MIGRATION",
                        "title": "Remove listing on Amazon and place it on Meesho",
                        "impact": "+₹280 Net Profit / Unit",
                        "description": "Amazon India's 15% referral fee and escalating CPC ad costs are compressing unit margins down to 50.8%. Delisting this SKU from Amazon and placing it on Meesho's 0%-commission portal unlocks Tier-2 and Tier-3 festive wedding bulk orders while expanding net margin by +₹280 per shirt.",
                        "action_label": "Delist from Amazon & Publish to Meesho",
                        "is_channel_action": True
                    },
                    {
                        "id": "rec_sh_01_bundle",
                        "type": "BUNDLE_PAIR",
                        "badge": "COMPLEMENTARY PAIRING",
                        "title": "Bundle up this pair with Tailored Khaki Chino Trousers",
                        "impact": "Unlocks ₹42,000 GMV",
                        "pair_sku": "VAST-TR-01",
                        "pair_name": "Vastram Tailored Khaki Chino Trousers",
                        "pair_image": "/clothing/khaki_chino.jpg",
                        "pair_discount_price": 389900,
                        "description": "Autonomous styling affinity analysis shows a 92% co-purchase correlation between the White Oxford Shirt and Khaki Chinos. Launching a 'Smart Executive Duo' bundle at ₹3,899 (regular ₹4,198) increases Average Order Value (AOV) from ₹1,899 to ₹3,899.",
                        "action_label": "Publish 1-Click Bundle Deal"
                    },
                    {
                        "id": "rec_sh_01_price",
                        "type": "PRICE_OPTIMIZATION",
                        "badge": "PRICING POWER",
                        "title": "Lift List Price by ₹200 to ₹2,099",
                        "impact": "+₹42,000 / mo Net Profit",
                        "description": "Zero stockout competitors detected in premium Giza cotton oxford category. Demand elasticity retention is 97.4%, providing immediate headroom to lift retail price from ₹1,899 to ₹2,099.",
                        "action_label": "Apply Price Adjustment (₹2,099)"
                    }
                ]
            })
        ),
        # 2. Navy Casual Shirt
        (
            "prod_vastram_shirt_navy",
            "Dyed in deep saturated indigo hues and pre-washed for a super-soft, lived-in feel, the Vastram Signature Royal Navy Casual Shirt is engineered for effortless sophistication. Spun from 100% high-grade combed cotton with a light peached finish that feels exceptionally gentle against the skin. Features a relaxed spread collar, contrasting tonal button-down accents, twin-needle durable stitching, and a rounded hem designed to be worn untucked or tucked with chinos or denims.",
            json.dumps({
                "fabric": "100% Combed Indigo Cotton (Peached Finish)",
                "weave": "Twill Weave (160 GSM)",
                "fit": "Regular Casual Fit",
                "collar": "Modern Casual Spread Collar",
                "care": "Gentle cold cycle. Wash inside-out with dark colors. Line dry in shade.",
                "sizes": ["38", "40", "42", "44"],
                "color": "Royal Navy Blue",
                "origin": "Loomed in Tirupur, Tamil Nadu",
                "refined_photo_url": "/clothing/navy_shirt.jpg",
                "marketplaces": [
                    {
                        "name": "Amazon India",
                        "code": "AMAZON",
                        "status": "ACTIVE",
                        "listing_id": "ASIN: B0D9Y81M2",
                        "price_paise": 199900,
                        "fee_percent": 15.0,
                        "fulfillment": "FBA Prime",
                        "orders_today": 4,
                        "rating": "4.6 ★"
                    },
                    {
                        "name": "Flipkart",
                        "code": "FLIPKART",
                        "status": "ACTIVE",
                        "listing_id": "FSN: SHRNVY991",
                        "price_paise": 199900,
                        "fee_percent": 14.5,
                        "fulfillment": "Flipkart Assured",
                        "orders_today": 3,
                        "rating": "4.5 ★"
                    },
                    {
                        "name": "Meesho",
                        "code": "MEESHO",
                        "status": "NOT_LISTED",
                        "listing_id": "Unlisted",
                        "price_paise": 189900,
                        "fee_percent": 0.0,
                        "fulfillment": "Self-Ship",
                        "orders_today": 0
                    },
                    {
                        "name": "Myntra",
                        "code": "MYNTRA",
                        "status": "ACTIVE",
                        "listing_id": "MYN-VAST-NVY-02",
                        "price_paise": 219900,
                        "fee_percent": 18.0,
                        "fulfillment": "Omni Express",
                        "orders_today": 4,
                        "rating": "4.7 ★"
                    },
                    {
                        "name": "Vastram Direct (WhatsApp)",
                        "code": "WHATSAPP",
                        "status": "ACTIVE (PRIMARY)",
                        "listing_id": "WA-CATALOG-02",
                        "price_paise": 199900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Express",
                        "orders_today": 7,
                        "rating": "4.9 ★"
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec_sh_02_bundle",
                        "type": "BUNDLE_PAIR",
                        "badge": "CONTRAST PAIRING",
                        "title": "Bundle up this pair with Italian Wool Charcoal Grey Trousers",
                        "impact": "+₹34,000 Weekly GMV",
                        "pair_sku": "VAST-TR-02",
                        "pair_name": "Vastram Italian Wool Charcoal Grey Trousers",
                        "pair_image": "/clothing/grey_trouser.jpg",
                        "pair_discount_price": 439900,
                        "description": "High visual contrast pairing: Royal Navy casual shirt with Charcoal Grey trousers has an 85% stylist approval rating. Promoted as 'Evening Formal Transition Set' at ₹4,399.",
                        "action_label": "Deploy Smart Bundle"
                    },
                    {
                        "id": "rec_sh_02_channel",
                        "type": "CHANNEL_SHIFT",
                        "badge": "MARGIN PRESERVATION",
                        "title": "Shift 25 Units from Amazon to WhatsApp Direct VIPs",
                        "impact": "+14.5% Margin Boost",
                        "description": "Amazon casual shirt category return rate is 18.4% due to customer sizing confusion, whereas WhatsApp Direct return rate is only 1.2%. Shifting catalog allocation saves ₹18,000 in reverse logistics.",
                        "action_label": "Allocate to WhatsApp Queue",
                        "is_channel_action": True
                    }
                ]
            })
        ),
        # 3. Olive Linen Shirt
        (
            "prod_vastram_shirt_linen",
            "Woven from 100% natural European French flax linen, the Vastram Pure Olive Linen Casual Shirt is an airy masterpiece designed for tropical climates and destination getaways. The garment undergoes enzyme garment-washing to achieve a feather-light slub texture that softens with every wash. Designed with a laid-back camp collar, natural coconut-shell buttons, and a relaxed boxy cut that optimizes air circulation throughout warm humid days.",
            json.dumps({
                "fabric": "100% Pure European Flax Linen",
                "weave": "Open Slub Plain Weave (130 GSM)",
                "fit": "Relaxed Resort Fit",
                "collar": "Convertible Camp Collar",
                "care": "Hand wash or gentle machine wash cold. Hang dry damp to preserve natural linen texture. Steam iron if crisp finish preferred.",
                "sizes": ["38", "40", "42", "44"],
                "color": "Earth Sage Olive",
                "origin": "Woven in Bhagalpur, India",
                "refined_photo_url": "/clothing/linen_shirt.jpg",
                "marketplaces": [
                    {
                        "name": "Amazon India",
                        "code": "AMAZON",
                        "status": "ACTIVE",
                        "listing_id": "ASIN: B0D8Z55LIN",
                        "price_paise": 249900,
                        "fee_percent": 15.0,
                        "fulfillment": "FBA Prime",
                        "orders_today": 3,
                        "rating": "4.8 ★"
                    },
                    {
                        "name": "Flipkart",
                        "code": "FLIPKART",
                        "status": "ACTIVE",
                        "listing_id": "FSN: SHRLIN992",
                        "price_paise": 249900,
                        "fee_percent": 14.5,
                        "fulfillment": "Flipkart Assured",
                        "orders_today": 2,
                        "rating": "4.7 ★"
                    },
                    {
                        "name": "Meesho",
                        "code": "MEESHO",
                        "status": "NOT_LISTED",
                        "listing_id": "Unlisted",
                        "price_paise": 239900,
                        "fee_percent": 0.0,
                        "fulfillment": "Self-Ship",
                        "orders_today": 0
                    },
                    {
                        "name": "Myntra",
                        "code": "MYNTRA",
                        "status": "ACTIVE (FEATURED)",
                        "listing_id": "MYN-VAST-LIN-03",
                        "price_paise": 269900,
                        "fee_percent": 18.0,
                        "fulfillment": "Myntra Omni-Studio",
                        "orders_today": 6,
                        "rating": "4.9 ★"
                    },
                    {
                        "name": "Vastram Direct (WhatsApp)",
                        "code": "WHATSAPP",
                        "status": "ACTIVE (PRIMARY)",
                        "listing_id": "WA-CATALOG-03",
                        "price_paise": 249900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Express",
                        "orders_today": 7,
                        "rating": "4.9 ★"
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec_sh_03_bundle",
                        "type": "BUNDLE_PAIR",
                        "badge": "RESORT DUO",
                        "title": "Bundle up this pair with Tailored Khaki Chino Trousers",
                        "impact": "+₹58,000 GMV Expansion",
                        "pair_sku": "VAST-TR-01",
                        "pair_name": "Vastram Tailored Khaki Chino Trousers",
                        "pair_image": "/clothing/khaki_chino.jpg",
                        "pair_discount_price": 429900,
                        "description": "Earthy olive linen paired with sandy khaki chinos is Vastram's #1 Instagram lookbook combination with an 88% cross-sell affinity score. Package as 'Weekend Linen Escapade Duo' at ₹4,299 (save ₹499).",
                        "action_label": "Activate Resort Bundle"
                    },
                    {
                        "id": "rec_sh_03_channel",
                        "type": "CHANNEL_SHIFT",
                        "badge": "PREMIUM POSITIONING",
                        "title": "Delist from Discount Portals & Launch on Tata CLiQ Luxury",
                        "impact": "+₹350 Net Price Realization",
                        "description": "Pure flax linen commands premium brand perception. Tata CLiQ Luxury fashion edit accepts Vastram pure linen at ₹2,899 retail with zero discount pressure.",
                        "action_label": "Syndicate to Luxury Portal",
                        "is_channel_action": True
                    }
                ]
            })
        ),
        # 4. Khaki Chino Trousers
        (
            "prod_vastram_trouser_khaki",
            "The Vastram Tailored Khaki Chino Trousers bridge the gap between crisp business casual and weekend leisure. Constructed from a durable 98% combed compact cotton twill infused with 2% elastane for dynamic 4-way stretch. Designed with a clean flat front, slanted side coin and hand pockets, button-through welt back pockets, and an engineered curved waistband that prevents gapping. Tailored slim through the thigh with a neat taper at the hem.",
            json.dumps({
                "fabric": "98% Combed Compact Cotton, 2% Spandex Elastane",
                "weave": "Heavy Chino Twill (240 GSM)",
                "fit": "Tailored Slim Tapered",
                "waist": "Mid-Rise with Engineered Anti-Roll Waistband",
                "closure": "YKK Brass Zip Fly with Extended Tab Horn Button",
                "care": "Machine wash inside out in cold water. Tumble dry warm. Iron inside out.",
                "sizes": ["30", "32", "34", "36", "38"],
                "color": "Warm British Khaki",
                "origin": "Tailored in Bengaluru, Karnataka",
                "refined_photo_url": "/clothing/khaki_chino.jpg",
                "marketplaces": [
                    {
                        "name": "Amazon India",
                        "code": "AMAZON",
                        "status": "ACTIVE",
                        "listing_id": "ASIN: B0D7T89KHK",
                        "price_paise": 229900,
                        "fee_percent": 15.0,
                        "fulfillment": "FBA Prime",
                        "orders_today": 6,
                        "rating": "4.7 ★"
                    },
                    {
                        "name": "Flipkart",
                        "code": "FLIPKART",
                        "status": "ACTIVE",
                        "listing_id": "FSN: TRSKHK771",
                        "price_paise": 229900,
                        "fee_percent": 14.5,
                        "fulfillment": "Flipkart Assured",
                        "orders_today": 4,
                        "rating": "4.6 ★"
                    },
                    {
                        "name": "Meesho",
                        "code": "MEESHO",
                        "status": "ACTIVE",
                        "listing_id": "MEE-KHK-01",
                        "price_paise": 209900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Courier",
                        "orders_today": 5,
                        "rating": "4.5 ★"
                    },
                    {
                        "name": "Myntra",
                        "code": "MYNTRA",
                        "status": "ACTIVE",
                        "listing_id": "MYN-VAST-KHK-01",
                        "price_paise": 249900,
                        "fee_percent": 18.0,
                        "fulfillment": "Myntra Omni-Studio",
                        "orders_today": 3,
                        "rating": "4.8 ★"
                    },
                    {
                        "name": "Vastram Direct (WhatsApp)",
                        "code": "WHATSAPP",
                        "status": "ACTIVE (PRIMARY)",
                        "listing_id": "WA-CATALOG-TR01",
                        "price_paise": 229900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Express",
                        "orders_today": 8,
                        "rating": "4.9 ★"
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec_tr_01_bundle",
                        "type": "BUNDLE_PAIR",
                        "badge": "UNIVERSAL ANCHOR",
                        "title": "Bundle up this pair with White Oxford Shirt or Olive Linen Shirt",
                        "impact": "+₹46,000 GMV",
                        "pair_sku": "VAST-SH-01",
                        "pair_name": "Vastram Classic White Oxford Cotton Shirt",
                        "pair_image": "/clothing/white_oxford.jpg",
                        "pair_discount_price": 389900,
                        "description": "Universal wardrobe anchor: Over 74% of trousers orders are purchased alongside an Oxford or Linen shirt. Display dynamic bundle discount at checkout.",
                        "action_label": "Enable Checkout Pairing"
                    },
                    {
                        "id": "rec_tr_01_channel",
                        "type": "CHANNEL_SHIFT",
                        "badge": "AD SPEND OPTIMIZATION",
                        "title": "Pause Amazon Sponsored Listing & Shift Budget to WhatsApp Ads",
                        "impact": "Saves ₹14,000 Ad Waste",
                        "description": "Amazon Sponsored Products ACOS on chinos has reached 31% due to fierce international fast-fashion bidding. Diverting budget to WhatsApp retargeting delivers a 5.2x ROAS.",
                        "action_label": "Pause Amazon Ads & Reallocate",
                        "is_channel_action": True
                    }
                ]
            })
        ),
        # 5. Charcoal Grey Trousers -> RECOMMENDATIONS: NONE!
        (
            "prod_vastram_trouser_grey",
            "Crafted from an all-season tropical wool-blend cloth woven with micro-stretch elasticity, the Vastram Italian Wool Charcoal Grey Trousers deliver unmatched drape and wrinkle resistance. Features a razor-sharp permanent crease, curtain waistband with internal silicone shirt-grippers to keep shirts firmly tucked, taped blind-stitched hems, and a luxurious half-lined viscose interior for frictionless glide over socks and dress shoes.",
            json.dumps({
                "fabric": "60% Tropical Worsted Wool, 38% Poly-Viscose, 2% Lycra",
                "weave": "Fine Birdseye Tropical Suiting (220 GSM)",
                "fit": "Executive Slim Formal",
                "waist": "Mid-Rise with Internal Rubberised Shirt-Gripper",
                "crease": "Permanent Super-Crease Front & Back",
                "care": "Dry clean only recommended. Steaming restores fresh crease without heat damage.",
                "sizes": ["30", "32", "34", "36", "38"],
                "color": "Heather Charcoal Grey",
                "origin": "Tailored in Bhilwara, Rajasthan",
                "refined_photo_url": "/clothing/grey_trouser.jpg",
                "marketplaces": [
                    {
                        "name": "Amazon India",
                        "code": "AMAZON",
                        "status": "ACTIVE",
                        "listing_id": "ASIN: B0D9W21GRY",
                        "price_paise": 279900,
                        "fee_percent": 15.0,
                        "fulfillment": "FBA Prime",
                        "orders_today": 4,
                        "rating": "4.9 ★"
                    },
                    {
                        "name": "Flipkart",
                        "code": "FLIPKART",
                        "status": "ACTIVE",
                        "listing_id": "FSN: TRSGRY441",
                        "price_paise": 279900,
                        "fee_percent": 14.5,
                        "fulfillment": "Flipkart Assured",
                        "orders_today": 2,
                        "rating": "4.8 ★"
                    },
                    {
                        "name": "Meesho",
                        "code": "MEESHO",
                        "status": "NOT_LISTED",
                        "listing_id": "Unlisted (Not suitable for discount portal)",
                        "price_paise": 279900,
                        "fee_percent": 0.0,
                        "fulfillment": "None",
                        "orders_today": 0
                    },
                    {
                        "name": "Myntra",
                        "code": "MYNTRA",
                        "status": "ACTIVE (PRIME FASHION)",
                        "listing_id": "MYN-VAST-GRY-02",
                        "price_paise": 299900,
                        "fee_percent": 18.0,
                        "fulfillment": "Myntra Omni-Studio",
                        "orders_today": 5,
                        "rating": "4.9 ★"
                    },
                    {
                        "name": "Vastram Direct (WhatsApp)",
                        "code": "WHATSAPP",
                        "status": "ACTIVE (PRIMARY)",
                        "listing_id": "WA-CATALOG-TR02",
                        "price_paise": 279900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Express",
                        "orders_today": 4,
                        "rating": "5.0 ★"
                    }
                ],
                "recommendations": []  # <--- NONE! Kept as None as explicitly requested by user!
            })
        ),
        # 6. Jet Black Formal Trousers
        (
            "prod_vastram_trouser_black",
            "Constructed with high-tenacity yarn-dyed black fibers that resist fading even after 50+ wash cycles, the Vastram Classic Jet Black Formal Trousers are an enduring foundation for black-tie, corporate, and ceremony wear. Spun from a non-iron, stain-repellent poly-viscose blend that naturally resists creases throughout 14-hour workdays. Features French hook-and-bar front closure, concealed zip security pocket, and clean straight-leg profile.",
            json.dumps({
                "fabric": "70% Polyester, 28% Viscose Rayon, 2% Elastane",
                "weave": "Stain-Repellent Cavalry Twill (250 GSM)",
                "fit": "Regular Straight Formal Fit",
                "waist": "Expandable Comfort Waistband (+1.5 inches dynamic flex)",
                "closure": "Double French Hook-and-Bar with Concealed Safety Zip",
                "care": "Machine wash cold gentle cycle. Permanent press dry. No iron required.",
                "sizes": ["30", "32", "34", "36", "38", "40"],
                "color": "Deep Carbon Jet Black",
                "origin": "Tailored in Ahmedabad, Gujarat",
                "refined_photo_url": "/clothing/black_trouser.jpg",
                "marketplaces": [
                    {
                        "name": "Amazon India",
                        "code": "AMAZON",
                        "status": "PAUSED (LOW STOCK)",
                        "listing_id": "ASIN: B0D6B12BLK",
                        "price_paise": 219900,
                        "fee_percent": 15.0,
                        "fulfillment": "FBA Prime",
                        "orders_today": 2,
                        "rating": "4.8 ★"
                    },
                    {
                        "name": "Flipkart",
                        "code": "FLIPKART",
                        "status": "PAUSED (LOW STOCK)",
                        "listing_id": "FSN: TRSBLK112",
                        "price_paise": 219900,
                        "fee_percent": 14.5,
                        "fulfillment": "Flipkart Assured",
                        "orders_today": 1,
                        "rating": "4.7 ★"
                    },
                    {
                        "name": "Meesho",
                        "code": "MEESHO",
                        "status": "NOT_LISTED",
                        "listing_id": "Unlisted",
                        "price_paise": 209900,
                        "fee_percent": 0.0,
                        "fulfillment": "Self-Ship",
                        "orders_today": 0
                    },
                    {
                        "name": "Myntra",
                        "code": "MYNTRA",
                        "status": "PAUSED (LOW STOCK)",
                        "listing_id": "MYN-VAST-BLK-03",
                        "price_paise": 239900,
                        "fee_percent": 18.0,
                        "fulfillment": "Omni Express",
                        "orders_today": 1,
                        "rating": "4.8 ★"
                    },
                    {
                        "name": "Vastram Direct (WhatsApp)",
                        "code": "WHATSAPP",
                        "status": "ACTIVE (SOLE CHANNEL)",
                        "listing_id": "WA-CATALOG-TR03",
                        "price_paise": 219900,
                        "fee_percent": 0.0,
                        "fulfillment": "Direct Express",
                        "orders_today": 5,
                        "rating": "4.9 ★"
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec_tr_03_stock",
                        "type": "CHANNEL_SHIFT",
                        "badge": "STOCKOUT PREVENTION",
                        "title": "Delist from Amazon & Flipkart immediately to protect remaining 6 units",
                        "impact": "Saves ₹8,500 OOS Penalties",
                        "description": "Stock is down to critical 6 units (depleting in ~7.5 hours). Pause all marketplace listings (Amazon & Flipkart) to avoid stockout penalty fees, and funnel all remaining 6 units exclusively through WhatsApp Direct to retain 64.1% full gross profit.",
                        "action_label": "Halt Marketplaces & Channel to WhatsApp",
                        "is_channel_action": True
                    },
                    {
                        "id": "rec_tr_03_reorder",
                        "type": "SUPPLIER_REORDER",
                        "badge": "SUPPLY CHAIN ACTION",
                        "title": "Urgent Supplier Reorder +50 Units",
                        "impact": "Protects ₹1,09,950 Sales Pipeline",
                        "description": "Reorder 50 units immediately from the Coimbatore mill. Current velocity of 12 orders/day will lead to zero stock by tonight.",
                        "action_label": "Dispatch Supplier Reorder PO"
                    }
                ]
            })
        )
    ]

    for pid, desc, attrs in products_data:
        cur.execute("""
            UPDATE products
            SET description = ?, attributes = ?
            WHERE id = ?
        """, (desc, attrs, pid))

    conn.commit()
    conn.close()
    print("Successfully enriched Vastram products with descriptions, marketplaces, and tailored AI recommendations!")

if __name__ == '__main__':
    enrich_products()
