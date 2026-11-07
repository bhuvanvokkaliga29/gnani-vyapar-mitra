"""Unit tests for Gemini Policy Client and Dual-Engine Policy Agent.

Validates:
1. System prompt and context formatting into Gemini request.
2. Structured JSON response parsing into typed PolicyCandidate models.
3. Fallback to deterministic heuristic engine on network/auth failure.
4. Downstream deterministic validation on LLM-proposed candidates.
"""

import pytest
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock

from domain.intent_schemas import BuyerIntent, BudgetConstraint, ConfidenceLevel
from domain.commerce_schemas import (
    MerchantCommerceContext,
    ProductResponse,
    RelationshipResponse
)
from services.policy.schemas import (
    StrategyType,
    CandidateValidationStatus,
    ProposalStatus
)
from services.policy.prompts import format_policy_prompt
from services.policy.llm_client import GeminiPolicyClient
from services.policy.agent import MerchantPolicyAgent


@pytest.fixture
def sample_intent() -> BuyerIntent:
    return BuyerIntent(
        category="travel_backpack",
        use_case="travel",
        quantity=1,
        budget=BudgetConstraint(max_amount_paise=500000, currency="INR"),
        confidence=ConfidenceLevel.HIGH
    )


@pytest.fixture
def sample_context() -> MerchantCommerceContext:
    from datetime import datetime, timezone
    p1 = ProductResponse(
        id="prod_atlas_01",
        merchant_id="merch_atlas_travel",
        sku="SKU-ATL-01",
        name="Atlas Pro Backpack 35L",
        category="travel_backpack",
        price_paise=400000,
        cost_paise=200000,
        currency="INR",
        inventory_quantity=15,
        reserved_quantity=0,
        available_to_sell=15,
        gross_profit_paise=200000,
        gross_margin_percent=Decimal("50.00"),
        is_active=True,
        is_eligible=True,
        attributes={"capacity": "35L", "laptop_sleeve": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    p2 = ProductResponse(
        id="prod_pouch_01",
        merchant_id="merch_atlas_travel",
        sku="SKU-POUCH-01",
        name="Atlas Tech Pouch",
        category="accessory",
        price_paise=100000,
        cost_paise=40000,
        currency="INR",
        inventory_quantity=20,
        reserved_quantity=0,
        available_to_sell=20,
        gross_profit_paise=60000,
        gross_margin_percent=Decimal("60.00"),
        is_active=True,
        is_eligible=True,
        attributes={"waterproof": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    rel = RelationshipResponse(
        id=1,
        merchant_id="merch_atlas_travel",
        primary_product_id="prod_atlas_01",
        related_product_id="prod_pouch_01",
        relationship_type="COMPLEMENTARY",
        affinity_score=Decimal("0.90"),
        source="merchant_defined",
        confidence=Decimal("1.00"),
        created_at=datetime.now(timezone.utc)
    )
    return MerchantCommerceContext(
        merchant_id="merch_atlas_travel",
        merchant_name="Atlas Travel Gear",
        currency="INR",
        status="active",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        constraints={
            "minimum_margin_percent": Decimal("25.00"),
            "maximum_discount_percent": Decimal("20.00"),
            "target_aov_paise": 400000
        },
        priorities={
            "priority_product_ids": ["prod_atlas_01"],
            "priority_categories": ["travel_backpack"],
            "clearance_product_ids": []
        },
        products=[p1, p2],
        relationships=[rel],
        generated_at=datetime.now(timezone.utc)
    )


def test_format_policy_prompt_structure(sample_intent, sample_context):
    """Verify format_policy_prompt produces grounded JSON structure."""
    prompt = format_policy_prompt(sample_intent, sample_context, sample_context.products)
    assert "=== MERCHANT CONTEXT ===" in prompt
    assert "=== ELIGIBLE PRODUCTS IN STOCK ===" in prompt
    assert "=== BUYER INTENT ===" in prompt
    assert "prod_atlas_01" in prompt
    assert "Atlas Pro Backpack 35L" in prompt
    assert "COMPLEMENTARY" in prompt


def test_gemini_client_unconfigured_behavior(sample_intent, sample_context):
    """Client with no API key should gracefully report not configured and return None."""
    client = GeminiPolicyClient(api_key=None)
    assert not client.is_configured
    assert client.propose_candidates_sync(sample_intent, sample_context, sample_context.products) is None


def test_gemini_client_mock_api_success(sample_intent, sample_context):
    """Verify Gemini JSON response is parsed into valid PolicyCandidate instances."""
    client = GeminiPolicyClient(api_key="test_gemini_api_key")

    mock_llm_json = {
        "candidates": [
            {
                "strategy_type": "COMPLEMENTARY_BUNDLE",
                "product_ids": ["prod_atlas_01", "prod_pouch_01"],
                "bundle_components": [
                    {"product_id": "prod_atlas_01", "quantity": 1},
                    {"product_id": "prod_pouch_01", "quantity": 1}
                ],
                "positioning": "Ultimate travel combination",
                "rationale": "Bundling the 35L backpack with tech pouch fits within ₹5,000 budget.",
                "evidence": [
                    {
                        "evidence_type": "merchant_relationship",
                        "field": "COMPLEMENTARY",
                        "description": "Tech pouch complements backpack"
                    }
                ]
            },
            {
                "strategy_type": "BOUNDED_DISCOUNT",
                "product_ids": ["prod_atlas_01"],
                "bundle_components": [{"product_id": "prod_atlas_01", "quantity": 1}],
                "incentive": {
                    "incentive_type": "discount",
                    "discount_percent": 10.0,
                    "description": "10% promotional conversion incentive"
                },
                "positioning": "Special value offer",
                "rationale": "10% discount leaves healthy 44% margin.",
                "evidence": []
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_llm_json)}]
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_response):
        candidates = client.propose_candidates_sync(sample_intent, sample_context, sample_context.products)

    assert candidates is not None
    assert len(candidates) == 2
    assert candidates[0].strategy_type == StrategyType.COMPLEMENTARY_BUNDLE
    assert candidates[0].product_ids == ["prod_atlas_01", "prod_pouch_01"]
    assert candidates[1].strategy_type == StrategyType.BOUNDED_DISCOUNT
    assert candidates[1].incentive.discount_percent == Decimal("10.0")


def test_agent_dual_engine_fallback_when_llm_unavailable(sample_intent, sample_context):
    """When LLM is unconfigured or fails, agent seamlessly falls back to deterministic heuristic."""
    # Unconfigured client
    agent = MerchantPolicyAgent(llm_client=GeminiPolicyClient(api_key=""))
    proposal = agent.generate_policy(sample_intent, sample_context)

    assert proposal.status == ProposalStatus.APPROVED_FOR_EVALUATION
    assert proposal.model_provider == "deterministic-reasoning-engine"
    assert len(proposal.candidates) >= 2
    assert any("heuristic_candidates_generated" in step for step in proposal.audit_trail["step_trace"])


def test_agent_dual_engine_uses_llm_when_available(sample_intent, sample_context):
    """When LLM is configured and responds, agent tags provider as Gemini and validates proposals."""
    client = GeminiPolicyClient(api_key="live_test_key")

    mock_llm_candidates = [
        {
            "strategy_type": "SINGLE_PRODUCT",
            "product_ids": ["prod_atlas_01"],
            "bundle_components": [{"product_id": "prod_atlas_01", "quantity": 1}],
            "positioning": "Core travel pack",
            "rationale": "Satisfies buyer requirements.",
            "evidence": []
        }
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps({"candidates": mock_llm_candidates})}]
                }
            }
        ]
    }

    agent = MerchantPolicyAgent(llm_client=client)

    with patch("httpx.Client.post", return_value=mock_response):
        proposal = agent.generate_policy(sample_intent, sample_context)

    assert proposal.model_provider == "gemini-1.5-flash"
    assert any("gemini_llm_candidates_proposed" in step for step in proposal.audit_trail["step_trace"])
    # Crucially, downstream deterministic validation approved the compliant candidate
    assert proposal.selected_candidate.validation_status == CandidateValidationStatus.APPROVED
