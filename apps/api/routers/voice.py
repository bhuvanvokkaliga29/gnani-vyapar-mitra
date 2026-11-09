"""FastAPI Router for Voice AI & Flagship Doctor Advisor Endpoints.

Endpoints:
1. POST /api/v1/voice/transcribe  - Ingest browser mic audio & return Gnani Prisma transcript
2. POST /api/v1/voice/synthesize  - Vocalize text into natural Indian regional speech via Gnani Timbre
3. POST /api/v1/doctor/query      - Complete Doctor conversation loop (NLU + BI Tools + Gemini + Audio)
4. POST /api/v1/doctor/callback   - Create merchant voice advisor callback request
5. GET  /api/v1/doctor/callbacks  - List recent callback requests
6. POST /api/v1/doctor/action/approve - Merchant one-click action approval
"""

import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import structlog

from apps.api.core.database import get_db
from apps.api.core.config import settings
from domain.models import AuditEvent
from domain.growth_models import MerchantCallbackRequest, OwnerApprovalItem
from domain.session_models import VoiceConversationSession, VoiceConversationTurn, DoctorActionProposal
from services.voice.gnani_stt_client import GnaniSTTClient
from services.voice.gnani_tts_client import GnaniTTSClient
from services.agent.doctor_advisor import DoctorAdvisorAgent, prepare_spoken_response
from services.conversation.session_manager import SessionManager
from services.governance.action_service import ActionGovernanceService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1", tags=["Voice AI & Doctor Advisor"])


# =============================================================================
# Request & Response Schemas
# =============================================================================

class VoiceSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to synthesize")
    voice: Optional[str] = Field(default=None, description="Timbre voice: Lakshmi, Avinash, Shivani")
    language: Optional[str] = Field(default=None, description="Language: kn, hi, en")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class DoctorQueryRequest(BaseModel):
    merchant_id: str = Field(default="merch_atlas_travel", description="Merchant tenant ID")
    query: str = Field(..., min_length=1, description="Merchant spoken or typed question")
    session_id: Optional[str] = Field(default=None, description="Optional persistent conversation session ID")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    preferred_language: Optional[str] = Field(default=None, description="Preferred language: kn, hi, en")
    synthesize_audio: bool = Field(default=True, description="Whether to include Gnani Timbre audio")
    agent_type: Optional[str] = Field(default="VOICE_AGENT", description="Agent scope: VOICE_AGENT or DOCTOR")


class SessionCreateRequest(BaseModel):
    merchant_id: str = Field(default="merch_atlas_travel")
    title: Optional[str] = Field(default=None)
    language: str = Field(default="kn")


class SessionInterruptRequest(BaseModel):
    merchant_id: str = Field(default="merch_atlas_travel")
    partial_text: Optional[str] = Field(default=None)


class ProposalActionRequest(BaseModel):
    merchant_id: str = Field(default="merch_atlas_travel")
    reason: Optional[str] = Field(default=None)
    actor: str = Field(default="MERCHANT_OWNER")


class CallbackCreateRequest(BaseModel):
    merchant_id: str = Field(default="merch_atlas_travel")
    phone_number: str = Field(default="+919113960498")
    preferred_language: str = Field(default="kn")
    topic: str = Field(default="SALES_SUMMARY")
    reason: Optional[str] = Field(default=None)
    preferred_time_slot: str = Field(default="Immediate (Next 10 mins)")


class ActionApprovalRequest(BaseModel):
    merchant_id: str = Field(default="merch_atlas_travel")
    action_type: str = Field(...)
    action_title: str = Field(...)
    payload: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# 1. Gnani Prisma Speech-to-Text Endpoint
# =============================================================================

@router.post("/voice/transcribe")
async def transcribe_voice(
    audio_file: UploadFile = File(...),
    language_code: Optional[str] = Form(None),
    format_type: Optional[str] = Form("codemix")
):
    """Receive browser microphone audio and return Gnani Prisma ASR transcript."""
    content_bytes = await audio_file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

    client = GnaniSTTClient()
    result = await client.transcribe_audio_async(
        audio_bytes=content_bytes,
        filename=audio_file.filename or "audio.wav",
        content_type=audio_file.content_type or "audio/wav",
        language_code=language_code,
        format_type=format_type
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=502 if "timeout" in result.get("error", "").lower() else 400,
            detail=result.get("error")
        )

    return result


