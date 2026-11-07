"""FastAPI router for AI Buyer Lab simulation endpoints."""

import time
import uuid
from fastapi import APIRouter, HTTPException, Depends
import structlog

from services.buyer_lab.schemas import (
    BuyerSimulationRequest,
    BuyerSimulationResponse
)
from services.buyer_lab.simulator import BuyerSimulator

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/buyer-lab", tags=["AI Buyer Lab"])


def get_buyer_simulator() -> BuyerSimulator:
    """Dependency provider for BuyerSimulator."""
    return BuyerSimulator()


@router.post("/simulate", response_model=BuyerSimulationResponse)
async def simulate_buyer_choice(
    request: BuyerSimulationRequest,
    simulator: BuyerSimulator = Depends(get_buyer_simulator)
) -> BuyerSimulationResponse:
    """Simulate machine-buyer evaluation and selection over a candidate offer set.

    Inviolable Boundary:
    - This is an offline simulation of buyer choice.
    - Zero Razorpay API calls, zero financial executions, zero database mutations.
    - Zero visibility into merchant internal financial data (COGS, margins).
    """
    start_time = time.perf_counter()
    sim_id = f"sim_{uuid.uuid4().hex[:16]}"

    try:
        selection_result = simulator.simulate_selection(
            intent=request.intent,
            offers=request.offers,
            persona=request.buyer_persona,
            scenario_id=request.scenario_id
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return BuyerSimulationResponse(
            result=selection_result,
            simulation_id=sim_id,
            execution_time_ms=elapsed_ms
        )
    except Exception as e:
        logger.error("buyer_simulation_failed", error=str(e), sim_id=sim_id)
        raise HTTPException(
            status_code=400,
            detail=f"Simulation failed: {str(e)}"
        )
