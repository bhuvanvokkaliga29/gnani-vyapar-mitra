"""Health, Readiness, and Operational Metrics Diagnostic Endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.core.database import get_db
from services.observability.metrics import RuntimeMetricsRegistry

router = APIRouter(tags=["Health & Readiness"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe confirming the application process is running.
    
    Guarantees: Zero state mutation, zero external API calls, zero secret leakage.
    """
    return {
        "status": "healthy",
        "service": "merchant-policy-agent",
        "version": "0.1.0",
        "phase": "Phase 9.4: Observability, Audit & Tenant Isolation"
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe checking database connectivity without external dependencies.
    
    Guarantees: Zero external provider or LLM calls, deterministic response.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected"
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database readiness check failed: {str(exc)}"
        )


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics():
    """Operational metrics snapshot with strictly bounded labels and zero secret leakage."""
    return RuntimeMetricsRegistry.snapshot()

