"""FastAPI Application Main Entrypoint."""

import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.config import settings
from apps.api.core.database import init_db
from apps.api.core.logging import configure_structured_logging
from apps.api.core.middleware import CorrelationMiddleware
from apps.api.routers import (
    health, orders, webhooks, merchants, intent, policy, execution,
    buyer_lab, experiments, learning, reward, memory, learning_model, policy_selection,
    policy_safety, policy_exploration, policy_lifecycle, evaluation, decisions, decision_execution, outcomes,
    observability, dashboard, mcp,
    growth_doctor, marketplace, sales_agent, owner_policy, campaigns, demo_control,
    whatsapp, voice, gnani_agent
)
from fastapi.responses import FileResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Initialize structured logging with information hygiene
    configure_structured_logging()
    # Initialize database tables
    await init_db()
    yield


app = FastAPI(
    title="Merchant Growth Agent API",
    description="Autonomous commercial policy and channel growth intelligence for independent Indian merchants (HackSprint PS21).",
    version="0.2.0",
    lifespan=lifespan
)

# Correlation and Observability Middleware (must be outermost to trace entire request lifecycle)
app.add_middleware(CorrelationMiddleware)

# Enable CORS for local development and debug UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )

# Register Routers
app.include_router(health.router)
app.include_router(observability.router)
app.include_router(orders.router)
app.include_router(webhooks.router)
app.include_router(webhooks.router, prefix="/api")
app.include_router(merchants.router)
app.include_router(intent.router)
app.include_router(policy.router)
app.include_router(execution.router)
app.include_router(buyer_lab.router)
app.include_router(experiments.router)
app.include_router(learning.router)
app.include_router(reward.router)
app.include_router(memory.router)
app.include_router(learning_model.router)
app.include_router(policy_selection.router)
app.include_router(policy_safety.router)
app.include_router(policy_exploration.router)
app.include_router(policy_lifecycle.router)
app.include_router(evaluation.router)
app.include_router(decisions.router)
app.include_router(decision_execution.router)
app.include_router(outcomes.router)
app.include_router(dashboard.router)
app.include_router(mcp.router)

# Growth Agent Extension Routers
app.include_router(growth_doctor.router)
app.include_router(marketplace.router)
app.include_router(sales_agent.router)
app.include_router(owner_policy.router)
app.include_router(campaigns.router)
app.include_router(demo_control.router)
app.include_router(whatsapp.router)
app.include_router(voice.router)
app.include_router(gnani_agent.router)

@app.get("/test-checkout", response_class=FileResponse)
async def test_checkout_page():
    return FileResponse("scripts/test_checkout.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
