"""SQLAlchemy Domain Models for Persistent Conversation Sessions & Action Governance (Stage E).

Contract: session-governance/v1
Encompasses:
1. VoiceConversationSession - Tenant-isolated multi-session container with rolling context summaries.
2. VoiceConversationTurn - Immutable, audit-grade conversation turn history with tool traces.
3. DoctorActionProposal - Governed lifecycle (PROPOSED -> VALIDATED -> WAITING_FOR_APPROVAL -> APPROVED -> EXECUTED).
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
    Index,
    func
)
from sqlalchemy.orm import relationship

from domain.models import Base


class VoiceConversationSession(Base):
    """Merchant-scoped voice and text conversation session."""
    __tablename__ = "voice_conversation_sessions"

    id = Column(String(64), primary_key=True, index=True)  # vcs_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Voice Advisory Session")
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)  # ACTIVE, ARCHIVED, EXPIRED
    language = Column(String(16), nullable=False, default="kn")  # kn, hi, en

    # Rolling context summary of earlier conversation turns
    context_summary = Column(Text, nullable=True)

    # Recently focused commercial entity (for conversational follow-up resolution)
    focused_entity_type = Column(String(32), nullable=True)  # PRODUCT, CATEGORY, ORDER, CHANNEL
    focused_entity_id = Column(String(64), nullable=True)
    focused_entity_name = Column(String(255), nullable=True)
    focused_entity_sku = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    turns = relationship(
        "VoiceConversationTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="VoiceConversationTurn.turn_index",
        lazy="selectin"
    )
    action_proposals = relationship(
        "DoctorActionProposal",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_vcs_merchant_status", "merchant_id", "status"),
        Index("ix_vcs_merchant_last_activity", "merchant_id", "last_activity_at"),
    )


class VoiceConversationTurn(Base):
    """Single conversational turn in a session (user, assistant, tool, or system)."""
    __tablename__ = "voice_conversation_turns"

    id = Column(String(64), primary_key=True, index=True)  # trn_...
    session_id = Column(String(64), ForeignKey("voice_conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False, default=0)
    role = Column(String(32), nullable=False)  # user, assistant, system, tool

    content = Column(Text, nullable=False)
    spoken_content = Column(Text, nullable=True)
    is_interrupted = Column(Boolean, nullable=False, default=False)

    # Structured tool invocation and data snapshot
    tool_calls_json = Column(JSON, nullable=False, default=list)
    tool_results_json = Column(JSON, nullable=False, default=dict)
    metrics_snapshot_json = Column(JSON, nullable=False, default=dict)
    referenced_entities_json = Column(JSON, nullable=False, default=list)
    token_usage_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("VoiceConversationSession", back_populates="turns")

    __table_args__ = (
        Index("ix_trn_session_index", "session_id", "turn_index"),
        Index("ix_trn_merchant_session", "merchant_id", "session_id"),
    )


class DoctorActionProposal(Base):
    """Governed commercial action proposal requiring explicit merchant sign-off."""
    __tablename__ = "doctor_action_proposals"

    id = Column(String(64), primary_key=True, index=True)  # actprop_...
    session_id = Column(String(64), ForeignKey("voice_conversation_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)  # PRICE_CHANGE, CLEARANCE_BUNDLE, STOCK_REORDER, CHANNEL_SHIFT
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Lifecycle: PROPOSED -> VALIDATED -> WAITING_FOR_APPROVAL -> APPROVED -> EXECUTED
    # Fallbacks: REJECTED, EXPIRED, FAILED, CANCELLED
    status = Column(String(32), nullable=False, default="PROPOSED", index=True)

    # Parameters and Financial Auditing
    parameters = Column(JSON, nullable=False, default=dict)
    financial_impact = Column(JSON, nullable=False, default=dict)
    margin_floor_compliant = Column(Boolean, nullable=False, default=True)
    margin_percent = Column(Numeric(5, 2), nullable=True)
    requires_approval = Column(Boolean, nullable=False, default=True)

    # Governance & Sign-off Details
    approval_actor = Column(String(64), nullable=True)  # e.g., 'MERCHANT_OWNER'
    rejection_reason = Column(Text, nullable=True)
    execution_result = Column(JSON, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("VoiceConversationSession", back_populates="action_proposals")

    __table_args__ = (
        Index("ix_actprop_merchant_status", "merchant_id", "status"),
        Index("ix_actprop_merchant_type", "merchant_id", "action_type"),
    )

