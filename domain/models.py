"""SQLAlchemy Relational Database Models for Transaction Substrate & Merchant Commerce Model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
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
    Float,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Index,
    func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# =============================================================================
# PHASE 1: TRANSACTION DOMAIN
# =============================================================================

class Order(Base):
    """Internal Order representation tracking Razorpay order synchronization."""
    __tablename__ = "orders"

    id = Column(String(64), primary_key=True, index=True)
    decision_id = Column(String(64), unique=True, nullable=False, index=True)
    razorpay_order_id = Column(String(64), unique=True, nullable=True, index=True)
    amount_paise = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    receipt = Column(String(40), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="CREATION_PENDING", index=True)
    notes = Column(JSON, nullable=True, default=dict)
    is_simulated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan", lazy="selectin")


class Payment(Base):
    """Individual payment capture or attempt received from Razorpay."""
    __tablename__ = "payments"

    id = Column(String(64), primary_key=True, index=True)  # Razorpay payment ID (pay_...)
    order_id = Column(String(64), ForeignKey("orders.id"), nullable=False, index=True)
    amount_paise = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(32), nullable=False, index=True)  # 'authorized', 'captured', 'failed'
    method = Column(String(32), nullable=True)  # 'card', 'upi', 'netbanking'
    error_code = Column(String(64), nullable=True)
    error_description = Column(Text, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="payments")


class ProcessedWebhookEvent(Base):
    """Idempotency ledger enforcing strict database-level deduplication of webhooks."""
    __tablename__ = "processed_webhook_events"

    event_id = Column(String(128), primary_key=True, index=True)  # From X-Razorpay-Event-Id
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    """Immutable append-only audit trail for all transactional and commerce events.
    
    Contract: audit-event/v1
    Enforces append-only immutability. Updates and deletions are strictly blocked.
    """
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_event_id = Column(String(64), unique=True, index=True, nullable=True)  # aud_...
    merchant_id = Column(String(64), nullable=True, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # 'ORDER', 'PAYMENT', 'MERCHANT', 'DECISION', etc.
    entity_id = Column(String(64), nullable=False, index=True)
    actor = Column(String(64), nullable=False)  # 'APPLICATION', 'POLICY_ENGINE', 'COMMERCE_SERVICE', etc.
    action = Column(String(64), nullable=False, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    opportunity_id = Column(String(128), nullable=True, index=True)
    decision_id = Column(String(64), nullable=True, index=True)
    execution_id = Column(String(64), nullable=True, index=True)
    outcome_id = Column(String(64), nullable=True, index=True)
    evidence_id = Column(String(64), nullable=True, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Immutability enforcement: Block updates and deletions on AuditEvent
from sqlalchemy import event


@event.listens_for(AuditEvent, "before_update")
def receive_audit_before_update(mapper, connection, target):
    from services.audit.errors import AuditImmutabilityViolationError
    raise AuditImmutabilityViolationError(
        f"AuditEvent record '{target.id}' is immutable and append-only. Updates are strictly forbidden."
    )


@event.listens_for(AuditEvent, "before_delete")
def receive_audit_before_delete(mapper, connection, target):
    from services.audit.errors import AuditImmutabilityViolationError
    raise AuditImmutabilityViolationError(
        f"AuditEvent record '{target.id}' is immutable and append-only. Deletions are strictly forbidden."
    )


# =============================================================================
# PHASE 2: MERCHANT COMMERCE DOMAIN
# =============================================================================

class Merchant(Base):
    """Merchant entity operating commercial policies and catalog rules."""
    __tablename__ = "merchants"

    id = Column(String(64), primary_key=True, index=True)  # e.g., 'merch_atlas_travel'
    name = Column(String(255), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)  # 'ACTIVE', 'INACTIVE'

    # Business Objective & Constraints
    business_objective = Column(String(64), nullable=False, default="BALANCE_REVENUE_AND_MARGIN")
    minimum_margin_percent = Column(Numeric(5, 2), nullable=False, default=25.00)
    maximum_discount_percent = Column(Numeric(5, 2), nullable=False, default=8.00)
    target_aov_paise = Column(BigInteger, nullable=False, default=400000)  # e.g. ₹4,000

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    products = relationship("Product", back_populates="merchant", cascade="all, delete-orphan", lazy="selectin")
    priorities = relationship("MerchantPriority", back_populates="merchant", cascade="all, delete-orphan", uselist=False, lazy="selectin")


class Product(Base):
    """Merchant catalog item with pricing, COGS, and real-time inventory."""
    __tablename__ = "products"

    id = Column(String(64), primary_key=True, index=True)  # e.g., 'prod_travel_backpack'
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=False, index=True)

    # Unit Economics (Integer Paise)
    price_paise = Column(BigInteger, nullable=False)  # Selling price
    cost_paise = Column(BigInteger, nullable=False)   # Unit COGS
    currency = Column(String(3), nullable=False, default="INR")

    # Inventory State
    inventory_quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    attributes = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="products")

    __table_args__ = (
        UniqueConstraint("merchant_id", "sku", name="uq_products_merchant_sku"),
        CheckConstraint("price_paise > 0", name="chk_price_positive"),
        CheckConstraint("cost_paise >= 0", name="chk_cost_non_negative"),
        CheckConstraint("inventory_quantity >= 0", name="chk_inventory_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="chk_reserved_non_negative"),
    )


class ProductRelationship(Base):
    """Structured product relationships (complementary, substitute, bundle components)."""
    __tablename__ = "product_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_product_id = Column(String(64), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    related_product_id = Column(String(64), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationship classification
    relationship_type = Column(String(32), nullable=False, index=True)  # COMPLEMENTARY, SUBSTITUTE, BUNDLE_COMPONENT, UPSELL, CROSS_SELL
    affinity_score = Column(Numeric(3, 2), nullable=False, default=0.50)  # 0.00 to 1.00
    source = Column(String(32), nullable=False, default="merchant_defined")  # 'merchant_defined', 'system_inferred'
    confidence = Column(Numeric(3, 2), nullable=False, default=1.00)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    primary_product = relationship("Product", foreign_keys=[primary_product_id], lazy="selectin")
    related_product = relationship("Product", foreign_keys=[related_product_id], lazy="selectin")

    __table_args__ = (
        UniqueConstraint("primary_product_id", "related_product_id", "relationship_type", name="uq_product_relationship"),
        CheckConstraint("primary_product_id != related_product_id", name="chk_no_self_relationship"),
    )


class MerchantPriority(Base):
    """Merchant product, category, and inventory clearance preferences."""
    __tablename__ = "merchant_priorities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    priority_product_ids = Column(JSON, nullable=False, default=list)
    priority_categories = Column(JSON, nullable=False, default=list)
    clearance_product_ids = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="priorities")


# =============================================================================
# PHASE 5: DETERMINISTIC EXECUTION DOMAIN
# =============================================================================

class ExecutionRecord(Base):
    """Authoritative audit record for a commercial policy execution authorization."""
    __tablename__ = "execution_records"

    id = Column(String(64), primary_key=True, index=True)  # e.g. exec_...
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    proposal_id = Column(String(64), nullable=False, index=True)
    candidate_id = Column(String(64), nullable=False)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String(64), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    razorpay_order_id = Column(String(64), nullable=True, index=True)
    receipt = Column(String(40), nullable=False, index=True)

    # Authorized Financial Figures (Minor Units)
    authorized_amount_paise = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(32), nullable=False, default="REVALIDATING", index=True)

    # Audit & Provenance Payloads
    rejection_reasons = Column(JSON, nullable=False, default=list)
    recalculated_economics = Column(JSON, nullable=True)
    audit_metadata = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    merchant = relationship("Merchant", lazy="selectin")
    order = relationship("Order", lazy="selectin")


# =============================================================================
# PHASE 7: CONTROLLED POLICY EXPERIMENTS DOMAIN
# =============================================================================

class ExperimentRecord(Base):
    """Authoritative persistent record for a controlled policy experiment."""
    __tablename__ = "experiments"

    id = Column(String(64), primary_key=True, index=True)  # exp_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    control_policy_id = Column(String(64), nullable=False)
    treatment_policy_id = Column(String(64), nullable=False)
    control_proposal_snapshot = Column(JSON, nullable=False)
    treatment_proposal_snapshot = Column(JSON, nullable=False)
    hypothesis = Column(JSON, nullable=False)
    guardrails = Column(JSON, nullable=False, default=list)
    primary_metric = Column(String(64), nullable=False, default="EXPECTED_CONTRIBUTION_PER_SHOPPER")
    secondary_metrics = Column(JSON, nullable=False, default=list)
    randomization_seed = Column(Integer, nullable=False, default=42)
    assignment_strategy = Column(String(32), nullable=False, default="DETERMINISTIC_HASH")
    population_scenarios = Column(JSON, nullable=False, default=list)
    policy_diff = Column(JSON, nullable=True)
    sample_size_target = Column(Integer, nullable=False, default=50)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    merchant = relationship("Merchant", lazy="selectin")
    observations = relationship("ObservationRecord", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin")


class ObservationRecord(Base):
    """Authoritative audit record of an experimental observation (simulated or test-mode)."""
    __tablename__ = "observations"

    id = Column(String(64), primary_key=True, index=True)  # obs_...
    experiment_id = Column(String(64), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    variant = Column(String(16), nullable=False, index=True)  # CONTROL, TREATMENT
    outcome_type = Column(String(32), nullable=False, default="SIMULATED")  # SIMULATED, TEST_MODE_OBSERVED
    buyer_selection_result_id = Column(String(64), nullable=True)
    selected_offer_id = Column(String(64), nullable=True)
    is_selected = Column(Boolean, nullable=False, default=False)
    execution_id = Column(String(64), ForeignKey("execution_records.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id = Column(String(64), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    razorpay_order_id = Column(String(64), nullable=True)
    payment_outcome = Column(String(32), nullable=True)
    revenue_paise = Column(BigInteger, nullable=False, default=0)
    contribution_paise = Column(BigInteger, nullable=False, default=0)
    margin_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    guardrail_violations = Column(JSON, nullable=False, default=list)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    experiment = relationship("ExperimentRecord", back_populates="observations")


class LearningEvidenceRecord(Base):
    """Authoritative persistent record of policy learning evidence (merchant-learning/v1).
    
    Serves as the strict firewall between experimentation and future policy learning.
    """
    __tablename__ = "learning_evidence"

    id = Column(String(64), primary_key=True, index=True)  # evi_...
    evidence_version = Column(String(32), nullable=False, default="merchant-learning/v1")
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_id = Column(String(64), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_observation_id = Column(String(64), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    policy_id = Column(String(64), nullable=False, index=True)
    policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    variant = Column(String(16), nullable=False)  # CONTROL, TREATMENT
    buyer_context_key = Column(String(128), nullable=False, index=True)
    buyer_intent_version = Column(String(32), nullable=False, default="buyer-intent/v1")
    buyer_selection_result_id = Column(String(64), nullable=True)
    simulation_version = Column(String(32), nullable=True, default="buyer-selection/v1")
    execution_id = Column(String(64), nullable=True)
    provider_order_id = Column(String(64), nullable=True)
    verified_payment_id = Column(String(64), nullable=True)
    source = Column(String(32), nullable=False)  # SIMULATED, TEST_MODE_OBSERVED
    outcome_type = Column(String(32), nullable=False)
    sample_size = Column(Integer, nullable=False, default=1)
    is_selected = Column(Boolean, nullable=False, default=False)
    expected_revenue_paise = Column(BigInteger, nullable=False, default=0)
    expected_contribution_paise = Column(BigInteger, nullable=False, default=0)
    observed_revenue_paise = Column(BigInteger, nullable=True)
    observed_contribution_paise = Column(BigInteger, nullable=True)
    margin_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    guardrail_results = Column(JSON, nullable=False, default=list)
    evidence_status = Column(String(32), nullable=False)  # VALID, INSUFFICIENT_SAMPLE, INCONCLUSIVE, GUARDRAIL_FAILURE, INVALID
    lifecycle_state = Column(String(32), nullable=False, default="CAPTURED")
    learning_eligible = Column(Boolean, nullable=False, default=False, index=True)
    eligibility_reasons = Column(JSON, nullable=False, default=list)
    aggregation_key = Column(String(256), nullable=False, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PolicyMemoryRecord(Base):
    """Authoritative persistent record of historical policy memory (merchant-memory/v1).
    
    Serves as the immutable historical record of verified economic outcomes,
    buyer context, and policy provenance.
    """
    __tablename__ = "policy_memory"

    id = Column(String(64), primary_key=True, index=True)  # mem_...
    memory_version = Column(String(32), nullable=False, default="merchant-memory/v1")
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(128), nullable=False, index=True)
    buyer_context_key = Column(String(128), nullable=False, index=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    policy_id = Column(String(64), nullable=False, index=True)
    policy_version = Column(String(32), nullable=False, default="merchant-policy/v1", index=True)
    experiment_id = Column(String(64), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_version = Column(String(32), nullable=False, default="policy-experiment/v1")
    variant = Column(String(16), nullable=False)  # CONTROL, TREATMENT
    evidence_id = Column(String(64), ForeignKey("learning_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_source = Column(String(32), nullable=False)  # SIMULATED, TEST_MODE_OBSERVED
    outcome_type = Column(String(32), nullable=False)
    learning_eligible = Column(Boolean, nullable=False, default=False, index=True)
    reward_id = Column(String(64), nullable=False, index=True)
    reward_version = Column(String(32), nullable=False, default="merchant-reward/v1")
    formula_version = Column(String(32), nullable=False, default="contribution-formula/v1")
    reward_state = Column(String(32), nullable=False)
    is_admissible = Column(Boolean, nullable=False, default=False)
    is_safety_violation = Column(Boolean, nullable=False, default=False)
    realized_revenue_paise = Column(BigInteger, nullable=False, default=0)
    realized_cogs_paise = Column(BigInteger, nullable=False, default=0)
    realized_discount_paise = Column(BigInteger, nullable=False, default=0)
    reward_contribution_paise = Column(BigInteger, nullable=False, default=0)
    margin_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    superseded_by = Column(String(64), nullable=True, index=True)
    supersedes = Column(String(64), nullable=True, index=True)
    correction_reason = Column(String(128), nullable=True)
    reconciliation_ref = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    persisted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_policy_memory_merchant_policy", "merchant_id", "policy_id"),
        Index("ix_policy_memory_merchant_policy_ver", "merchant_id", "policy_id", "policy_version"),
        Index("ix_policy_memory_merchant_context", "merchant_id", "buyer_context_key"),
        Index("ix_policy_memory_merchant_pol_ctx", "merchant_id", "policy_id", "buyer_context_key"),
        Index("ix_policy_memory_merchant_exp", "merchant_id", "experiment_id"),
        Index("ix_policy_memory_merchant_obs_time", "merchant_id", "observed_at"),
        Index("ix_policy_memory_merchant_opp_current", "merchant_id", "opportunity_id", "is_current"),
    )


class PolicyLearningModelState(Base):
    """Authoritative persistent record of a merchant-specific contextual learning model state.
    
    Conforms to contract learning-model/v1.
    Maintains sufficient statistics (A matrix, b vector, and derived theta weights)
    for Contextual Linear Upper Confidence Bound (LinUCB) value estimation.
    Uses optimistic locking via the 'version' column to prevent concurrent lost updates.
    """
    __tablename__ = "policy_learning_model_states"

    id = Column(String(64), primary_key=True, index=True)  # lms_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    model_version = Column(String(32), nullable=False, default="learning-model/v1")
    algorithm_version = Column(String(32), nullable=False, default="learning-algorithm/v1")
    feature_version = Column(String(32), nullable=False, default="feature-schema/v1")
    reward_version = Column(String(32), nullable=False, default="merchant-reward/v1")
    formula_version = Column(String(32), nullable=False, default="contribution-formula/v1")
    dimension = Column(Integer, nullable=False, default=19)
    lambda_reg = Column(Numeric(8, 4), nullable=False, default=1.0)
    alpha_paise = Column(BigInteger, nullable=False, default=10000)
    observation_count = Column(Integer, nullable=False, default=0)
    matrix_a_json = Column(JSON, nullable=False)
    vector_b_json = Column(JSON, nullable=False)
    theta_json = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AppliedModelObservationRecord(Base):
    """Authoritative ledger of observations applied to merchant Contextual LinUCB models.

    Contract: learning-model/v1
    Enforces atomic, durable deduplication at the model update boundary.
    Guarantees that a single learning observation (evidence_id) can NEVER
    update a merchant's model more than once under crashes, retries, or concurrency.
    """
    __tablename__ = "applied_model_observations"

    id = Column(String(64), primary_key=True, index=True)  # amo_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(String(64), ForeignKey("learning_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version = Column(Integer, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "evidence_id", name="uq_applied_obs_merchant_evidence"),
        Index("ix_applied_obs_merchant_evidence", "merchant_id", "evidence_id"),
    )


class PolicySelectionRecord(Base):
    """Authoritative persistent record of a deterministic learned candidate selection.
    
    Conforms to contract policy-selection/v1.
    Persists the decision snapshot, full ranked candidate slate, predicted contributions,
    diagnostic uncertainties, baseline comparison, and selection reason.
    Provides complete auditability and idempotency for Phase 8.5.
    """
    __tablename__ = "policy_selection_records"

    id = Column(String(64), primary_key=True, index=True)  # sel_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(128), nullable=False, index=True)
    buyer_context_key = Column(String(128), nullable=False, index=True)
    selected_policy_id = Column(String(64), nullable=False)
    selected_policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    baseline_policy_id = Column(String(64), nullable=False)
    selected_predicted_contribution_paise = Column(BigInteger, nullable=False)
    selected_uncertainty = Column(Numeric(10, 4), nullable=False)
    baseline_predicted_contribution_paise = Column(BigInteger, nullable=False)
    ranked_candidates_json = Column(JSON, nullable=False)
    model_version = Column(String(32), nullable=False, default="learning-model/v1")
    feature_version = Column(String(32), nullable=False, default="feature-schema/v1")
    selection_version = Column(String(32), nullable=False, default="policy-selection/v1")
    selection_reason = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_policy_selection_merchant_opp", "merchant_id", "opportunity_id"),
    )


class PolicySafetyRecord(Base):
    """Authoritative persistent record of a deterministic safety and admissibility check.
    
    Conforms to contract policy-safety/v1.
    Persists validation outcome, failure codes, recomputed economics snapshot,
    merchant context reference, and timestamp.
    Provides complete auditability and idempotency for Phase 8.6.
    """
    __tablename__ = "policy_safety_records"

    id = Column(String(64), primary_key=True, index=True)  # safe_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(128), nullable=False, index=True)
    buyer_context_key = Column(String(128), nullable=False)
    policy_id = Column(String(64), nullable=False)
    policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    selection_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False)  # ADMISSIBLE, REJECTED
    failure_codes_json = Column(JSON, nullable=False, default=list)
    recalculated_economics_json = Column(JSON, nullable=True)
    validation_reason = Column(String(128), nullable=False)
    merchant_context_version = Column(String(32), nullable=True)
    safety_version = Column(String(32), nullable=False, default="policy-safety/v1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_policy_safety_merchant_opp", "merchant_id", "opportunity_id", "policy_id"),
    )


class MerchantExplorationState(Base):
    """Authoritative operational state tracking exploration budget and exposure for a merchant.
    
    Conforms to policy-exploration/v1.
    Strictly isolated per merchant tenant.
    Tracks opportunities used, cumulative economic exposure, per-policy exposure,
    per-context exposure, and consecutive exploration count.
    """
    __tablename__ = "merchant_exploration_states"

    id = Column(String(64), primary_key=True, index=True)  # exp_state_{merchant_id}_{window_id}
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    window_id = Column(String(64), nullable=False, default="window_default")
    opportunities_used = Column(Integer, nullable=False, default=0)
    exposure_paise_used = Column(BigInteger, nullable=False, default=0)
    consecutive_explorations = Column(Integer, nullable=False, default=0)
    policy_counts_json = Column(JSON, nullable=False, default=dict)
    context_counts_json = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_merchant_exploration_state_mw", "merchant_id", "window_id", unique=True),
    )


class ExplorationDecisionRecord(Base):
    """Authoritative persistent record of a deterministic exploration vs exploitation decision.
    
    Conforms to contract policy-exploration/v1.
    Persists chosen mode (EXPLOIT or EXPLORE), exploit policy ID, selected policy ID,
    predicted contribution, uncertainty, UCB score, reason code, safety check reference,
    and budget snapshots.
    Provides complete auditability, reproducibility, and idempotency for Phase 8.7.
    """
    __tablename__ = "exploration_decision_records"

    id = Column(String(64), primary_key=True, index=True)  # exp_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(128), nullable=False, index=True)
    buyer_context_key = Column(String(128), nullable=False)
    mode = Column(String(16), nullable=False)  # EXPLOIT, EXPLORE
    exploit_policy_id = Column(String(64), nullable=False)
    exploit_policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    selected_policy_id = Column(String(64), nullable=False)
    selected_policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    predicted_contribution_paise = Column(BigInteger, nullable=False)
    uncertainty = Column(Float, nullable=False)
    ucb_score_paise = Column(BigInteger, nullable=False)
    exposure_paise = Column(BigInteger, nullable=False, default=0)
    reason_code = Column(String(64), nullable=False)
    safety_check_id = Column(String(64), nullable=True)
    budget_state_json = Column(JSON, nullable=False, default=dict)
    policy_exposure_state_json = Column(JSON, nullable=False, default=dict)
    context_exposure_state_json = Column(JSON, nullable=False, default=dict)
    model_version = Column(String(32), nullable=False, default="learning-model/v1")
    feature_version = Column(String(32), nullable=False, default="feature-schema/v1")
    selection_version = Column(String(32), nullable=False, default="policy-selection/v1")
    exploration_version = Column(String(32), nullable=False, default="policy-exploration/v1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_policy_exploration_merchant_opp", "merchant_id", "opportunity_id"),
    )


# =============================================================================
# PHASE 8.8: POLICY LIFECYCLE & PROMOTION MANAGEMENT
# =============================================================================

class MerchantActivePolicy(Base):
    """Authoritative pointer to the currently active commercial policy version for a merchant.
    
    Inviolable Invariant: Exactly one active policy version per merchant at any time.
    Enforced via merchant_id as the primary key.
    """
    __tablename__ = "merchant_active_policies"

    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), primary_key=True)
    policy_id = Column(String(64), nullable=False)
    policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    activated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    promotion_id = Column(String(64), nullable=False)


class MerchantPolicyVersionRecord(Base):
    """Immutable persistent record of a merchant commercial policy version.
    
    Conforms to contract policy-lifecycle/v1.
    Lifecycle states: CANDIDATE, ELIGIBLE_FOR_PROMOTION, ACTIVE, RETIRED, ROLLED_BACK.
    """
    __tablename__ = "merchant_policy_version_records"

    id = Column(String(128), primary_key=True, index=True)  # pver_{merchant_id}_{policy_id}_{version}
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(String(64), nullable=False, index=True)
    policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    lifecycle_status = Column(String(32), nullable=False, default="CANDIDATE", index=True)
    strategy_type = Column(String(32), nullable=False)
    product_ids_json = Column(JSON, nullable=False, default=list)
    incentive_json = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    provenance_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "policy_id", "policy_version", name="uq_merchant_policy_version"),
        Index("ix_merchant_policy_version_status", "merchant_id", "lifecycle_status"),
    )


class PolicyLifecycleAuditRecord(Base):
    """Immutable audit trail for all policy lifecycle transitions (promotion, retirement, rollback).
    
    Conforms to contract policy-lifecycle/v1.
    Preserves complete provenance, evidence references, and Phase 8.6 safety check IDs.
    """
    __tablename__ = "policy_lifecycle_audit_records"

    id = Column(String(64), primary_key=True, index=True)  # lcyc_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    transition_type = Column(String(32), nullable=False)  # PROMOTION, ROLLBACK
    candidate_policy_id = Column(String(64), nullable=False)
    candidate_policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    previous_active_policy_id = Column(String(64), nullable=True)
    previous_active_policy_version = Column(String(32), nullable=True)
    resulting_active_policy_id = Column(String(64), nullable=True)
    resulting_active_policy_version = Column(String(32), nullable=True)
    promotion_status = Column(String(32), nullable=False)  # PROMOTED, NOT_ELIGIBLE, INSUFFICIENT_EVIDENCE, SAFETY_REJECTED, CONFLICT, ROLLED_BACK
    eligibility_status = Column(String(64), nullable=False)
    failure_codes_json = Column(JSON, nullable=False, default=list)
    evidence_type = Column(String(32), nullable=True)  # CONTROLLED_EXPERIMENT, OBSERVATIONAL_HISTORY
    evidence_references_json = Column(JSON, nullable=False, default=dict)
    safety_check_id = Column(String(64), nullable=True)
    promotion_config_version = Column(String(32), nullable=False, default="promotion-policy/v1")
    lifecycle_version = Column(String(32), nullable=False, default="policy-lifecycle/v1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_lifecycle_audit_merchant_trans", "merchant_id", "transition_type"),
    )


# =============================================================================
# PHASE 8.9: CLOSED-LOOP LEARNING EVALUATION DOMAIN
# =============================================================================

class ClosedLoopEvaluationRecord(Base):
    """Authoritative persistent record of a closed-loop learning evaluation run.
    
    Conforms to contract closed-loop-evaluation/v1.
    Preserves immutable evaluation definition, baseline, training/holdout metrics,
    learning curves, diagnostics, and deterministic audit trail.
    """
    __tablename__ = "closed_loop_evaluations"

    id = Column(String(64), primary_key=True, index=True)  # eval_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(32), nullable=False)  # SIMULATION, CONTROLLED_TEST_MODE, REPLAY
    status = Column(String(32), nullable=False, default="RUNNING", index=True)  # RUNNING, COMPLETED, FAILED
    overall_outcome = Column(String(32), nullable=False)  # PASS, FAIL, INCONCLUSIVE, INSUFFICIENT_EVIDENCE
    dataset_id = Column(String(128), nullable=False)
    baseline_definition_json = Column(JSON, nullable=False, default=dict)
    training_definition_json = Column(JSON, nullable=False, default=dict)
    evaluation_definition_json = Column(JSON, nullable=False, default=dict)
    holdout_definition_json = Column(JSON, nullable=False, default=dict)
    config_json = Column(JSON, nullable=False, default=dict)
    seed = Column(Integer, nullable=False, default=42)
    summary_metrics_json = Column(JSON, nullable=False, default=dict)
    learning_curve_json = Column(JSON, nullable=False, default=list)
    holdout_metrics_json = Column(JSON, nullable=False, default=dict)
    diagnostics_json = Column(JSON, nullable=False, default=dict)
    warnings_json = Column(JSON, nullable=False, default=list)
    failure_reasons_json = Column(JSON, nullable=False, default=list)
    contract_versions_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_closed_loop_eval_merchant_mode", "merchant_id", "mode"),
    )


class CanonicalDecisionRecord(Base):
    """Authoritative audit record of a canonical decision executed by Phase 9.1 Decision Runtime.

    Contract: canonical-decision/v1
    Preserves immutable decision envelope, selected policy, predicted scores,
    exploration vs exploit choice, and point-in-time safety verification.
    """
    __tablename__ = "canonical_decisions"

    id = Column(String(64), primary_key=True, index=True)  # dec_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    decision_version = Column(String(64), nullable=False, default="canonical-decision/v1")
    buyer_context_key = Column(String(255), nullable=False)
    decision_mode = Column(String(32), nullable=False)  # EXPLOIT, EXPLORE
    decision_reason = Column(String(128), nullable=False)
    selected_policy_id = Column(String(64), nullable=False)
    selected_strategy_type = Column(String(64), nullable=False)
    proposed_price_paise = Column(Integer, nullable=False, default=0)
    predicted_contribution_paise = Column(Integer, nullable=False, default=0)
    decision_envelope_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_canonical_decisions_merchant_opp", "merchant_id", "opportunity_id", unique=True),
    )


class DecisionExecutionRecord(Base):
    """Authoritative audit record of an execution boundary traversal.

    Contract: execution-boundary/v1
    Links Phase 9.1 canonical decision to Phase 5 transactional execution record,
    tracking server-issued single-use authorization, fresh safety verification,
    and execution boundary status.
    """
    __tablename__ = "decision_executions"

    id = Column(String(64), primary_key=True, index=True)  # dexec_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    decision_id = Column(String(64), ForeignKey("canonical_decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(128), nullable=False, index=True)
    authorization_id = Column(String(64), unique=True, nullable=False, index=True)  # eauth_...
    policy_id = Column(String(64), nullable=False)
    policy_version = Column(String(32), nullable=False, default="merchant-policy/v1")
    state_fingerprint = Column(String(64), nullable=False)
    safety_check_id = Column(String(64), nullable=True)
    boundary_status = Column(String(32), nullable=False, index=True)
    execution_record_id = Column(String(64), ForeignKey("execution_records.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id = Column(String(64), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    razorpay_order_id = Column(String(64), nullable=True, index=True)
    authorized_amount_paise = Column(BigInteger, nullable=True)
    currency = Column(String(3), nullable=False, default="INR")
    rejection_reasons_json = Column(JSON, nullable=False, default=list)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_decision_executions_merchant_decision", "merchant_id", "decision_id"),
    )


# =============================================================================
# PHASE 9.3: OUTCOME, FEEDBACK & RECOVERY LOOP
# =============================================================================

class OutcomeFeedbackRecord(Base):
    """Authoritative persistent record for outcome resolution, feedback, and closed-loop learning.

    Contract: outcome-feedback/v1
    Links Phase 9.2 boundary execution and Phase 5 authoritative transaction state
    to Phase 8.1 evidence, Phase 8.2 reward, Phase 8.3 memory, and Phase 8.4 model.
    Guarantees at-least-once processing with idempotent exactly-once learning effect.
    """
    __tablename__ = "outcome_feedbacks"

    id = Column(String(64), primary_key=True, index=True)  # out_...
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(128), nullable=False, index=True)
    decision_id = Column(String(64), ForeignKey("canonical_decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id = Column(String(64), ForeignKey("decision_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String(64), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    razorpay_order_id = Column(String(64), nullable=True, index=True)
    razorpay_payment_id = Column(String(64), nullable=True, index=True)
    feedback_version = Column(String(32), nullable=False, default="outcome-feedback/v1")
    transaction_state = Column(String(32), nullable=False)
    outcome_status = Column(String(32), nullable=False, index=True)
    processing_state = Column(String(32), nullable=False, default="RECEIVED", index=True)
    is_terminal = Column(Boolean, nullable=False, default=False, index=True)
    learning_eligible = Column(Boolean, nullable=False, default=False, index=True)
    evidence_id = Column(String(64), nullable=True, index=True)
    memory_id = Column(String(64), nullable=True, index=True)
    model_updated = Column(Boolean, nullable=False, default=False, index=True)
    realized_revenue_paise = Column(BigInteger, nullable=True)
    realized_cogs_paise = Column(BigInteger, nullable=True)
    reward_contribution_paise = Column(BigInteger, nullable=True)
    rejection_reasons_json = Column(JSON, nullable=False, default=list)
    audit_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "execution_id", name="uq_outcome_merchant_execution"),
        Index("ix_outcome_feedbacks_merchant_decision", "merchant_id", "decision_id"),
        Index("ix_outcome_feedbacks_merchant_status", "merchant_id", "outcome_status"),
    )


# Stage E: Persistent Conversation Memory & Action Governance Models
from domain.session_models import (
    VoiceConversationSession,
    VoiceConversationTurn,
    DoctorActionProposal
)







