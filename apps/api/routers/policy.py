"""FastAPI Router for Merchant Policy Agent & Commercial Strategy Generation."""

import time
import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.core.database import get_db
from domain.intent_schemas import BuyerIntent
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.policy.schemas import PolicyGenerateRequest, PolicyGenerateResponse, PolicyProposal
from services.policy.agent import MerchantPolicyAgent
from services.policy.errors import PolicyError

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/policy", tags=["Merchant Policy Agent"])

_agent = MerchantPolicyAgent()
_commerce_service = CommerceService()


def get_policy_agent() -> MerchantPolicyAgent:
    return _agent


def get_commerce_service() -> CommerceService:
    return _commerce_service


@router.post("/generate", response_model=PolicyGenerateResponse, status_code=status.HTTP_200_OK)
async def generate_policy_strategy(
    req: PolicyGenerateRequest,
    db: AsyncSession = Depends(get_db),
    agent: MerchantPolicyAgent = Depends(get_policy_agent),
    commerce_svc: CommerceService = Depends(get_commerce_service)
):
    """Generate, validate, and rank merchant commercial strategies for a buyer intent.

    Flow:
    1. Resolve MerchantCommerceContext (from request payload or DB)
    2. Invoke Policy Agent reasoning
    3. Run deterministic validation against commercial guardrails
    4. Rank candidates by merchant objective
    5. Return versioned PolicyProposal with audit trace

    CRITICAL INVARIANT: The LLM can propose. It CANNOT spend or call financial APIs.
    """
    start_time = time.perf_counter()
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    try:
        # 1. Resolve Commerce Context
        context = req.commerce_context
        if not context:
            try:
                context = await commerce_svc.get_merchant_commerce_context(db, req.merchant_id)
            except MerchantNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Merchant '{req.merchant_id}' not found"
                )

        # 2. Invoke Policy Agent
        proposal = agent.generate_policy(
            intent=req.intent,
            context=context,
            buyer_intent_id=None
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "policy_strategy_generated",
            run_id=run_id,
            merchant_id=req.merchant_id,
            status=proposal.status.value,
            valid_candidates=proposal.valid_candidates_count,
            latency_ms=round(duration_ms, 2)
        )

        return PolicyGenerateResponse(
            proposal=proposal,
            latency_ms=round(duration_ms, 2),
            audit_run_id=run_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("policy_generation_internal_error", error=str(e), run_id=run_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during policy strategy generation."
        )
