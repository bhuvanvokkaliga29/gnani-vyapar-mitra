"""Audit Service implementing immutable append-only persistence and tenant-isolated querying.

Contract: audit-event/v1
Guarantees:
1. Append-only persistence.
2. Tenant-scoped query isolation (merchant_id is strictly mandatory).
3. Automatic correlation enrichment from async contextvars.
4. Information hygiene enforcement on audit payloads.
"""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from domain.models import AuditEvent
from services.audit.schemas import (
    AUDIT_SCHEMA_VERSION,
    AuditEventRecordSchema,
    AuditQueryResponse,
)
from services.audit.errors import (
    AuditTenantViolationError,
    AuditEventNotFoundError,
)
from services.observability.correlation import get_correlation_context
from apps.api.core.logging import sanitize_value


class AuditService:
    """Service governing immutable domain audit trails for Phase 9.4."""

    @classmethod
    async def record_event(
        cls,
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "APPLICATION",
        merchant_id: Optional[str] = None,
        request_id: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Durable, append-only recording of a material domain or security audit event."""
        # 1. Enrich from async correlation context if not explicitly passed
        ctx = get_correlation_context()
        eff_merchant_id = merchant_id or ctx.get("merchant_id")
        eff_request_id = request_id or ctx.get("request_id")
        eff_opp_id = opportunity_id or ctx.get("opportunity_id")
        eff_dec_id = decision_id or ctx.get("decision_id")
        eff_exec_id = execution_id or ctx.get("execution_id")

        # 2. Enforce Information Hygiene on payload
        safe_payload = sanitize_value(payload or {})

        # 3. Create Audit Record
        aud_id = f"aud_{uuid.uuid4().hex[:16]}"
        event_rec = AuditEvent(
            audit_event_id=aud_id,
            merchant_id=eff_merchant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            action=action,
            request_id=eff_request_id,
            opportunity_id=eff_opp_id,
            decision_id=eff_dec_id,
            execution_id=eff_exec_id,
            outcome_id=outcome_id,
            evidence_id=evidence_id,
            payload=safe_payload,
        )
        db.add(event_rec)
        await db.flush()
        return event_rec

    @classmethod
    async def query_events(
        cls,
        db: AsyncSession,
        merchant_id: str,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditQueryResponse:
        """Tenant-scoped query for audit history.
        
        Strictly requires merchant_id. Cross-tenant queries are rejected.
        """
        if not merchant_id or not isinstance(merchant_id, str):
            raise AuditTenantViolationError("Merchant ID is mandatory for tenant-scoped audit queries.")

        conditions = [AuditEvent.merchant_id == merchant_id]
        if entity_type:
            conditions.append(AuditEvent.entity_type == entity_type)
        if action:
            conditions.append(AuditEvent.action == action)
        if opportunity_id:
            conditions.append(AuditEvent.opportunity_id == opportunity_id)
        if decision_id:
            conditions.append(AuditEvent.decision_id == decision_id)
        if execution_id:
            conditions.append(AuditEvent.execution_id == execution_id)

        # Count total matching
        count_stmt = select(func.count(AuditEvent.id)).where(and_(*conditions))
        total_count = (await db.execute(count_stmt)).scalar_one()

        # Query events
        stmt = (
            select(AuditEvent)
            .where(and_(*conditions))
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(min(limit, 100))
        )
        res = await db.execute(stmt)
        records = res.scalars().all()

        events_schema = [
            AuditEventRecordSchema(
                audit_event_id=rec.audit_event_id or f"aud_legacy_{rec.id}",
                merchant_id=rec.merchant_id,
                entity_type=rec.entity_type,
                entity_id=rec.entity_id,
                actor=rec.actor,
                action=rec.action,
                request_id=rec.request_id,
                opportunity_id=rec.opportunity_id,
                decision_id=rec.decision_id,
                execution_id=rec.execution_id,
                outcome_id=rec.outcome_id,
                evidence_id=rec.evidence_id,
                payload=rec.payload or {},
                created_at=rec.created_at,
                audit_version=AUDIT_SCHEMA_VERSION,
            )
            for rec in records
        ]

        return AuditQueryResponse(
            merchant_id=merchant_id,
            total_count=total_count,
            events=events_schema,
            audit_version=AUDIT_SCHEMA_VERSION,
        )

    @classmethod
    async def get_event_by_id(
        cls,
        db: AsyncSession,
        audit_event_id: str,
        merchant_id: str,
    ) -> AuditEventRecordSchema:
        """Fetch a single audit event within strict tenant boundaries."""
        if not merchant_id:
            raise AuditTenantViolationError("Merchant ID is mandatory.")

        stmt = select(AuditEvent).where(
            and_(
                AuditEvent.audit_event_id == audit_event_id,
                AuditEvent.merchant_id == merchant_id,
            )
        )
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if not rec:
            raise AuditEventNotFoundError(
                f"AuditEvent '{audit_event_id}' not found for merchant '{merchant_id}'."
            )

        return AuditEventRecordSchema(
            audit_event_id=rec.audit_event_id or f"aud_legacy_{rec.id}",
            merchant_id=rec.merchant_id,
            entity_type=rec.entity_type,
            entity_id=rec.entity_id,
            actor=rec.actor,
            action=rec.action,
            request_id=rec.request_id,
            opportunity_id=rec.opportunity_id,
            decision_id=rec.decision_id,
            execution_id=rec.execution_id,
            outcome_id=rec.outcome_id,
            evidence_id=rec.evidence_id,
            payload=rec.payload or {},
            created_at=rec.created_at,
            audit_version=AUDIT_SCHEMA_VERSION,
        )
