"""Unit Tests for Doctor Business Intelligence Tools and Dynamic LLM Tool Calling Agent (Stage D)."""

import pytest
from decimal import Decimal

from apps.api.core.database import AsyncSessionLocal
from domain.llm_schemas import (
    LLMMessage,
    LLMRole,
    LLMResponse,
    LLMToolCall,
    LLMUsage,
    LLMQuotaExceededError
)
from services.commerce.business_intelligence import (
    BusinessIntelligenceService,
    VASTRAM_MINIMUM_MARGIN_FLOOR_PERCENT
)
from services.agent.doctor_tools import (
    DOCTOR_TOOLS,
    execute_doctor_tool
)
from services.agent.doctor_advisor import (
    DoctorAdvisorAgent,
    MAX_TOOL_ITERATIONS
)
from services.llm.base import LLMProvider


# =============================================================================
# Mock Provider for Stage D Agent Tests
# =============================================================================

class MockProvider(LLMProvider):
    """Controllable mock provider for testing dynamic autonomous tool calling loops."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_history = []

    @property
    def provider_name(self) -> str:
        return "mock_provider"

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def active_model(self) -> str:
        return "mock-model-v1"

    async def chat_complete(self, messages, temperature=0.2, max_tokens=1024, timeout=15.0):
        return await self.chat_with_tools(messages, tools=[], temperature=temperature, max_tokens=max_tokens)

    async def chat_with_tools(self, messages, tools=None, tool_choice="auto", temperature=0.2, max_tokens=1024, timeout=15.0):
        self.call_history.append({"messages": messages, "tools": tools})
        if not self.responses:
            raise RuntimeError("No more mocked responses available in test sequence")
        return self.responses.pop(0)


# =============================================================================
# 1. Tests for the 10 Authoritative Business Intelligence Tools
# =============================================================================

@pytest.mark.asyncio
async def test_tool_1_get_daily_sales():
    async with AsyncSessionLocal() as db:
        res = await BusinessIntelligenceService.get_daily_sales(db, "merch_atlas_travel")
        assert res["date"] is not None
        assert res["total_orders"] >= 18
        assert res["revenue_paise"] > 0
        assert "₹" in res["revenue_formatted"]
        assert res["gross_margin_percent"] > 0
        assert "WHATSAPP" in res["channels"]


@pytest.mark.asyncio
async def test_tool_2_get_sales_summary():
    async with AsyncSessionLocal() as db:
        res = await BusinessIntelligenceService.get_sales_summary(db, "merch_atlas_travel", days=7)
        assert res["period_days"] == 7
        assert res["order_count"] > 0
        assert res["total_revenue_paise"] > 0
        assert "₹" in res["total_revenue_formatted"]
        assert res["aov_paise"] > 0


@pytest.mark.asyncio
async def test_tool_3_get_profit_summary():
    async with AsyncSessionLocal() as db:
        res = await BusinessIntelligenceService.get_profit_summary(db, "merch_atlas_travel", days=30)
        assert res["period_days"] == 30
        assert res["total_revenue_paise"] > 0
        assert res["gross_margin_percent"] >= 25.0
        assert res["is_above_policy_floor"] is True
        assert res["policy_margin_floor_percent"] == 25.0


@pytest.mark.asyncio
async def test_tool_4_get_top_selling_products():
    async with AsyncSessionLocal() as db:
        top_items = await BusinessIntelligenceService.get_top_selling_products(db, "merch_atlas_travel", limit=5, days=30)
        assert isinstance(top_items, list)
        assert len(top_items) > 0
        assert len(top_items) <= 5
        top_1 = top_items[0]
        assert "sku" in top_1
        assert "name" in top_1
        assert top_1["units_sold"] > 0
        assert top_1["revenue_paise"] > 0


@pytest.mark.asyncio
async def test_tool_5_get_low_stock_products():
    async with AsyncSessionLocal() as db:
        low_stock = await BusinessIntelligenceService.get_low_stock_products(db, "merch_atlas_travel", threshold=15)
        assert isinstance(low_stock, list)
        assert len(low_stock) > 0
        first = low_stock[0]
        assert "sku" in first
        assert "stock" in first
        assert first["stock"] <= 15
        assert first["urgency"] in ("CRITICAL", "HIGH", "MEDIUM")


@pytest.mark.asyncio
async def test_tool_6_get_inventory_health():
    async with AsyncSessionLocal() as db:
        inv = await BusinessIntelligenceService.get_inventory_health(db, "merch_atlas_travel")
        assert inv["total_products_count"] >= 64
        assert inv["dead_stock_count"] >= 2
        assert inv["total_trapped_capital_paise"] > 0
        assert inv["annual_holding_cost_paise"] > 0


@pytest.mark.asyncio
async def test_tool_7_compare_sales_periods():
    async with AsyncSessionLocal() as db:
        cmp = await BusinessIntelligenceService.compare_sales_periods(db, "merch_atlas_travel", current_days=7, previous_days=7)
        assert "current_revenue_paise" in cmp
        assert "previous_revenue_paise" in cmp
        assert "revenue_growth_percent" in cmp
        assert "orders_growth_percent" in cmp
        assert "growth_trend" in cmp
        assert cmp["current_revenue_paise"] > 0


@pytest.mark.asyncio
async def test_tool_8_get_channel_performance():
    async with AsyncSessionLocal() as db:
        matrix = await BusinessIntelligenceService.get_channel_performance(db, "merch_atlas_travel")
        assert "channels" in matrix
        channels = matrix["channels"]
        channel_codes = [c["channel_code"] for c in channels]
        assert "WHATSAPP" in channel_codes
        assert "AMAZON" in channel_codes
        assert "recommended_primary_channel" in matrix


@pytest.mark.asyncio
async def test_tool_9_simulate_price_change_margin_floor():
    assert VASTRAM_MINIMUM_MARGIN_FLOOR_PERCENT == Decimal("25.00")
    async with AsyncSessionLocal() as db:
        # 1. Price change with healthy margin >= 25% (₹1,999 on ₹650 cost item)
        sim_safe = await BusinessIntelligenceService.simulate_price_change(
            db, "merch_atlas_travel", "VAST-SH-01", 199900
        )
        assert sim_safe["success"] is True
        assert sim_safe["policy_compliant"] is True
        assert sim_safe["target_margin_percent"] >= 25.0
        assert sim_safe["warning"] is None

        # 2. Steep clearance discount violating 25% floor (₹700 on ₹650 cost item -> 7.14% margin)
        sim_unsafe = await BusinessIntelligenceService.simulate_price_change(
            db, "merch_atlas_travel", "VAST-SH-01", 70000
        )
        assert sim_unsafe["success"] is True
        assert sim_unsafe["policy_compliant"] is False
        assert sim_unsafe["target_margin_percent"] < 25.0
        assert "VIOLATION" in sim_unsafe["warning"]

        # 3. Non-existent SKU handled gracefully without exception
        sim_missing = await BusinessIntelligenceService.simulate_price_change(
            db, "merch_atlas_travel", "NON-EXISTENT-SKU", 100000
        )
        assert sim_missing["success"] is False
        assert "not found" in sim_missing["error"]


@pytest.mark.asyncio
async def test_tool_10_get_business_recommendations():
    async with AsyncSessionLocal() as db:
        recs = await BusinessIntelligenceService.get_business_recommendations(db, "merch_atlas_travel")
        assert "recommendations" in recs
        assert len(recs["recommendations"]) >= 1
        rec = recs["recommendations"][0]
        assert "type" in rec
        assert "title" in rec
        assert "action_payload" in rec


# =============================================================================
# 2. Tests for Tool Declarations and Safe Dispatcher
# =============================================================================

def test_tool_declarations_schema():
    assert len(DOCTOR_TOOLS) >= 10
    tool_names = [t.function.name for t in DOCTOR_TOOLS]
    expected_names = [
        "get_daily_sales",
        "get_sales_summary",
        "get_profit_summary",
        "get_top_selling_products",
        "get_low_stock_products",
        "get_inventory_health",
        "compare_sales_periods",
        "get_channel_performance",
        "simulate_price_change",
        "get_business_recommendations"
    ]
    for name in expected_names:
        assert name in tool_names

    # Check simulate_price_change required parameters
    sim_tool = next(t for t in DOCTOR_TOOLS if t.function.name == "simulate_price_change")
    assert "sku_or_id" in sim_tool.function.parameters["required"]
    assert "new_price_paise" in sim_tool.function.parameters["required"]


@pytest.mark.asyncio
async def test_execute_doctor_tool_dispatcher():
    async with AsyncSessionLocal() as db:
        # Valid execution
        res = await execute_doctor_tool(db, "merch_atlas_travel", "get_daily_sales", {})
        assert "revenue_paise" in res

        # Unknown tool
        res_unknown = await execute_doctor_tool(db, "merch_atlas_travel", "invalid_mystery_tool", {})
        assert "error" in res_unknown
        assert "not recognized" in res_unknown["error"]


# =============================================================================
# 3. Tests for Dynamic Autonomous Tool Calling in DoctorAdvisorAgent
# =============================================================================

@pytest.mark.asyncio
async def test_doctor_dynamic_single_tool_loop():
    # Turn 1: LLM decides to call 'get_daily_sales'
    step_1 = LLMResponse(
        content="",
        tool_calls=[
            LLMToolCall(id="call_1", name="get_daily_sales", arguments={})
        ],
        provider="mock_provider",
        model="mock-model"
    )

    # Turn 2: LLM receives tool output and synthesizes dual output
    step_2 = LLMResponse(
        content="SPOKEN_REPLY: Today Vastram achieved strong revenue with healthy gross margins.\nDETAILED_ADVICE: Daily sales analysis confirms strong performance:\n- Revenue verified from store database.\n- Gross margin above 25% policy floor.",
        tool_calls=[],
        provider="mock_provider",
        model="mock-model"
    )

    mock_provider = MockProvider([step_1, step_2])
    agent = DoctorAdvisorAgent(api_key="mock_key")
    agent._llm = mock_provider

    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(
            db,
            query="How did Vastram perform today?",
            merchant_id="merch_atlas_travel",
            preferred_language="en"
        )

        assert res["gemini_live"] is True
        assert res["spoken_text"] == "Today Vastram achieved strong revenue with healthy gross margins."
        assert "Daily sales analysis confirms strong performance" in res["detailed_advice"]
        assert "tool_executed:get_daily_sales" in res["trace"]
        assert "get_daily_sales" in res["metrics"]
        assert res["metrics"]["get_daily_sales"]["revenue_paise"] > 0
        assert len(mock_provider.call_history) == 2


@pytest.mark.asyncio
async def test_doctor_dynamic_multi_tool_loop():
    # Turn 1: LLM calls get_low_stock_products
    step_1 = LLMResponse(
        content="",
        tool_calls=[
            LLMToolCall(id="call_stock", name="get_low_stock_products", arguments={"threshold": 10})
        ],
        provider="mock_provider",
        model="mock-model"
    )
    # Turn 2: LLM calls get_inventory_health
    step_2 = LLMResponse(
        content="",
        tool_calls=[
            LLMToolCall(id="call_inv", name="get_inventory_health", arguments={})
        ],
        provider="mock_provider",
        model="mock-model"
    )
    # Turn 3: LLM final response
    step_3 = LLMResponse(
        content="SPOKEN_REPLY: You have critical low stock on several trousers, while capital is trapped in dead inventory.\nDETAILED_ADVICE: Comprehensive stock audit complete.",
        tool_calls=[],
        provider="mock_provider",
        model="mock-model"
    )

    mock_provider = MockProvider([step_1, step_2, step_3])
    agent = DoctorAdvisorAgent(api_key="mock_key")
    agent._llm = mock_provider

    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(
            db,
            query="Check my inventory and dead stock situation",
            merchant_id="merch_atlas_travel",
            preferred_language="en"
        )

        assert res["gemini_live"] is True
        assert "tool_executed:get_low_stock_products" in res["trace"]
        assert "tool_executed:get_inventory_health" in res["trace"]
        assert "get_low_stock_products" in res["metrics"]
        assert "get_inventory_health" in res["metrics"]
        assert len(mock_provider.call_history) == 3


@pytest.mark.asyncio
async def test_doctor_agent_max_tool_iterations_guard():
    # Create an infinite tool-calling loop (returns tool call indefinitely)
    infinite_steps = [
        LLMResponse(
            content="",
            tool_calls=[LLMToolCall(id=f"c_{i}", name="get_daily_sales", arguments={})],
            provider="mock_provider",
            model="mock-model"
        )
        for i in range(10)
    ]

    mock_provider = MockProvider(infinite_steps)
    agent = DoctorAdvisorAgent(api_key="mock_key")
    agent._llm = mock_provider

    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(
            db,
            query="Keep checking forever",
            merchant_id="merch_atlas_travel"
        )

        # Must terminate at MAX_TOOL_ITERATIONS and formulate synthesis from collected data
        assert len(mock_provider.call_history) == MAX_TOOL_ITERATIONS
        assert res["spoken_text"] is not None
        assert res["metrics"] is not None


@pytest.mark.asyncio
async def test_doctor_agent_multilingual_handling():
    # 1. Kannada query
    agent = DoctorAdvisorAgent(api_key="mock_key")
    kannada_reply = LLMResponse(
        content="SPOKEN_REPLY: ಇವತ್ತು ವಸ್ತ್ರಂ ಅಂಗಡಿಯಲ್ಲಿ 44,982 ರೂಪಾಯಿಗಳ ವ್ಯಾಪಾರವಾಗಿದೆ.\nDETAILED_ADVICE: ಇವತ್ತಿನ ದಿನದ ಒಟ್ಟು 18 ಆರ್ಡರ್‌ಗಳು ಬಂದಿವೆ.",
        tool_calls=[],
        provider="mock_provider",
        model="mock-model"
    )
    agent._llm = MockProvider([kannada_reply])

    async with AsyncSessionLocal() as db:
        res_kn = await agent.answer_merchant_query(
            db,
            query="ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?",
            merchant_id="merch_atlas_travel"
        )
        assert res_kn["language"] == "kn"
        assert "language_detected:kn" in res_kn["trace"]
        assert "44,982 ರೂಪಾಯಿ" in res_kn["spoken_text"]

    # 2. Hindi query
    hindi_reply = LLMResponse(
        content="SPOKEN_REPLY: आज वस्त्रम में 44,982 रुपये की कुल बिक्री हुई है।\nDETAILED_ADVICE: आज 18 ऑردರ್्स पूरे हुए हैं।",
        tool_calls=[],
        provider="mock_provider",
        model="mock-model"
    )
    agent._llm = MockProvider([hindi_reply])

    async with AsyncSessionLocal() as db:
        res_hi = await agent.answer_merchant_query(
            db,
            query="आज की बिक्री कितनी है?",
            merchant_id="merch_atlas_travel"
        )
        assert res_hi["language"] == "hi"
        assert "language_detected:hi" in res_hi["trace"]
        assert "44,982 रुपये" in res_hi["spoken_text"]


@pytest.mark.asyncio
async def test_doctor_agent_llm_failure_fallback():
    # Provider fails with Quota or Network error
    class FailingProvider(LLMProvider):
        @property
        def provider_name(self) -> str:
            return "failing_provider"

        @property
        def is_configured(self) -> bool:
            return True

        @property
        def active_model(self) -> str:
            return "failing-model"

        async def chat_complete(self, messages, temperature=0.2, max_tokens=1024, timeout=15.0):
            raise LLMQuotaExceededError("Rate limit 429 exceeded on upstream", provider="failing_provider", status_code=429)

        async def chat_with_tools(self, messages, tools=None, tool_choice="auto", temperature=0.2, max_tokens=1024, timeout=15.0):
            raise LLMQuotaExceededError("Rate limit 429 exceeded on upstream", provider="failing_provider", status_code=429)

    agent = DoctorAdvisorAgent(api_key="mock_key")
    agent._llm = FailingProvider()

    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(
            db,
            query="What are today's sales figures?",
            merchant_id="merch_atlas_travel"
        )

        # Must not raise exception, must seamlessly fall back to deterministic intelligence
        assert res["gemini_live"] is False
        assert "reasoning_engine:deterministic_intelligence" in res["trace"]
        assert "llm_error_fallback" in str(res["trace"])
        assert "₹" in res["spoken_text"] or "sales" in res["spoken_text"].lower()
        assert res["metrics"]["revenue_paise"] > 0
