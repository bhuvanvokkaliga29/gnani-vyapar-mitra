"""FastAPI Router for Growth Doctor Endpoints."""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.growth_doctor.service import GrowthDoctorService

router = APIRouter(prefix="/api/v1/doctor", tags=["Growth Doctor"])


class ProposeActionRequest(BaseModel):
    merchant_id: str
    finding_id: str


@router.get("/findings")
async def get_doctor_findings(
    merchant_id: str = Query("merch_atlas_travel"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve evidence-backed commercial diagnostic findings for a merchant."""
    try:
        findings = await GrowthDoctorService.analyze_merchant(db, merchant_id)
        return {
            "merchant_id": merchant_id,
            "total_findings": len(findings),
            "findings": [
                {
                    "id": f.id,
                    "category": f.category,
                    "title": f.title,
                    "description": f.description,
                    "rupee_impact_paise": f.rupee_impact_paise,
                    "rupee_impact_formatted": f"₹{f.rupee_impact_paise / 100:,.2f}",
                    "confidence": f.confidence,
                    "method_note": f.method_note,
                    "evidence_rows": f.evidence_rows_json,
                    "recommended_action_type": f.recommended_action_type,
                    "recommended_action_payload": f.recommended_action_payload,
                    "status": f.status,
                    "created_at": f.created_at.isoformat() if f.created_at else None
                }
                for f in findings
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnostic error: {str(e)}")


@router.post("/actions/propose")
async def propose_finding_action(
    req: ProposeActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a pending OwnerApprovalItem from a Growth Doctor finding."""
    try:
        approval = await GrowthDoctorService.propose_finding_action(
            db=db,
            finding_id=req.finding_id,
            merchant_id=req.merchant_id
        )
        return {
            "status": "PROPOSED",
            "approval_id": approval.id,
            "merchant_id": approval.merchant_id,
            "title": approval.title,
            "description": approval.description,
            "payload": approval.payload_json
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
