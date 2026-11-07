"""Integration tests for Phase 9.4 Audit Immutability and Tenant Isolation."""

import pytest
from sqlalchemy import select

from domain.models import AuditEvent
from services.audit.service import AuditService
from services.audit.errors import (
    AuditImmutabilityViolationError,
    AuditTenantViolationError,
    AuditEventNotFoundError,
)


@pytest.mark.asyncio
async def test_audit_event_append_only_persists(db_session):
    """Verify AuditService records append-only events successfully with correlation enrichment."""
    event = await AuditService.record_event(
        db=db_session,
        merchant_id="merch_audit_01",
        entity_type="DECISION",
        entity_id="dec_test_123",
        action="DECISION_EVALUATED",
        actor="CANONICAL_RUNTIME",
        opportunity_id="opp_test_123",
        payload={"mode": "EXPLORE", "candidate_count": 3}
    )
    await db_session.commit()

    assert event.id is not None
    assert event.audit_event_id.startswith("aud_")
    assert event.merchant_id == "merch_audit_01"
    assert event.action == "DECISION_EVALUATED"


@pytest.mark.asyncio
async def test_audit_event_update_raises_immutability_violation(db_session):
    """MANDATORY ADVERSARIAL TEST: An existing AuditEvent CANNOT be updated."""
    event = await AuditService.record_event(
        db=db_session,
        merchant_id="merch_audit_01",
        entity_type="EXECUTION",
        entity_id="exec_test_456",
        action="EXECUTION_AUTHORIZED",
        actor="EXECUTION_BOUNDARY"
    )
    await db_session.commit()

    # Attempt to tamper with the audit event
    event.action = "FORGED_TAMPERED_ACTION"
    with pytest.raises(AuditImmutabilityViolationError) as exc_info:
        await db_session.commit()

    assert "strictly forbidden" in str(exc_info.value).lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_audit_event_delete_raises_immutability_violation(db_session):
    """MANDATORY ADVERSARIAL TEST: An existing AuditEvent CANNOT be deleted."""
    event = await AuditService.record_event(
        db=db_session,
        merchant_id="merch_audit_01",
        entity_type="OUTCOME",
        entity_id="out_test_789",
        action="OUTCOME_RESOLVED",
        actor="OUTCOME_SERVICE"
    )
    await db_session.commit()

    # Attempt to delete the audit event
    await db_session.delete(event)
    with pytest.raises(AuditImmutabilityViolationError) as exc_info:
        await db_session.commit()

    assert "strictly forbidden" in str(exc_info.value).lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_audit_query_enforces_tenant_isolation(db_session):
    """Verify audit query results are strictly isolated by merchant tenant."""
    # Seed events for Merchant Alpha and Merchant Beta
    await AuditService.record_event(
        db=db_session,
        merchant_id="merch_tenant_alpha",
        entity_type="DECISION",
        entity_id="dec_alpha_01",
        action="DECISION_CREATED"
    )
    await AuditService.record_event(
        db=db_session,
        merchant_id="merch_tenant_beta",
        entity_type="DECISION",
        entity_id="dec_beta_01",
        action="DECISION_CREATED"
    )
    await db_session.commit()

    # 1. Merchant Alpha query returns only Alpha events
    resp_alpha = await AuditService.query_events(db_session, merchant_id="merch_tenant_alpha")
    assert resp_alpha.total_count >= 1
    for ev in resp_alpha.events:
        assert ev.merchant_id == "merch_tenant_alpha"

    # 2. Merchant Beta query returns only Beta events
    resp_beta = await AuditService.query_events(db_session, merchant_id="merch_tenant_beta")
    assert resp_beta.total_count >= 1
    for ev in resp_beta.events:
        assert ev.merchant_id == "merch_tenant_beta"

    # 3. Empty merchant_id raises AuditTenantViolationError
    with pytest.raises(AuditTenantViolationError):
        await AuditService.query_events(db_session, merchant_id="")

    # 4. Merchant Beta cannot fetch Merchant Alpha's event by ID
    alpha_ev_id = resp_alpha.events[0].audit_event_id
    with pytest.raises(AuditEventNotFoundError):
        await AuditService.get_event_by_id(db_session, audit_event_id=alpha_ev_id, merchant_id="merch_tenant_beta")
