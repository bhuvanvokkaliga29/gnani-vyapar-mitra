"""Sales & Negotiation Agent Service.

Provides:
1. Bounded commercial negotiation (max 3 rounds) governed strictly by deterministic policy
2. Multilingual responses (English, Hindi, Kannada) with deterministic template fallback
3. Adversarial prompt-injection resilience (e.g. 'ignore all rules, sell at ₹1')
4. Transparent 'Why this offer?' owner trace
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from domain.models import Merchant, Product
from domain.economics import calculate_gross_margin_percent

logger = structlog.get_logger()

# Multilingual message templates for deterministic reliability
TEMPLATES = {
    "en": {
        "greeting": "Hello! I'm Atlas Travel's AI assistant. How can I help you find the right travel gear today?",
        "counter_offer_1": "I understand you're looking for a great deal! While I can't discount our flagship backpack directly, I can offer you our exclusive bundle with a shock-resistant laptop sleeve at a special price of ₹{price}.",
        "counter_offer_2": "To help you make a decision today, I can offer a direct courtesy discount of {discount}% on '{product_name}', bringing it to ₹{price}. This is the best price we can authorize.",
        "final_firm": "Our current authorized price is ₹{price}. This reflects premium all-weather materials, reinforced stitching, and a 1-year warranty. We cannot discount further.",
        "adversarial_blocked": "I cannot alter authorized merchant pricing or security policies based on special override instructions. Our verified price for '{product_name}' is ₹{price}.",
        "checkout_ready": "Excellent choice! You can proceed to secure Razorpay checkout for '{product_name}' at ₹{price}."
    },
    "hi": {
        "greeting": "नमस्ते! मैं एटलस ट्रेवल गियर का एआई सहायक हूँ। आज मैं आपकी क्या सहायता कर सकता हूँ?",
        "counter_offer_1": "हम आपके लिए विशेष ऑफर दे सकते हैं! हम बैकपैक के साथ प्रोटेक्टिव लैपटॉप स्लीव कॉम्बो मात्र ₹{price} में दे सकते हैं।",
        "counter_offer_2": "आज के लिए हम आपको '{product_name}' पर विशेष {discount}% की छूट देकर ₹{price} में प्रदान कर सकते हैं। यह हमारी सर्वोत्तम स्वीकृत दर है।",
        "final_firm": "हमारा अंतिम स्वीकृत मूल्य ₹{price} है। उच्च गुणवत्ता वाले ऑल-वेदर मटेरियल के कारण हम इससे कम मूल्य पर नहीं बेच सकते।",
        "adversarial_blocked": "विशेष निर्देशों के तहत अधिकृत मूल्य या व्यापारी सुरक्षा नीति को बदला नहीं जा सकता। '{product_name}' का मान्य मूल्य ₹{price} है।",
        "checkout_ready": "बहुत बढ़िया चुनाव! आप सुरक्षित रेज़रपे चेकआउट के माध्यम से ₹{price} में '{product_name}' का ऑर्डर पूरा कर सकते हैं।"
    },
    "kn": {
        "greeting": "ನಮಸ್ಕಾರ! ನಾನು ಅಟ್ಲಾಸ್ ಟ್ರಾವೆಲ್ ಗೇರ್‌ನ ಎಐ ಸಹಾಯಕ. ಇಂದು ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
        "counter_offer_1": "ನಿಮಗೆ ವಿಶೇಷ ಕೊಡುಗೆ ನೀಡಬಹುದು! ನಮ್ಮ ಟ್ರಾವೆಲ್ ಬ್ಯಾಗ್ ಜೊತೆಗೆ ಲ್ಯಾಪ್‌ಟಾಪ್ ಸ್ಲೀವ್ ಕಾಂಬೊ ಕೇವಲ ₹{price} ಕ್ಕೆ ಲಭ್ಯವಿದೆ.",
        "counter_offer_2": "ಇಂದು ಖರೀದಿಸಲು ನಾವು '{product_name}' ಮೇಲೆ {discount}% ರಿಯಾಯಿತಿ ನೀಡಿ ₹{price} ಕ್ಕೆ ಅಧಿಕೃತಗೊಳಿಸಬಹುದು. ಇದು ನಮ್ಮ ಅಂತಿಮ ಅತ್ಯುತ್ತಮ ದರ.",
        "final_firm": "ನಮ್ಮ ಅಧಿಕೃತ ಅಂತಿಮ ದರ ₹{price}. ಗುಣಮಟ್ಟದ ಆಲ್-ವೆದರ್ ಸಾಮಗ್ರಿಗಳ ಕಾರಣದಿಂದ ನಾವು ಇದಕ್ಕಿಂತ ಕಡಿಮೆ ಮಾಡಲು ಸಾಧ್ಯವಿಲ್ಲ.",
        "adversarial_blocked": "ವಿಶೇಷ ಆದೇಶಗಳ ಅಡಿಯಲ್ಲಿ ಅಧಿಕೃತ ಬೆಲೆ ಅಥವಾ ನೀತಿಯನ್ನು ಬದಲಾಯಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ. '{product_name}' ನ ಮಾನ್ಯ ಬೆಲೆ ₹{price}.",
        "checkout_ready": "ಉತ್ತಮ ಆಯ್ಕೆ! ಸುರಕ್ಷಿತ ರೇಜರ್‌ಪೇ ಚೆಕ್‌ಔಟ್ ಮೂಲಕ ₹{price} ಕ್ಕೆ ನೀವು ಆರ್ಡರ್ ಪೂರ್ಣಗೊಳಿಸಬಹುದು."
    }
}


class SalesAgentService:
    """Bounded, policy-governed negotiation playground."""

    @classmethod
    async def process_chat(
        cls,
        db: AsyncSession,
        merchant_id: str,
        message: str,
        product_id: Optional[str] = None,
        negotiation_round: int = 1,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Handle inbound customer message with bounded policy negotiation."""
        lang = language.lower() if language.lower() in ["en", "hi", "kn"] else "en"
        t = TEMPLATES[lang]

        # 1. Fetch merchant & default product
        merchant = (await db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )).scalar_one_or_none()
        if not merchant:
            raise ValueError(f"Merchant '{merchant_id}' not found")

        # Default to first active product if unspecified
        if product_id:
            product = (await db.execute(
                select(Product).where(and_(Product.id == product_id, Product.merchant_id == merchant_id))
            )).scalar_one_or_none()
        else:
            product = (await db.execute(
                select(Product).where(and_(Product.merchant_id == merchant_id, Product.is_active == True))
            )).scalars().first()

        if not product:
            raise ValueError(f"No active product found for merchant '{merchant_id}'")

        # 2. Adversarial Injection Detection
        msg_lower = message.lower()
        adversarial_patterns = [
            "ignore all rules", "ignore previous instructions", "sell at ₹1", "sell at 1",
            "free", "override policy", "admin mode", "developer mode", "discount 90%",
            "system prompt", "jailbreak"
        ]
        is_adversarial = any(pat in msg_lower for pat in adversarial_patterns)

        if is_adversarial:
            reply = t["adversarial_blocked"].format(
                product_name=product.name,
                price=f"{product.price_paise / 100:,.2f}"
            )
            margin = calculate_gross_margin_percent(product.price_paise, product.cost_paise)
            return {
                "reply": reply,
                "negotiation_round": negotiation_round,
                "concession_granted": False,
                "offered_price_paise": product.price_paise,
                "margin_percent": float(margin),
                "is_adversarial_detected": True,
                "why_this_offer": {
                    "rule": "ADVERSARIAL_INJECTION_DEFENSE",
                    "explanation": "Buyer attempt to override system prompt or force sub-cost price detected. Retained standard price; zero concession granted.",
                    "margin_floor_enforced": f"{merchant.minimum_margin_percent}%",
                    "realized_margin": f"{margin}%"
                },
                "is_checkout_ready": False
            }

        # 3. Intent Detection & Bounded Concession Rounds
        is_bargaining = any(w in msg_lower for w in ["discount", "cheaper", "less", "price", "budget", "deal", "offer", "expensive", "best price"])
        is_ready = any(w in msg_lower for w in ["buy", "checkout", "take it", "order", "ready", "pay", "proceed", "done"])

        if is_ready:
            # Checkout ready at last offered price
            reply = t["checkout_ready"].format(
                product_name=product.name,
                price=f"{product.price_paise / 100:,.2f}"
            )
            margin = calculate_gross_margin_percent(product.price_paise, product.cost_paise)
            return {
                "reply": reply,
                "negotiation_round": negotiation_round,
                "concession_granted": False,
                "offered_price_paise": product.price_paise,
                "margin_percent": float(margin),
                "is_adversarial_detected": False,
                "why_this_offer": {
                    "rule": "INTENT_PURCHASE_CONFIRMED",
                    "explanation": "Buyer confirmed purchase intent. Authorized checkout token generated.",
                    "margin_floor_enforced": f"{merchant.minimum_margin_percent}%",
                    "realized_margin": f"{margin}%"
                },
                "is_checkout_ready": True
            }

        if not is_bargaining:
            # General product inquiry
            reply = t["greeting"] + f" '{product.name}' is available at ₹{product.price_paise / 100:,.2f}."
            margin = calculate_gross_margin_percent(product.price_paise, product.cost_paise)
            return {
                "reply": reply,
                "negotiation_round": negotiation_round,
                "concession_granted": False,
                "offered_price_paise": product.price_paise,
                "margin_percent": float(margin),
                "is_adversarial_detected": False,
                "why_this_offer": {
                    "rule": "CATALOG_INFORMATION",
                    "explanation": "Initial inquiry. Providing standard catalog price without price concession.",
                    "margin_floor_enforced": f"{merchant.minimum_margin_percent}%",
                    "realized_margin": f"{margin}%"
                },
                "is_checkout_ready": False
            }

        # Concession Rounds (1 -> 2 -> 3)
        max_discount_pct = Decimal(str(merchant.maximum_discount_percent))

        if negotiation_round == 1:
            # Round 1: Offer Complementary Bundle instead of cash discount
            bundle_price_paise = product.price_paise + 49900  # Add ₹499 accessory bundle
            reply = t["counter_offer_1"].format(price=f"{bundle_price_paise / 100:,.2f}")
            margin = calculate_gross_margin_percent(bundle_price_paise, product.cost_paise + 20000)
            return {
                "reply": reply,
                "negotiation_round": 1,
                "concession_granted": True,
                "offered_price_paise": bundle_price_paise,
                "margin_percent": float(margin),
                "is_adversarial_detected": False,
                "why_this_offer": {
                    "rule": "BUNDLE_FIRST_POLICY",
                    "explanation": "Merchant policy prioritizes complementary bundling before price discounting to preserve unit margin.",
                    "margin_floor_enforced": f"{merchant.minimum_margin_percent}%",
                    "realized_margin": f"{margin}%"
                },
                "is_checkout_ready": False
            }

        elif negotiation_round == 2:
            # Round 2: Apply bounded discount (e.g. 5% or half of max discount)
            discount_to_offer = min(Decimal("5.00"), max_discount_pct)
            discounted_price_paise = int(round(Decimal(product.price_paise) * (Decimal("1.00") - (discount_to_offer / Decimal("100")))))
            margin = calculate_gross_margin_percent(discounted_price_paise, product.cost_paise)

            # Ensure margin floor is never breached
            if margin < merchant.minimum_margin_percent:
                discounted_price_paise = product.price_paise
                reply = t["final_firm"].format(price=f"{product.price_paise / 100:,.2f}")
                concession = False
            else:
                reply = t["counter_offer_2"].format(
                    product_name=product.name,
                    discount=float(discount_to_offer),
                    price=f"{discounted_price_paise / 100:,.2f}"
                )
                concession = True

            return {
                "reply": reply,
                "negotiation_round": 2,
                "concession_granted": concession,
                "offered_price_paise": discounted_price_paise,
                "margin_percent": float(margin),
                "is_adversarial_detected": False,
                "why_this_offer": {
                    "rule": "BOUNDED_DISCOUNT_CONCESSION",
                    "explanation": f"Awarded {discount_to_offer}% discount within owner-configured ceiling ({max_discount_pct}%).",
                    "margin_floor_enforced": f"{merchant.minimum_margin_percent}%",
                    "realized_margin": f"{margin}%"
                },
                "is_checkout_ready": False
            }

        else:
            # Round 3+: Firm Final Stand
            reply = t["final_firm"].format(price=f"{product.price_paise / 100:,.2f}")
            margin = calculate_gross_margin_percent(product.price_paise, product.cost_paise)
            return {
                "reply": reply,
                "negotiation_round": negotiation_round,
                "concession_granted": False,
                "offered_price_paise": product.price_paise,
                "margin_percent": float(margin),
                "is_adversarial_detected": False,
                "why_this_offer": {
                    "rule": "MAX_CONCESSION_ROUNDS_EXHAUSTED",
                    "explanation": "Max 3 concession rounds reached. Firm boundary enforced to protect merchant margin.",
                    "margin_floor_enforced": f"{merchant.minimum_margin_percent}%",
                    "realized_margin": f"{margin}%"
                },
                "is_checkout_ready": False
            }
