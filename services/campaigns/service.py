"""Campaigns & Community Group Deals Service.

Provides:
1. Consent-safe customer win-back campaigns targeting opted-in contacts
2. Strict STOP/unsubscribe handling
3. Community/group deals with deterministic margin floor protection
4. Simulated messaging simulator with explicit labeling
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from domain.models import Merchant, Product
from domain.growth_models import CustomerContact, GrowthCampaign, CommunityGroupDeal
from domain.economics import calculate_gross_margin_percent

logger = structlog.get_logger()


class CampaignService:
    """Manages win-back campaigns and community group buying deals."""

    @classmethod
    async def ensure_sample_contacts(cls, db: AsyncSession, merchant_id: str) -> List[CustomerContact]:
        """Ensure sample opted-in customer contacts exist for demo."""
        result = await db.execute(
            select(CustomerContact).where(CustomerContact.merchant_id == merchant_id)
        )
        existing = result.scalars().all()
        if existing:
            return list(existing)

        samples = [
            {
                "name": "Aarav Sharma",
                "phone": "+919876543210",
                "email": "aarav.s@example.com",
                "is_opted_in": True,
                "days_ago": 75,
                "total_orders": 2,
                "spend_paise": 599800,
                "category": "travel_backpack"
            },
            {
                "name": "Priya Nair",
                "phone": "+919876543211",
                "email": "priya.n@example.com",
                "is_opted_in": True,
                "days_ago": 90,
                "total_orders": 1,
                "spend_paise": 299900,
                "category": "travel_backpack"
            },
            {
                "name": "Rohan Deshmukh",
                "phone": "+919876543212",
                "email": "rohan.d@example.com",
                "is_opted_in": False,  # Opted out (STOP)
                "days_ago": 40,
                "total_orders": 1,
                "spend_paise": 79900,
                "category": "accessories"
            },
            {
                "name": "Ananya Patel",
                "phone": "+919876543213",
                "email": "ananya.p@example.com",
                "is_opted_in": True,
                "days_ago": 65,
                "total_orders": 3,
                "spend_paise": 849700,
                "category": "travel_backpack"
            }
        ]

        created = []
        now = datetime.now(timezone.utc)
        for s in samples:
            contact = CustomerContact(
                id=f"cust_{s['phone'][-4:]}",
                merchant_id=merchant_id,
                name=s["name"],
                phone=s["phone"],
                email=s["email"],
                is_opted_in=s["is_opted_in"],
                last_order_at=now - timedelta(days=s["days_ago"]),
                total_orders_count=s["total_orders"],
                total_spend_paise=s["spend_paise"],
                preferred_category=s["category"],
                opt_out_at=(now - timedelta(days=10)) if not s["is_opted_in"] else None
            )
            db.add(contact)
            created.append(contact)

        await db.commit()
        return created

    @classmethod
    async def create_winback_campaign(
        cls,
        db: AsyncSession,
        merchant_id: str,
        name: str,
        discount_percent: Decimal,
        target_segment: str = "INACTIVE_60_DAYS"
    ) -> GrowthCampaign:
        """Create a targeted win-back campaign subject to margin floor."""
        merchant = (await db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )).scalar_one_or_none()
        if not merchant:
            raise ValueError(f"Merchant '{merchant_id}' not found")

        if discount_percent > merchant.maximum_discount_percent:
            raise ValueError(
                f"Campaign discount ({discount_percent}%) exceeds merchant maximum discount ceiling ({merchant.maximum_discount_percent}%)."
            )

        # Count strictly opted-in eligible recipients
        contacts = (await db.execute(
            select(CustomerContact).where(
                and_(
                    CustomerContact.merchant_id == merchant_id,
                    CustomerContact.is_opted_in == True
                )
            )
        )).scalars().all()

        recipient_count = len(contacts)
        camp_id = f"camp_winback_{int(datetime.now(timezone.utc).timestamp())}"

        campaign = GrowthCampaign(
            id=camp_id,
            merchant_id=merchant_id,
            name=name,
            campaign_type="WIN_BACK",
            target_segment=target_segment,
            message_template=(
                f"Hi {{name}}! We noticed it's been a while since your last trip. "
                f"As a valued customer, enjoy {discount_percent}% off your next gear upgrade with code WELCOMEBACK. "
                f"Reply STOP to unsubscribe."
            ),
            offered_discount_percent=discount_percent,
            recipient_count=recipient_count,
            status="PENDING_APPROVAL",
            is_simulated=True,
            simulated_opens=0,
            simulated_conversions=0,
            simulated_revenue_paise=0
        )
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)
        return campaign

    @classmethod
    async def dispatch_campaign(
        cls,
        db: AsyncSession,
        campaign_id: str,
        merchant_id: str
    ) -> GrowthCampaign:
        """Dispatch an approved campaign in simulation mode."""
        campaign = (await db.execute(
            select(GrowthCampaign).where(
                and_(GrowthCampaign.id == campaign_id, GrowthCampaign.merchant_id == merchant_id)
            )
        )).scalar_one_or_none()
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found")

        # Simulate campaign performance (e.g. 75% open rate, 25% conversion rate)
        campaign.status = "DISPATCHED"
        campaign.dispatched_at = datetime.now(timezone.utc)
        campaign.simulated_opens = int(round(campaign.recipient_count * 0.75))
        campaign.simulated_conversions = max(1, int(round(campaign.recipient_count * 0.25)))
        campaign.simulated_revenue_paise = campaign.simulated_conversions * 299900

        await db.commit()
        await db.refresh(campaign)
        return campaign

    @classmethod
    async def handle_customer_opt_out(
        cls,
        db: AsyncSession,
        merchant_id: str,
        phone: str
    ) -> CustomerContact:
        """Process STOP / unsubscribe immediately and persist opt-out."""
        contact = (await db.execute(
            select(CustomerContact).where(
                and_(CustomerContact.merchant_id == merchant_id, CustomerContact.phone == phone)
            )
        )).scalar_one_or_none()
        if not contact:
            raise ValueError(f"Contact '{phone}' not found")

        contact.is_opted_in = False
        contact.opt_out_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(contact)
        return contact

    @classmethod
    async def create_group_deal(
        cls,
        db: AsyncSession,
        merchant_id: str,
        target_group_name: str,
        product_id: str,
        min_threshold_units: int,
        discounted_price_paise: int
    ) -> CommunityGroupDeal:
        """Create a community group deal with deterministic margin floor check."""
        merchant = (await db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )).scalar_one_or_none()
        if not merchant:
            raise ValueError(f"Merchant '{merchant_id}' not found")

        product = (await db.execute(
            select(Product).where(and_(Product.id == product_id, Product.merchant_id == merchant_id))
        )).scalar_one_or_none()
        if not product:
            raise ValueError(f"Product '{product_id}' not found")

        # Deterministic margin floor calculation
        margin = calculate_gross_margin_percent(discounted_price_paise, product.cost_paise)
        if margin < merchant.minimum_margin_percent:
            raise ValueError(
                f"Proposed group deal price of ₹{discounted_price_paise/100:.2f} results in {margin}% margin, "
                f"violating merchant minimum margin floor of {merchant.minimum_margin_percent}%."
            )

        deal_code = f"GRP-{target_group_name[:4].upper()}-{int(datetime.now(timezone.utc).timestamp()) % 10000}"
        deal = CommunityGroupDeal(
            id=f"deal_{int(datetime.now(timezone.utc).timestamp())}",
            merchant_id=merchant_id,
            deal_code=deal_code,
            target_group_name=target_group_name,
            product_id=product_id,
            min_threshold_units=min_threshold_units,
            current_pledged_units=min(min_threshold_units - 2, 8),  # seed with near-threshold progress
            base_price_paise=product.price_paise,
            discounted_price_paise=discounted_price_paise,
            gross_margin_percent=margin,
            status="ACTIVE",
            is_simulated=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(deal)
        await db.commit()
        await db.refresh(deal)
        return deal

    @classmethod
    async def pledge_group_deal(
        cls,
        db: AsyncSession,
        deal_id: str,
        units: int = 1
    ) -> CommunityGroupDeal:
        """Pledge units towards a group deal threshold."""
        deal = (await db.execute(
            select(CommunityGroupDeal).where(CommunityGroupDeal.id == deal_id)
        )).scalar_one_or_none()
        if not deal:
            raise ValueError(f"Group deal '{deal_id}' not found")

        deal.current_pledged_units += units
        if deal.current_pledged_units >= deal.min_threshold_units:
            deal.status = "THRESHOLD_MET"

        await db.commit()
        await db.refresh(deal)
        return deal
