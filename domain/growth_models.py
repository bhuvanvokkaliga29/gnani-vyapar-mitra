"""SQLAlchemy Models for Merchant Growth Agent Modules.

Encompasses:
- Growth Doctor (evidence-backed diagnoses & proposals)
- Marketplace Growth Manager (channel configuration & SKU channel decisions)
- Owner Policy Confirmation & Approvals Queue
- Customer Contacts & Consent-safe Win-back Campaigns
- Community / Group Deals
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Index,
    func
)
from sqlalchemy.orm import relationship
from domain.models import Base


class GrowthDoctorFinding(Base):
    """Deterministic, evidence-backed findings on merchant performance and profit leaks."""
    __tablename__ = "growth_doctor_findings"

    id = Column(String(64), primary_key=True, index=True)  # doc_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(32), nullable=False, index=True)  # DEAD_STOCK, MARGIN_LEAKAGE, UNDERPRICED, MISSED_SALES
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rupee_impact_paise = Column(BigInteger, nullable=False, default=0)
    confidence = Column(String(16), nullable=False, default="HIGH")  # HIGH, MEDIUM, LOW
    method_note = Column(Text, nullable=False)
    evidence_rows_json = Column(JSON, nullable=False, default=list)
    recommended_action_type = Column(String(64), nullable=False)
    recommended_action_payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="DETECTED", index=True)  # DETECTED, PROPOSED, APPROVED, RESOLVED, REJECTED
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_doctor_findings_merchant_cat", "merchant_id", "category"),
    )


class ChannelConfig(Base):
    """Channel economics and fee structure assumptions for digital channels."""
    __tablename__ = "channel_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id = Column(String(32), nullable=False, index=True)  # AMAZON, FLIPKART, MEESHO, DIRECT_WHATSAPP, GOOGLE_LOCAL, INSTAGRAM, ONDC
    name = Column(String(64), nullable=False)
    fee_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    fixed_fee_paise = Column(BigInteger, nullable=False, default=0)
    shipping_base_paise = Column(BigInteger, nullable=False, default=0)
    return_rate_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    return_cost_paise = Column(BigInteger, nullable=False, default=0)
    ad_cost_paise = Column(BigInteger, nullable=False, default=0)
    verification_status = Column(String(16), nullable=False, default="SAMPLE")  # VERIFIED, SAMPLE, VERIFY
    audience_fit = Column(String(128), nullable=False, default="General retail shoppers")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "channel_id", name="uq_channel_config_merchant_channel"),
    )


class SKUChannelDecision(Base):
    """Authoritative net contribution calculation and allocation decision for a product on a channel."""
    __tablename__ = "sku_channel_decisions"

    id = Column(String(64), primary_key=True, index=True)  # chdec_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(64), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(64), nullable=False, index=True)
    channel_id = Column(String(32), nullable=False, index=True)
    decision = Column(String(32), nullable=False, index=True)  # LIST, HOLD, DIRECT_CHANNEL
    selling_price_paise = Column(BigInteger, nullable=False)
    cogs_paise = Column(BigInteger, nullable=False)
    estimated_fees_paise = Column(BigInteger, nullable=False, default=0)
    estimated_shipping_paise = Column(BigInteger, nullable=False, default=0)
    expected_return_cost_paise = Column(BigInteger, nullable=False, default=0)
    estimated_ad_cost_paise = Column(BigInteger, nullable=False, default=0)
    net_contribution_paise = Column(BigInteger, nullable=False)
    margin_percent = Column(Numeric(5, 2), nullable=False)
    rationale = Column(Text, nullable=False)
    confidence = Column(String(16), nullable=False, default="HIGH")  # HIGH, MEDIUM, LOW
    is_published = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "product_id", "channel_id", name="uq_sku_channel_decision"),
        Index("ix_sku_channel_decisions_merchant_decision", "merchant_id", "decision"),
    )


class OwnerPolicyProposal(Base):
    """Parsed merchant commercial policy awaiting explicit confirmation by merchant owner."""
    __tablename__ = "owner_policy_proposals"

    id = Column(String(64), primary_key=True, index=True)  # polprop_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_input_text = Column(Text, nullable=False)
    parsed_policy_json = Column(JSON, nullable=False)
    clarification_needed = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING_CONFIRMATION", index=True)  # PENDING_CONFIRMATION, CONFIRMED, REJECTED
    confirmed_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class OwnerApprovalItem(Base):
    """Pending commercial actions requiring explicit owner sign-off."""
    __tablename__ = "owner_approval_items"

    id = Column(String(64), primary_key=True, index=True)  # appr_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(32), nullable=False, index=True)  # DISCOUNT_OVER_LIMIT, PRICE_UPDATE, CAMPAIGN_DISPATCH, CHANNEL_ALLOCATION, GROUP_DEAL
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    payload_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class CustomerContact(Base):
    """First-party opted-in customer contact for consent-safe win-back campaigns."""
    __tablename__ = "customer_contacts"

    id = Column(String(64), primary_key=True, index=True)  # cust_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=False, index=True)
    email = Column(String(128), nullable=True)
    is_opted_in = Column(Boolean, nullable=False, default=True, index=True)
    last_order_at = Column(DateTime(timezone=True), nullable=True)
    total_orders_count = Column(Integer, nullable=False, default=0)
    total_spend_paise = Column(BigInteger, nullable=False, default=0)
    preferred_category = Column(String(64), nullable=True)
    opt_out_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "phone", name="uq_customer_contact_merchant_phone"),
    )


class GrowthCampaign(Base):
    """Marketing and win-back campaigns governed by merchant policy and consent."""
    __tablename__ = "growth_campaigns"

    id = Column(String(64), primary_key=True, index=True)  # camp_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    campaign_type = Column(String(32), nullable=False, default="WIN_BACK")  # WIN_BACK, SEASONAL, PRODUCT_LAUNCH
    target_segment = Column(String(64), nullable=False, default="INACTIVE_60_DAYS")
    message_template = Column(Text, nullable=False)
    offered_discount_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    target_sku = Column(String(64), nullable=True)
    recipient_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)  # DRAFT, PENDING_APPROVAL, APPROVED, DISPATCHED, CANCELLED
    is_simulated = Column(Boolean, nullable=False, default=True)
    simulated_opens = Column(Integer, nullable=False, default=0)
    simulated_conversions = Column(Integer, nullable=False, default=0)
    simulated_revenue_paise = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)


class CommunityGroupDeal(Base):
    """Hyper-local community and group buying deal with deterministic margin floor protection."""
    __tablename__ = "community_group_deals"

    id = Column(String(64), primary_key=True, index=True)  # grp_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_code = Column(String(32), unique=True, nullable=False, index=True)
    target_group_name = Column(String(128), nullable=False)  # e.g., 'Prestige Tech Park Hostel'
    product_id = Column(String(64), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    min_threshold_units = Column(Integer, nullable=False, default=10)
    current_pledged_units = Column(Integer, nullable=False, default=0)
    base_price_paise = Column(BigInteger, nullable=False)
    discounted_price_paise = Column(BigInteger, nullable=False)
    gross_margin_percent = Column(Numeric(5, 2), nullable=False)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)  # ACTIVE, THRESHOLD_MET, EXPIRED, CANCELLED
    is_simulated = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MerchantCallbackRequest(Base):
    """Voice advisor callback request for independent merchants."""
    __tablename__ = "merchant_callback_requests"

    id = Column(String(64), primary_key=True, index=True)  # cb_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number = Column(String(32), nullable=False)
    merchant_name = Column(String(128), nullable=True, default="Vastram Owner")
    preferred_language = Column(String(16), nullable=False, default="kn")  # kn, hi, en
    topic = Column(String(64), nullable=False, default="GENERAL_GROWTH")  # SALES_SUMMARY, INVENTORY_REORDER, PRICING_STRATEGY, DEAD_STOCK
    reason = Column(Text, nullable=True)
    preferred_time_slot = Column(String(64), nullable=True, default="Immediate (Next 10 mins)")
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING, SCHEDULED, IN_CALL, COMPLETED, CANCELLED
    summary_notes = Column(Text, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
