"""Deterministic Merchant Policy Guard for WhatsApp Commerce Operations.

Enforces strict commercial guardrails on price modifications, promotional discounts,
and inventory changes before execution. Calculates compliant alternative floors
if policies are violated.
"""

import math
from decimal import Decimal
from typing import Optional, Tuple
from pydantic import BaseModel, Field

from domain.models import Merchant, Product


class PolicyValidationResult(BaseModel):
    """Result of policy verification on a proposed commercial action."""
    is_valid: bool = Field(..., description="True if action satisfies all merchant constraints")
    violation_type: Optional[str] = Field(None, description="'MARGIN_VIOLATION', 'DISCOUNT_VIOLATION', etc.")
    violation_reason: Optional[str] = Field(None, description="Human readable explanation")
    
    proposed_price_paise: int
    current_price_paise: int
    cost_paise: int
    
    current_margin_percent: float
    proposed_margin_percent: float
    minimum_margin_percent: float
    maximum_discount_percent: float
    
    compliant_price_paise: Optional[int] = Field(None, description="Safe compliant price in paise")
    compliant_price_rupees: Optional[int] = Field(None, description="Safe compliant price in rounded rupees")
    
    # Multilingual user-facing explanations
    message_en: str = ""
    message_kn: str = ""
    message_hi: str = ""


