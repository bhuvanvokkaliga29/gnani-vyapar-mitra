"""Trace Reconstruction Service for Phase 9.4.

Contract: observability-trace/v1
Guarantees:
1. Deterministic reconstruction of the full commercial execution lifecycle:
   9.1 Decision -> 9.2 Execution -> Phase 5 Transaction -> 9.3 Outcome -> 8.1 Evidence -> 8.3 Memory -> 8.4 Model Update.
2. Clear diagnosis of missing stages or where a pipeline stopped.
3. Strict tenant isolation: merchant_id is mandatory.
4. Information hygiene: excludes secret credentials and internal merchant COGS.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from domain.models import (
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    Order,
    Payment,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
    AppliedModelObservationRecord,
    AuditEvent,
)
from services.audit.errors import AuditTenantViolationError

TRACE_SCHEMA_VERSION = "observability-trace/v1"


class TraceStageStatus(str, Enum):
    """Lifecycle stage status for opportunity trace reconstruction."""
    COMPLETED = "COMPLETED"
    STOPPED_AT_DECISION = "STOPPED_AT_DECISION"
    STOPPED_AT_EXECUTION = "STOPPED_AT_EXECUTION"
    STOPPED_AT_TRANSACTION = "STOPPED_AT_TRANSACTION"
    STOPPED_AT_OUTCOME = "STOPPED_AT_OUTCOME"
    STOPPED_AT_FIREWALL = "STOPPED_AT_FIREWALL"
    UNRESOLVED = "UNRESOLVED"


class OpportunityTraceSchema(BaseModel):
    """Authoritative representation of a reconstructed opportunity lifecycle."""
    model_config = ConfigDict(extra="forbid")

    trace_version: str = Field(default=TRACE_SCHEMA_VERSION)
    merchant_id: str
    opportunity_id: str
    request_id: Optional[str] = None
    decision_id: Optional[str] = None
    execution_id: Optional[str] = None
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    outcome_id: Optional[str] = None
    evidence_id: Optional[str] = None
    memory_id: Optional[str] = None
    applied_observation_id: Optional[str] = None
    trace_status: str
    stopped_reason: Optional[str] = None
    stages_present: List[str]
    audit_event_count: int


class TraceReconstructionService:
    """Service that reconstructs and validates the end-to-end trace of an opportunity."""

    @classmethod
    async def reconstruct_opportunity(
        cls,
        db: AsyncSession,
        merchant_id: str,
        opportunity_id: str,
    ) -> OpportunityTraceSchema:
        """Reconstruct the entire lifecycle trace of an opportunity within strict tenant scope."""
        if not merchant_id or not isinstance(merchant_id, str):
            raise AuditTenantViolationError("Merchant ID is mandatory for trace reconstruction.")

        stages_present: List[str] = []
        stopped_reason: Optional[str] = None

        # 1. Phase 9.1 Decision
        stmt_dec = select(CanonicalDecisionRecord).where(
            and_(
                CanonicalDecisionRecord.merchant_id == merchant_id,
                CanonicalDecisionRecord.opportunity_id == opportunity_id,
            )
        )
        dec_rec = (await db.execute(stmt_dec)).scalar_one_or_none()
        decision_id = dec_rec.id if dec_rec else None
        request_id = (dec_rec.decision_envelope_json or {}).get("request_id") if dec_rec else None
        if dec_rec:
            stages_present.append("9.1_DECISION")
        else:
            return OpportunityTraceSchema(
                merchant_id=merchant_id,
                opportunity_id=opportunity_id,
                trace_status=TraceStageStatus.STOPPED_AT_DECISION.value,
                stopped_reason="No canonical decision record found for opportunity.",
                stages_present=stages_present,
                audit_event_count=0,
            )

        # 2. Phase 9.2 Execution
        stmt_exec = select(DecisionExecutionRecord).where(
            and_(
                DecisionExecutionRecord.merchant_id == merchant_id,
                DecisionExecutionRecord.decision_id == decision_id,
            )
        )
        exec_rec = (await db.execute(stmt_exec)).scalar_one_or_none()
        execution_id = exec_rec.id if exec_rec else None
        order_id = exec_rec.order_id if exec_rec else None
        if exec_rec:
            stages_present.append("9.2_EXECUTION")
            if exec_rec.boundary_status != "EXECUTION_COMPLETED":
                stopped_reason = f"Execution boundary status: {exec_rec.boundary_status}"
        else:
            return OpportunityTraceSchema(
                merchant_id=merchant_id,
                opportunity_id=opportunity_id,
                request_id=request_id,
                decision_id=decision_id,
                trace_status=TraceStageStatus.STOPPED_AT_EXECUTION.value,
                stopped_reason="Decision was evaluated but never authorized/executed.",
                stages_present=stages_present,
                audit_event_count=0,
            )

        # 3. Phase 5 Transaction (Order & Payment)
        payment_id = None
        if order_id:
            stmt_order = select(Order).where(Order.id == order_id)
            order_rec = (await db.execute(stmt_order)).scalar_one_or_none()
            if order_rec:
                stages_present.append("PHASE_5_ORDER")
                stmt_pmt = select(Payment).where(Payment.order_id == order_id)
                pmt_rec = (await db.execute(stmt_pmt)).scalars().first()
                if pmt_rec:
                    payment_id = pmt_rec.id
                    stages_present.append("PHASE_5_PAYMENT")

        # 4. Phase 9.3 Outcome Feedback
        stmt_out = select(OutcomeFeedbackRecord).where(
            and_(
                OutcomeFeedbackRecord.merchant_id == merchant_id,
                OutcomeFeedbackRecord.execution_id == execution_id,
            )
        )
        out_rec = (await db.execute(stmt_out)).scalar_one_or_none()
        outcome_id = out_rec.id if out_rec else None
        evidence_id = out_rec.evidence_id if out_rec else None
        memory_id = out_rec.memory_id if out_rec else None

        if out_rec:
            stages_present.append("9.3_OUTCOME")
            if not out_rec.is_terminal:
                stopped_reason = f"Outcome non-terminal: {out_rec.outcome_status}"
            elif not out_rec.learning_eligible:
                stopped_reason = f"Outcome not eligible for learning: {out_rec.rejection_reasons_json}"
        else:
            return OpportunityTraceSchema(
                merchant_id=merchant_id,
                opportunity_id=opportunity_id,
                request_id=request_id,
                decision_id=decision_id,
                execution_id=execution_id,
                order_id=order_id,
                payment_id=payment_id,
                trace_status=TraceStageStatus.STOPPED_AT_TRANSACTION.value,
                stopped_reason="Transaction outcome feedback was never processed.",
                stages_present=stages_present,
                audit_event_count=0,
            )

        # 5. Phase 8.1 Learning Evidence
        if evidence_id:
            stmt_evi = select(LearningEvidenceRecord).where(
                and_(
                    LearningEvidenceRecord.merchant_id == merchant_id,
                    LearningEvidenceRecord.id == evidence_id,
                )
            )
            evi_rec = (await db.execute(stmt_evi)).scalar_one_or_none()
            if evi_rec:
                stages_present.append("8.1_EVIDENCE")

        # 6. Phase 8.3 Policy Memory
        if memory_id:
            stmt_mem = select(PolicyMemoryRecord).where(
                and_(
                    PolicyMemoryRecord.merchant_id == merchant_id,
                    PolicyMemoryRecord.id == memory_id,
                )
            )
            mem_rec = (await db.execute(stmt_mem)).scalar_one_or_none()
            if mem_rec:
                stages_present.append("8.3_MEMORY")

        # 7. Phase 8.4 Model Update Observation
        applied_obs_id = None
        if evidence_id:
            stmt_amo = select(AppliedModelObservationRecord).where(
                and_(
                    AppliedModelObservationRecord.merchant_id == merchant_id,
                    AppliedModelObservationRecord.evidence_id == evidence_id,
                )
            )
            amo_rec = (await db.execute(stmt_amo)).scalar_one_or_none()
            if amo_rec:
                applied_obs_id = amo_rec.id
                stages_present.append("8.4_MODEL_UPDATE")

        # 8. Audit Event Count
        stmt_audit_cnt = select(func.count(AuditEvent.id)).where(
            and_(
                AuditEvent.merchant_id == merchant_id,
                AuditEvent.opportunity_id == opportunity_id,
            )
        )
        audit_cnt = (await db.execute(stmt_audit_cnt)).scalar_one()

        # Determine overall trace status
        if "8.4_MODEL_UPDATE" in stages_present and out_rec.processing_state == "COMPLETED":
            overall_status = TraceStageStatus.COMPLETED.value
        elif not out_rec.learning_eligible:
            overall_status = TraceStageStatus.STOPPED_AT_FIREWALL.value
        elif not out_rec.is_terminal:
            overall_status = TraceStageStatus.UNRESOLVED.value
        else:
            overall_status = TraceStageStatus.STOPPED_AT_OUTCOME.value

        return OpportunityTraceSchema(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            request_id=request_id,
            decision_id=decision_id,
            execution_id=execution_id,
            order_id=order_id,
            payment_id=payment_id,
            outcome_id=outcome_id,
            evidence_id=evidence_id,
            memory_id=memory_id,
            applied_observation_id=applied_obs_id,
            trace_status=overall_status,
            stopped_reason=stopped_reason,
            stages_present=stages_present,
            audit_event_count=audit_cnt,
        )
