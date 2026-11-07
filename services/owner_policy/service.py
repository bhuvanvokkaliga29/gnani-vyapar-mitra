"""Owner Policy Setup & Confirmation Service.

Provides:
1. Natural language policy extraction into structured commercial constraints
2. Mandatory explicit owner confirmation step before any policy becomes active
3. Approval queue management for high-concession actions
"""

import re
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from domain.models import Merchant, MerchantPriority
from domain.growth_models import OwnerPolicyProposal, OwnerApprovalItem

logger = structlog.get_logger()


class OwnerPolicyService:
    """Manages merchant owner commercial intent, parsing, confirmation, and approvals."""

    @classmethod
    def parse_natural_language_policy(cls, text: str) -> Dict[str, Any]:
        """Parse natural language statement into a strict, validated policy schema."""
        text_lower = text.lower()

        # 1. Margin Floor (e.g., '18% margin', 'margin 20%')
        margin_match = re.search(r'(?:margin\s*(?:floor)?\s*(?:of)?|never\s*sell\s*below)\s*(\d+(?:\.\d+)?)\s*%', text_lower)
        if margin_match:
            margin_floor = Decimal(margin_match.group(1))
        else:
            margin_floor = Decimal("25.00")

        # 2. Maximum Discount (e.g., 'no more than 10% discount', 'max discount 15%')
        discount_match = re.search(r'(?:no\s*more\s*than|max(?:imum)?\s*discount\s*(?:of)?)\s*(\d+(?:\.\d+)?)\s*%', text_lower)
        if discount_match:
            max_discount = Decimal(discount_match.group(1))
        else:
            max_discount = Decimal("10.00")

        # 3. Approval Threshold (e.g., 'ask (my )?approval for discounts above 5%')
        approval_match = re.search(r'approval\s*(?:for\s*discounts)?\s*above\s*(\d+(?:\.\d+)?)\s*%', text_lower)
        if approval_match:
            approval_threshold = Decimal(approval_match.group(1))
        else:
            approval_threshold = Decimal("5.00")

        # 4. No-Discount Categories
        no_discount_categories = []
        if "new arrival" in text_lower or "new arrivals" in text_lower:
            no_discount_categories.append("new_arrivals")
        if "limited edition" in text_lower:
            no_discount_categories.append("limited_edition")

        # 5. Clearance Priority
        clearance_priority = "clear old stock" in text_lower or "clearance" in text_lower or "dead stock" in text_lower

        # 6. Safety Bound Validation
        if margin_floor < Decimal("10.00"):
            raise ValueError("Margin floor cannot be set below 10.00% absolute safety minimum.")
        if max_discount > Decimal("30.00"):
            raise ValueError("Maximum discount cannot exceed 30.00% to prevent financial leakage.")

        return {
            "minimum_margin_percent": float(margin_floor),
            "maximum_discount_percent": float(max_discount),
            "approval_threshold_percent": float(approval_threshold),
            "no_discount_categories": no_discount_categories,
            "clearance_priority": clearance_priority,
            "supported_languages": ["en", "hi", "kn"],
            "quiet_hours": {"start": "22:00", "end": "08:00"}
        }

    @classmethod
    async def create_policy_proposal(
        cls,
        db: AsyncSession,
        merchant_id: str,
        input_text: str
    ) -> OwnerPolicyProposal:
        """Create a pending proposal requiring owner confirmation."""
        parsed = cls.parse_natural_language_policy(input_text)
        proposal_id = f"polprop_{int(datetime.now(timezone.utc).timestamp())}"

        proposal = OwnerPolicyProposal(
            id=proposal_id,
            merchant_id=merchant_id,
            raw_input_text=input_text,
            parsed_policy_json=parsed,
            status="PENDING_CONFIRMATION"
        )
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal

    @classmethod
    async def confirm_policy_proposal(
        cls,
        db: AsyncSession,
        proposal_id: str,
        merchant_id: str
    ) -> Merchant:
        """Explicitly confirm and activate an owner policy proposal."""
        proposal = (await db.execute(
            select(OwnerPolicyProposal).where(
                and_(OwnerPolicyProposal.id == proposal_id, OwnerPolicyProposal.merchant_id == merchant_id)
            )
        )).scalar_one_or_none()
        if not proposal:
            raise ValueError(f"Proposal '{proposal_id}' not found for merchant '{merchant_id}'")

        merchant = (await db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )).scalar_one_or_none()
        if not merchant:
            raise ValueError(f"Merchant '{merchant_id}' not found")

        # Apply confirmed policy to Merchant
        parsed = proposal.parsed_policy_json
        merchant.minimum_margin_percent = Decimal(str(parsed["minimum_margin_percent"]))
        merchant.maximum_discount_percent = Decimal(str(parsed["maximum_discount_percent"]))

        # Update merchant priorities
        priority = (await db.execute(
            select(MerchantPriority).where(MerchantPriority.merchant_id == merchant_id)
        )).scalar_one_or_none()
        if priority:
            priority.priority_categories = parsed.get("no_discount_categories", [])

        proposal.status = "CONFIRMED"
        proposal.confirmed_at = datetime.now(timezone.utc)
        proposal.confirmed_by = "owner_primary"

        await db.commit()
        await db.refresh(merchant)
        return merchant

    @classmethod
    async def list_pending_approvals(
        cls,
        db: AsyncSession,
        merchant_id: str
    ) -> List[OwnerApprovalItem]:
        """Fetch all pending owner approvals."""
        result = await db.execute(
            select(OwnerApprovalItem)
            .where(and_(OwnerApprovalItem.merchant_id == merchant_id, OwnerApprovalItem.status == "PENDING"))
            .order_by(OwnerApprovalItem.created_at.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def resolve_approval(
        cls,
        db: AsyncSession,
        approval_id: str,
        merchant_id: str,
        decision: str  # APPROVED, REJECTED
    ) -> OwnerApprovalItem:
        """Resolve a pending owner approval item."""
        approval = (await db.execute(
            select(OwnerApprovalItem).where(
                and_(OwnerApprovalItem.id == approval_id, OwnerApprovalItem.merchant_id == merchant_id)
            )
        )).scalar_one_or_none()
        if not approval:
            raise ValueError(f"Approval item '{approval_id}' not found")

        approval.status = decision
        approval.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(approval)
        return approval