class PolicyGuard:
    """Evaluates and enforces merchant safety constraints."""

    @staticmethod
    def calculate_margin(price_paise: int, cost_paise: int) -> float:
        """Calculate profit margin percentage: ((price - cost) / price) * 100."""
        if price_paise <= 0:
            return 0.0
        return ((price_paise - cost_paise) / price_paise) * 100.0

    @staticmethod
    def calculate_compliant_price(
        cost_paise: int,
        min_margin_percent: float,
        current_price_paise: Optional[int] = None,
        max_discount_percent: Optional[float] = None
    ) -> int:
        """
        Calculate the lowest compliant selling price in paise.
        Satisfies:
          1) margin >= min_margin_percent -> price >= cost / (1 - min_margin/100)
          2) (if discount capped) price >= current_price * (1 - max_discount/100)
        """
        margin_frac = min_margin_percent / 100.0
        if margin_frac >= 1.0:
            margin_frac = 0.99  # guard against div by zero

        min_price_margin = math.ceil(cost_paise / (1.0 - margin_frac))

        min_price_discount = 0
        if current_price_paise and max_discount_percent:
            disc_frac = max_discount_percent / 100.0
            min_price_discount = math.ceil(current_price_paise * (1.0 - disc_frac))

        compliant = max(min_price_margin, min_price_discount)
        return int(compliant)

    @classmethod
    def validate_price_change(
        cls,
        merchant: Merchant,
        product: Product,
        proposed_price_paise: int,
        language: str = "en",
        enforce_discount_cap: bool = False
    ) -> PolicyValidationResult:
        """
        Validates proposed product price against merchant's minimum margin and optionally maximum discount.
        Generates compliant fallback if rejected.
        """
        cost_paise = product.cost_paise
        current_price_paise = product.price_paise
        min_margin = float(merchant.minimum_margin_percent)
        max_disc = float(merchant.maximum_discount_percent)

        curr_margin = cls.calculate_margin(current_price_paise, cost_paise)
        prop_margin = cls.calculate_margin(proposed_price_paise, cost_paise)

        # Check 1: Margin floor violation
        margin_violates = prop_margin < min_margin

        # Check 2: Discount cap violation (if price is reduced and discount cap enforcement requested)
        discount_violates = False
        discount_pct = 0.0
        if enforce_discount_cap and proposed_price_paise < current_price_paise and current_price_paise > 0:
            discount_pct = ((current_price_paise - proposed_price_paise) / current_price_paise) * 100.0
            if max_disc > 0 and discount_pct > max_disc:
                discount_violates = True

        if not margin_violates and not discount_violates:
            return PolicyValidationResult(
                is_valid=True,
                proposed_price_paise=proposed_price_paise,
                current_price_paise=current_price_paise,
                cost_paise=cost_paise,
                current_margin_percent=round(curr_margin, 2),
                proposed_margin_percent=round(prop_margin, 2),
                minimum_margin_percent=min_margin,
                maximum_discount_percent=max_disc,
                message_en="Price is policy compliant.",
                message_kn="ಬೆಲೆ ನೀತಿಬದ್ಧವಾಗಿದೆ.",
                message_hi="मूल्य नीति के अनुसार मान्य है।"
            )

        # Compute compliant floor
        compliant_paise = cls.calculate_compliant_price(
            cost_paise=cost_paise,
            min_margin_percent=min_margin,
            current_price_paise=current_price_paise if discount_violates else None,
            max_discount_percent=max_disc if discount_violates else None
        )
        compliant_rupees = math.ceil(compliant_paise / 100)
        proposed_rupees = proposed_price_paise // 100
        current_rupees = current_price_paise // 100

        violation_type = "MARGIN_VIOLATION" if margin_violates else "DISCOUNT_VIOLATION"
        violation_reason = (
            f"Proposed price ₹{proposed_rupees} yields a margin of {prop_margin:.1f}%, "
            f"below minimum floor of {min_margin:.1f}%."
            if margin_violates
            else f"Proposed discount of {discount_pct:.1f}% exceeds maximum allowed {max_disc:.1f}%."
        )

        msg_en = (
            f"⚠️ *Policy Guard Alert*: Price ₹{proposed_rupees} violates your minimum "
            f"margin floor ({min_margin:.0f}%). Proposed margin would be {prop_margin:.1f}% (Cost: ₹{cost_paise//100}).\n\n"
            f"🛡️ *Compliant Alternative*: Lowest safe price is *₹{compliant_rupees}* (gives {cls.calculate_margin(compliant_rupees*100, cost_paise):.1f}% margin).\n"
            f"Reply *YES* to accept ₹{compliant_rupees} or send a different price."
        )

        msg_kn = (
            f"⚠️ *ನೀತಿ ಎಚ್ಚರಿಕೆ (Policy Alert)*: ₹{proposed_rupees} ಬೆಲೆ ನಿಗದಿಪಡಿಸಿದರೆ ನಿಮ್ಮ ಲಾಭಾಂಶವು "
            f"{prop_margin:.1f}% ಆಗುತ್ತದೆ (ಅಸಲು: ₹{cost_paise//100}), ಇದು ಕನಿಷ್ಠ ಮಿತಿ {min_margin:.0f}% ಗಿಂತ ಕಡಿಮೆ.\n\n"
            f"🛡️ *ಸುರಕ್ಷಿತ ಪರ್ಯಾಯ ಬೆಲೆ*: ಕನಿಷ್ಠ ಮಾನ್ಯ ಬೆಲೆ *₹{compliant_rupees}* ಆಗಿದೆ.\n"
            f"ಈ ₹{compliant_rupees} ಬೆಲೆಯನ್ನು ಖಚಿತಪಡಿಸಲು *YES* ಎಂದು ಉತ್ತರಿಸಿ ಅಥವಾ ಬೇರೆ ಬೆಲೆಯನ್ನು ಕಳುಹಿಸಿ."
        )

        msg_hi = (
            f"⚠️ *पॉलिसी अलर्ट (Policy Alert)*: ₹{proposed_rupees} का मूल्य रखने पर आपका मार्जिन "
            f"{prop_margin:.1f}% रहेगा (लागत: ₹{cost_paise//100}), जो न्यूनतम सीमा {min_margin:.0f}% से कम है।\n\n"
            f"🛡️ *सुरक्षित विकल्प*: न्यूनतम स्वीकृत मूल्य *₹{compliant_rupees}* है।\n"
            f"₹{compliant_rupees} सेट करने के लिए *YES* भेजें या कोई अन्य मूल्य बताएं।"
        )

        return PolicyValidationResult(
            is_valid=False,
            violation_type=violation_type,
            violation_reason=violation_reason,
            proposed_price_paise=proposed_price_paise,
            current_price_paise=current_price_paise,
            cost_paise=cost_paise,
            current_margin_percent=round(curr_margin, 2),
            proposed_margin_percent=round(prop_margin, 2),
            minimum_margin_percent=min_margin,
            maximum_discount_percent=max_disc,
            compliant_price_paise=compliant_paise,
            compliant_price_rupees=compliant_rupees,
            message_en=msg_en,
            message_kn=msg_kn,
            message_hi=msg_hi
        )
