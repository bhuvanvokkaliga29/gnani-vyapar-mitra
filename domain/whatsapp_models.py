"""SQLAlchemy Models for WhatsApp Business Platform Integration & Auditing.

Includes:
1. WhatsAppWebhookLog: Inbound webhook event log and deduplication ledger.
2. WhatsAppPendingConfirmation: Expiring, single-use confirmation authorization tokens.
3. WhatsAppOutboundMessage: Outbound reply delivery tracking.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    Text,
    UniqueConstraint,
    Index,
    func
)
from domain.models import Base


class WhatsAppWebhookLog(Base):
    """Inbound webhook event ledger enforcing strict message-level deduplication."""
    __tablename__ = "whatsapp_webhook_logs"

    id = Column(String(64), primary_key=True, index=True)
    message_id = Column(String(128), unique=True, nullable=False, index=True)  # Meta WAMID (e.g. wamid.HBgL...)
    sender_phone = Column(String(32), nullable=False, index=True)  # Normalized (e.g. 919113960498)
    recipient_phone_id = Column(String(64), nullable=True)  # Meta Phone Number ID
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    message_text = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="RECEIVED", index=True)  # RECEIVED, PROCESSED, DUPLICATE, ERROR
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WhatsAppPendingConfirmation(Base):
    """Expiring, single-use confirmation authorization token for state-changing operations.
    
    Binds the operation to the merchant, product, proposed values, and record version.
    Prevents confirmation replay, cross-merchant confirmation, and execution after expiration.
    """
    __tablename__ = "whatsapp_pending_confirmations"

    id = Column(String(64), primary_key=True, index=True)  # e.g. waconf_4921
    confirmation_code = Column(String(16), nullable=False, index=True)  # Short 4-digit code e.g. '4921'
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_phone = Column(String(32), nullable=False, index=True)
    operation_type = Column(String(32), nullable=False, index=True)  # PRICE_UPDATE, INVENTORY_UPDATE, OFFER_CREATE, CAMPAIGN_DISPATCH
    product_id = Column(String(64), ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    product_sku = Column(String(64), nullable=True)
    product_name = Column(String(255), nullable=True)
    current_values = Column(JSON, nullable=False, default=dict)  # {"price_paise": 189900, "inventory_quantity": 40}
    proposed_values = Column(JSON, nullable=False, default=dict)  # {"price_paise": 160000}
    reason = Column(Text, nullable=True)
    language = Column(String(8), nullable=False, default="en")
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING, CONFIRMED, CANCELLED, EXPIRED, SUPERSEDED
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)


class WhatsAppOutboundMessage(Base):
    """Audit record of outbound responses dispatched to merchant phone."""
    __tablename__ = "whatsapp_outbound_messages"

    id = Column(String(64), primary_key=True, index=True)  # msg_...
    recipient_phone = Column(String(32), nullable=False, index=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    reply_to_message_id = Column(String(128), nullable=True, index=True)
    message_text = Column(Text, nullable=False)
    delivery_status = Column(String(32), nullable=False, default="SENT", index=True)  # SENT, DELIVERED, READ, FAILED, MOCK_SENT
    meta_response_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
