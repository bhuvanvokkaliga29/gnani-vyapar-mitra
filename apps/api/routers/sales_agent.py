"""FastAPI Router for Sales Agent & Negotiation Playground."""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.sales_agent.service import SalesAgentService

router = APIRouter(prefix="/api/v1/sales-agent", tags=["Sales & Negotiation Agent"])


class ChatMessageRequest(BaseModel):
    merchant_id: str = "merch_atlas_travel"
    message: str
    product_id: Optional[str] = None
    negotiation_round: Optional[int] = 1
    language: Optional[str] = "en"


@router.post("/chat")
async def chat_with_agent(
    req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """Interactive buyer-facing bargaining conversation governed strictly by merchant policy."""
    try:
        resp = await SalesAgentService.process_chat(
            db=db,
            merchant_id=req.merchant_id,
            message=req.message,
            product_id=req.product_id,
            negotiation_round=req.negotiation_round or 1,
            language=req.language or "en"
        )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
