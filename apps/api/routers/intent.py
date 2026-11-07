"""FastAPI Router for Buyer Intent Parsing & Conversational Memory."""

import time
import structlog
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from domain.intent_schemas import IntentParseRequest, IntentParseResponse, BuyerIntent
from services.intent.extractor import IntentExtractor
from services.intent.conversation import ConversationManager
from services.intent.validator import IntentValidationError

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/intent", tags=["Buyer Intent Engine"])

# In-memory singleton conversation manager and extractor
_conversation_manager = ConversationManager()
_extractor = IntentExtractor()


def get_intent_extractor() -> IntentExtractor:
    return _extractor


def get_conversation_manager() -> ConversationManager:
    return _conversation_manager


@router.post("/parse", response_model=IntentParseResponse, status_code=status.HTTP_200_OK)
async def parse_buyer_intent(
    req: IntentParseRequest,
    extractor: IntentExtractor = Depends(get_intent_extractor),
    conv_mgr: ConversationManager = Depends(get_conversation_manager)
):
    """Parse an unstructured natural-language buyer utterance into a structured BuyerIntent.

    Input Constraints (enforced by Pydantic schema):
    - message: 1-2000 characters (empty/oversized rejected with 422)
    - conversation_id: optional string for multi-turn sessions

    Returns:
    - 200: Structured BuyerIntent with conversation context
    - 422: Validation error (empty message, oversized message, malformed JSON)
    - 500: Unexpected internal error (no stack traces leaked)
    """
    start_time = time.perf_counter()

    try:
        session = conv_mgr.get_or_create_session(req.conversation_id)
        raw_intent = extractor.parse_utterance(req.message)

        # Accumulate into conversation session
        accumulated_intent = session.add_turn(req.message, raw_intent)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return IntentParseResponse(
            intent=accumulated_intent,
            conversation_id=session.conversation_id,
            turn_index=len(session.turns),
            processing_time_ms=round(duration_ms, 2)
        )
    except IntentValidationError as e:
        logger.error("intent_validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Intent validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error("intent_parse_internal_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing intent. Please try again."
        )