# =============================================================================
# 2. Gnani Timbre Text-to-Speech Endpoint
# =============================================================================

@router.post("/voice/synthesize")
async def synthesize_voice(req: VoiceSynthesizeRequest):
    """Synthesize text into natural Indian speech audio using Gnani Timbre."""
    clean_text = prepare_spoken_response(req.text)
    client = GnaniTTSClient()
    result = await client.synthesize_speech_async(
        text=clean_text or req.text,
        voice=req.voice,
        language=req.language,
        speed=req.speed
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    # Return JSON-safe payload (exclude raw binary bytes)
    return {
        "success": True,
        "audio_base64": result.get("audio_base64"),
        "audio_length_bytes": len(result.get("audio_bytes", b"")),
        "content_type": result.get("content_type"),
        "voice": result.get("voice"),
        "language": result.get("language"),
        "latency_seconds": result.get("latency_seconds"),
        "is_mock": result.get("is_mock", False),
        "is_fallback": result.get("is_fallback", False)
    }


# =============================================================================
# 3. Complete Doctor Conversational Loop Endpoint
# =============================================================================

@router.post("/doctor/query")
async def query_doctor(
    req: DoctorQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """Unified Doctor reasoning endpoint.
    
    1. Runs Intent Classification.
    2. Executes Deterministic Business Intelligence Tools on SQLite.
    3. Synthesizes Generative Advisory via Gemini / Deterministic Engine.
    4. Automatically vocalizes spoken reply using Gnani Timbre.
    """
    import time
    t0 = time.perf_counter()

    advisor = DoctorAdvisorAgent()
    doctor_response = await advisor.answer_merchant_query(
        db=db,
        query=req.query,
        merchant_id=req.merchant_id,
        conversation_history=req.conversation_history,
        preferred_language=req.preferred_language,
        session_id=req.session_id,
        agent_type=req.agent_type or "VOICE_AGENT"
    )

    # Vocalize response via Gnani Timbre if requested
    audio_payload = None
    tts_result = {}
    if req.synthesize_audio and doctor_response.get("spoken_text"):
        tts_client = GnaniTTSClient()
        tts_clean_text = prepare_spoken_response(
            doctor_response["spoken_text"],
            language=doctor_response.get("language"),
            intent=doctor_response.get("intent")
        )
        tts_speed = doctor_response.get("speech_speed", 1.0)
        tts_result = await tts_client.synthesize_speech_async(
            text=tts_clean_text or doctor_response["spoken_text"],
            language=doctor_response["language"],
            speed=tts_speed
        )
        if tts_result.get("success"):
            raw_bytes = tts_result.get("audio_bytes", b"")
            sample_rate = 24000
            duration_sec = round((len(raw_bytes) - 44) / (sample_rate * 2), 2) if len(raw_bytes) > 44 else 0.0
            audio_payload = {
                "audio_base64": tts_result.get("audio_base64"),
                "voice": tts_result.get("voice"),
                "content_type": tts_result.get("content_type", "audio/wav"),
                "sample_rate": sample_rate,
                "duration_seconds": max(0.1, duration_sec),
                "audio_length_bytes": len(raw_bytes),
                "is_fallback": tts_result.get("is_fallback", False)
            }
            doctor_response["trace"].append(
                f"speech_synthesis:gnani_timbre:{tts_result.get('voice')}"
            )

    total_latency = round(time.perf_counter() - t0, 3)

    return {
        "success": True,
        "session_id": doctor_response.get("session_id"),
        "query": doctor_response["query"],
        "intent": doctor_response["intent"],
        "emotion": doctor_response.get("emotion", "NEUTRAL"),
        "speech_speed": doctor_response.get("speech_speed", 1.0),
        "language": doctor_response["language"],
        "spoken_text": doctor_response["spoken_text"],
        "detailed_advice": doctor_response["detailed_advice"],
        "metrics": doctor_response["metrics"],
        "recommended_action": doctor_response.get("recommended_action"),
        "focused_entity": doctor_response.get("focused_entity"),
        "audio": audio_payload,
        "trace": doctor_response["trace"],
        "gemini_live": doctor_response["gemini_live"],
        "latency_metrics": {
            "reasoning_seconds": doctor_response.get("tools_latency_seconds", 0.0),
            "tts_ttfb_seconds": tts_result.get("time_to_first_byte") if tts_result else None,
            "tts_total_seconds": tts_result.get("total_duration") if tts_result else None,
            "total_latency_seconds": total_latency
        }
    }


# =============================================================================
# 4. Merchant Callback Request Endpoints
# =============================================================================

@router.post("/doctor/callback")
async def create_callback_request(
    req: CallbackCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register an outbound voice consultation callback for the merchant."""
    cb_id = f"cb_{uuid.uuid4().hex[:12]}"

    cb_record = MerchantCallbackRequest(
        id=cb_id,
        merchant_id=req.merchant_id,
        phone_number=req.phone_number,
        preferred_language=req.preferred_language,
        topic=req.topic,
        reason=req.reason,
        preferred_time_slot=req.preferred_time_slot,
        status="PENDING"
    )
    db.add(cb_record)

    # Immutable audit ledger entry
    audit = AuditEvent(
        audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
        merchant_id=req.merchant_id,
        entity_type="CALLBACK_REQUEST",
        entity_id=cb_id,
        actor="MERCHANT_OPERATOR",
        action="CALLBACK_REQUESTED",
        payload={
            "phone": req.phone_number,
            "language": req.preferred_language,
            "topic": req.topic,
            "time_slot": req.preferred_time_slot
        }
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "SUCCESS",
        "callback_id": cb_id,
        "message": f"Callback request registered for {req.phone_number}. An AI advisor will connect shortly in {req.preferred_language}."
    }


@router.get("/doctor/callbacks")
async def list_callback_requests(
    merchant_id: str = "merch_atlas_travel",
    db: AsyncSession = Depends(get_db)
):
    """List recent callback requests for a merchant."""
    stmt = (
        select(MerchantCallbackRequest)
        .where(MerchantCallbackRequest.merchant_id == merchant_id)
        .order_by(desc(MerchantCallbackRequest.created_at))
        .limit(10)
    )
    items = (await db.execute(stmt)).scalars().all()

    return {
        "merchant_id": merchant_id,
        "total": len(items),
        "callbacks": [
            {
                "id": c.id,
                "phone_number": c.phone_number,
                "preferred_language": c.preferred_language,
                "topic": c.topic,
                "preferred_time_slot": c.preferred_time_slot,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in items
        ]
    }


# =============================================================================
# 5. Governed Merchant Action Approval Endpoint
# =============================================================================

@router.post("/doctor/action/approve")
async def approve_doctor_action(
    req: ActionApprovalRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute a merchant-approved growth action (reorder, price change, bundle)."""
    approval_id = f"appr_{uuid.uuid4().hex[:12]}"

    approval = OwnerApprovalItem(
        id=approval_id,
        merchant_id=req.merchant_id,
        action_type=req.action_type,
        title=req.action_title,
        description=f"Action '{req.action_type}' authorized directly by merchant via AI Doctor.",
        payload_json=req.payload,
        status="APPROVED"
    )
    db.add(approval)

    # Immutable audit ledger entry
    audit = AuditEvent(
        audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
        merchant_id=req.merchant_id,
        entity_type="MERCHANT_ACTION",
        entity_id=approval_id,
        actor="MERCHANT_OWNER",
        action=f"ACTION_APPROVED_{req.action_type}",
        payload=req.payload
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "EXECUTED",
        "approval_id": approval_id,
        "action_type": req.action_type,
        "message": f"Action '{req.action_title}' approved and executed successfully under policy compliance."
    }


# =============================================================================
# 6. Persistent Conversation Sessions (Stage E)
# =============================================================================

@router.post("/doctor/sessions")
async def create_voice_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a persistent voice advisory session for the merchant."""
    session = await SessionManager.create_session(
        db=db,
        merchant_id=req.merchant_id,
        title=req.title,
        language=req.language
    )
    return {
        "status": "SUCCESS",
        "session": {
            "id": session.id,
            "merchant_id": session.merchant_id,
            "title": session.title,
            "language": session.language,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None
        }
    }


@router.get("/doctor/sessions")
async def list_voice_sessions(
    merchant_id: str = "merch_atlas_travel",
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List persistent sessions owned by authenticated merchant."""
    sessions = await SessionManager.list_sessions(
        db=db,
        merchant_id=merchant_id,
        limit=limit,
        offset=offset
    )
    return {
        "merchant_id": merchant_id,
        "total": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "language": s.language,
                "status": s.status,
                "focused_entity_name": s.focused_entity_name,
                "focused_entity_sku": s.focused_entity_sku,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None
            }
            for s in sessions
        ]
    }


@router.get("/doctor/sessions/{session_id}")
async def get_voice_session(
    session_id: str,
    merchant_id: str = "merch_atlas_travel",
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full conversation history and context for a session."""
    ctx = await SessionManager.get_sliding_window_context(
        db=db,
        session_id=session_id,
        merchant_id=merchant_id,
        window_size=30
    )
    if not ctx.get("session_id"):
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
    return ctx


@router.post("/doctor/sessions/{session_id}/archive")
async def archive_voice_session(
    session_id: str,
    merchant_id: str = "merch_atlas_travel",
    db: AsyncSession = Depends(get_db)
):
    """Archive an existing session."""
    success = await SessionManager.archive_session(db, session_id, merchant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
    return {"status": "SUCCESS", "session_id": session_id, "state": "ARCHIVED"}


@router.post("/doctor/sessions/{session_id}/interrupt")
async def interrupt_voice_session(
    session_id: str,
    req: SessionInterruptRequest,
    db: AsyncSession = Depends(get_db)
):
    """Mark the latest assistant speech turn as interrupted upon barge-in or user stop."""
    turn = await SessionManager.mark_last_assistant_turn_interrupted(
        db=db,
        session_id=session_id,
        merchant_id=req.merchant_id,
        partial_text=req.partial_text
    )
    return {
        "status": "SUCCESS",
        "session_id": session_id,
        "interrupted": bool(turn),
        "turn_id": turn.id if turn else None
    }


# =============================================================================
# 7. Governed Commercial Action Proposals (Stage E)
# =============================================================================

@router.get("/doctor/actions/pending")
async def list_pending_actions(
    merchant_id: str = "merch_atlas_travel",
    db: AsyncSession = Depends(get_db)
):
    """List pending commercial action proposals awaiting merchant approval."""
    proposals = await ActionGovernanceService.list_pending_proposals(db, merchant_id)
    return {
        "merchant_id": merchant_id,
        "total": len(proposals),
        "proposals": [
            {
                "id": p.id,
                "session_id": p.session_id,
                "action_type": p.action_type,
                "title": p.title,
                "description": p.description,
                "status": p.status,
                "parameters": p.parameters,
                "financial_impact": p.financial_impact,
                "margin_floor_compliant": p.margin_floor_compliant,
                "margin_percent": float(p.margin_percent) if p.margin_percent else None,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in proposals
        ]
    }


@router.post("/doctor/actions/{proposal_id}/approve")
async def approve_action_proposal(
    proposal_id: str,
    req: ProposalActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Merchant explicit one-click approval and execution of a proposal."""
    try:
        res = await ActionGovernanceService.approve_and_execute(
            db=db,
            merchant_id=req.merchant_id,
            proposal_id=proposal_id,
            actor=req.actor
        )
        return res
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))


@router.post("/doctor/actions/{proposal_id}/reject")
async def reject_action_proposal(
    proposal_id: str,
    req: ProposalActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Merchant explicit rejection of a commercial proposal."""
    try:
        p = await ActionGovernanceService.reject_proposal(
            db=db,
            merchant_id=req.merchant_id,
            proposal_id=proposal_id,
            reason=req.reason,
            actor=req.actor
        )
        return {
            "status": "REJECTED",
            "proposal_id": p.id,
            "rejection_reason": p.rejection_reason
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))


@router.post("/doctor/actions/{proposal_id}/cancel")
async def cancel_action_proposal(
    proposal_id: str,
    req: ProposalActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Cancel an eligible proposal."""
    try:
        p = await ActionGovernanceService.cancel_proposal(
            db=db,
            merchant_id=req.merchant_id,
            proposal_id=proposal_id,
            actor=req.actor
        )
        return {
            "status": "CANCELLED",
            "proposal_id": p.id
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

