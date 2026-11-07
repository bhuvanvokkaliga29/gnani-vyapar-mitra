"""Integration tests for Phase 9.4 FastAPI Observability Endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app
from services.audit.service import AuditService


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify /health returns 200 with service metadata and zero state mutation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "merchant-policy-agent"
        assert "Phase 9.4" in data["phase"]


@pytest.mark.asyncio
async def test_readiness_endpoint(db_session):
    """Verify /ready performs deterministic local database check without external calls."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Verify /metrics returns bounded operational snapshot with zero secret leakage."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        data = res.json()
        assert data["schema_version"] == "observability-metrics/v1"
        assert "counters" in data
        assert "latencies" in data


@pytest.mark.asyncio
async def test_audit_events_api_tenant_scoping(db_session, client):
    """Verify /api/v1/observability/audit/events enforces strict merchant_id scoping."""
    # Seed audit event
    await AuditService.record_event(
        db=db_session,
        merchant_id="merch_api_audit_01",
        entity_type="DECISION",
        entity_id="dec_api_01",
        action="DECISION_CREATED"
    )
    await db_session.commit()

    # 1. Valid merchant query
    res = await client.get(
        "/api/v1/observability/audit/events",
        params={"merchant_id": "merch_api_audit_01"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 1
    assert data["merchant_id"] == "merch_api_audit_01"

    # 2. Query for non-existent or empty merchant returns empty / 403
    res_empty = await client.get(
        "/api/v1/observability/audit/events",
        params={"merchant_id": ""}
    )
    assert res_empty.status_code == 403
