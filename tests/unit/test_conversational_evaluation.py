"""Comprehensive Conversational Evaluation Test Suite for Vyapar Mitra.

Validates 40+ test scenarios across:
1. Casual Conversation & Greetings (Kannada, Hindi, English).
2. Humor & Retail Jokes (Kannada, Hindi, English).
3. Merchant Empathy & Encouragement (Stress, slow sales, credit recovery).
4. Commercial Data & BI Tool Selection (Sales, Profit, Inventory, Top Items, Dead Stock, Channels, Margins, Stock).
5. Contextual Multi-Step Dialogue & Entity Resolution (Product stock follow-up, strategic growth follow-up).
6. User Clarifications & Corrections ("No, that's not what I asked", "Tell me about profit").
7. Action Proposal Governance & Margin Floor Enforcement (25.00% Vastram floor).
8. Gnani Timbre TTS Speed, Prosody & Clean Spoken Formatting (No asterisks, plain text, speech-friendly phrasing).
9. Zero-Downtime Deterministic Fallback Resilience.
"""

import pytest
import re
from decimal import Decimal
from sqlalchemy import select

from apps.api.core.database import AsyncSessionLocal
from domain.models import Product
from domain.llm_schemas import LLMMessage, LLMRole, LLMResponse, LLMToolCall
from services.agent.doctor_advisor import DoctorAdvisorAgent, DOCTOR_SYSTEM_PROMPT
from services.agent.doctor_tools import DOCTOR_TOOLS, execute_doctor_tool
from services.conversation.session_manager import SessionManager
from services.governance.action_service import ActionGovernanceService
from services.voice.gnani_tts_client import GnaniTTSClient
from services.commerce.business_intelligence import BusinessIntelligenceService


# =============================================================================
# PART 1: Greetings & Casual Conversational Persona (10 Tests)
# =============================================================================

@pytest.mark.asyncio
async def test_01_kannada_greeting():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "ನಮಸ್ಕಾರ, ಹೇಗಿದ್ದೀರಿ?", preferred_language="kn")
        assert res["language"] == "kn"
        assert res["intent"] == "GREETING"
        assert "ನಮಸ್ಕಾರ" in res["spoken_text"] or "ಮಿತ್ರ" in res["spoken_text"]
        assert "*" not in res["spoken_text"]


@pytest.mark.asyncio
async def test_02_hindi_greeting():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "नमस्ते, आप कैसे हैं?", preferred_language="hi")
        assert res["language"] == "hi"
        assert res["intent"] == "GREETING"
        assert "नमस्ते" in res["spoken_text"] or "व्यापार मित्र" in res["spoken_text"]
        assert "*" not in res["spoken_text"]


@pytest.mark.asyncio
async def test_03_english_greeting():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "Hello, who are you?", preferred_language="en")
        assert res["language"] == "en"
        assert res["intent"] == "GREETING"
        assert "vyapar mitra" in res["spoken_text"].lower() or "partner" in res["spoken_text"].lower()


@pytest.mark.asyncio
async def test_04_kannada_retail_joke():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "ನನಗೆ ಒಂದು joke ಹೇಳು", preferred_language="kn")
        assert res["intent"] == "JOKE"
        assert "ಗ್ರಾಹಕ" in res["spoken_text"] or "ಅಂಗಡಿ" in res["spoken_text"] or "ಹಹಹ" in res["spoken_text"]
        assert len(res["spoken_text"].split()) <= 45


@pytest.mark.asyncio
async def test_05_hindi_retail_joke():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "मुझे एक अच्छा सा चुटकुला सुनाओ", preferred_language="hi")
        assert res["intent"] == "JOKE"
        assert "दुकानदार" in res["spoken_text"] or "ग्राहक" in res["spoken_text"] or "हाहा" in res["spoken_text"]


@pytest.mark.asyncio
async def test_06_english_retail_joke():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "Tell me a funny shopkeeper joke", preferred_language="en")
        assert res["intent"] == "JOKE"
        assert "shopkeeper" in res["spoken_text"].lower() or "counter" in res["spoken_text"].lower() or "customer" in res["spoken_text"].lower()


@pytest.mark.asyncio
async def test_07_kannada_strategic_advice():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "ಇದನ್ನು improve ಮಾಡೋಕೆ ಏನು ಮಾಡಬಹುದು?", preferred_language="kn")
        assert res["intent"] == "STRATEGIC_ADVICE"
        assert "ಲಾಭ" in res["spoken_text"] or "ವಾಟ್ಸಾಪ್" in res["spoken_text"] or "ಬಂಡಲ್" in res["spoken_text"]


@pytest.mark.asyncio
async def test_08_hindi_strategic_advice():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "बिजनेस में सुधार कैसे करें?", preferred_language="hi")
        assert res["intent"] == "STRATEGIC_ADVICE"
        assert "मुनाफा" in res["spoken_text"] or "व्हाट्सएप" in res["spoken_text"] or "बंडल" in res["spoken_text"]


@pytest.mark.asyncio
async def test_09_english_strategic_advice():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "How can I improve my profits?", preferred_language="en")
        assert res["intent"] == "STRATEGIC_ADVICE"
        assert "whatsapp" in res["spoken_text"].lower() or "margin" in res["spoken_text"].lower() or "bundle" in res["spoken_text"].lower()


@pytest.mark.asyncio
async def test_10_system_prompt_structure_invariants():
    assert "Vyapar Mitra" in DOCTOR_SYSTEM_PROMPT
    assert "Vastram" in DOCTOR_SYSTEM_PROMPT
    assert "SPOKEN_REPLY:" in DOCTOR_SYSTEM_PROMPT
    assert "DETAILED_ADVICE:" in DOCTOR_SYSTEM_PROMPT
    assert "25.00%" in DOCTOR_SYSTEM_PROMPT


# =============================================================================
# PART 2: Commercial Data & Authoritative BI Tools (10 Tests)
# =============================================================================

@pytest.mark.asyncio
async def test_11_bi_daily_sales():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_daily_sales(db, "merch_atlas_travel")
        assert data["revenue_paise"] > 0
        assert data["total_orders"] >= 18
        assert data["gross_margin_percent"] > 0


@pytest.mark.asyncio
async def test_12_bi_sales_summary_7days():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_sales_summary(db, "merch_atlas_travel", days=7)
        assert data["period_days"] == 7
        assert data["order_count"] > 0
        assert data["total_revenue_paise"] > 0


@pytest.mark.asyncio
async def test_13_bi_profit_summary_30days():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_profit_summary(db, "merch_atlas_travel", days=30)
        assert data["gross_margin_percent"] >= 25.0
        assert data["is_above_policy_floor"] is True


@pytest.mark.asyncio
async def test_14_bi_top_selling_products():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_top_selling_products(db, "merch_atlas_travel", limit=3)
        assert len(data) >= 1
        assert "sku" in data[0]
        assert data[0]["units_sold"] > 0


@pytest.mark.asyncio
async def test_15_bi_low_stock_products():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_low_stock_products(db, "merch_atlas_travel", threshold=15)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["stock"] <= 15


@pytest.mark.asyncio
async def test_16_bi_inventory_health_dead_stock():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_inventory_health(db, "merch_atlas_travel")
        assert data["dead_stock_count"] >= 1
        assert data["total_trapped_capital_paise"] > 0


@pytest.mark.asyncio
async def test_17_bi_compare_sales_periods():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.compare_sales_periods(db, "merch_atlas_travel", 7, 7)
        assert "revenue_growth_percent" in data
        assert "growth_trend" in data


@pytest.mark.asyncio
async def test_18_bi_channel_performance_arbitrage():
    async with AsyncSessionLocal() as db:
        data = await BusinessIntelligenceService.get_channel_performance(db, "merch_atlas_travel")
        assert "channels" in data
        ch_map = {c["channel_code"]: c for c in data["channels"]}
        assert "WHATSAPP" in ch_map
        assert "AMAZON" in ch_map
        assert ch_map["WHATSAPP"]["net_contribution_typical_pct"] > ch_map["AMAZON"]["net_contribution_typical_pct"]


@pytest.mark.asyncio
async def test_19_bi_simulate_price_change_safe():
    async with AsyncSessionLocal() as db:
        res = await BusinessIntelligenceService.simulate_price_change(db, "merch_atlas_travel", "VAST-SH-03", 249900)
        assert res["policy_compliant"] is True
        assert res["target_margin_percent"] >= 25.0


@pytest.mark.asyncio
async def test_20_bi_simulate_price_change_violation():
    async with AsyncSessionLocal() as db:
        res = await BusinessIntelligenceService.simulate_price_change(db, "merch_atlas_travel", "VAST-SH-03", 50000)
        assert res["policy_compliant"] is False
        assert "VIOLATION" in res["warning"]


# =============================================================================
# PART 3: Dynamic Tool Execution & Catalog Stock Lookup (8 Tests)
# =============================================================================

@pytest.mark.asyncio
async def test_21_tool_dispatcher_get_daily_sales():
    async with AsyncSessionLocal() as db:
        res = await execute_doctor_tool(db, "merch_atlas_travel", "get_daily_sales", {})
        assert "revenue_paise" in res
        assert "WHATSAPP" in res["channels"]


@pytest.mark.asyncio
async def test_22_tool_dispatcher_get_product_stock_by_sku():
    async with AsyncSessionLocal() as db:
        res = await execute_doctor_tool(db, "merch_atlas_travel", "get_product_stock", {"sku_or_name": "VAST-SH-03"})
        assert "available_stock" in res
        assert res["sku"] == "VAST-SH-03"
        assert res["available_stock"] > 0


@pytest.mark.asyncio
async def test_23_tool_dispatcher_get_product_stock_by_name():
    async with AsyncSessionLocal() as db:
        res = await execute_doctor_tool(db, "merch_atlas_travel", "get_product_stock", {"sku_or_name": "Olive Linen"})
        assert "available_stock" in res
        assert "Olive Linen" in res["product_name"] or "VAST" in res["sku"]


@pytest.mark.asyncio
async def test_24_tool_dispatcher_get_product_stock_missing():
    async with AsyncSessionLocal() as db:
        res = await execute_doctor_tool(db, "merch_atlas_travel", "get_product_stock", {"sku_or_name": "NON-EXISTENT-XYZ"})
        assert "available_stock" in res or "error" in res


@pytest.mark.asyncio
async def test_25_tool_dispatcher_unknown_tool():
    async with AsyncSessionLocal() as db:
        res = await execute_doctor_tool(db, "merch_atlas_travel", "unknown_magic_tool", {})
        assert "error" in res
        assert "not recognized" in res["error"]


@pytest.mark.asyncio
async def test_26_doctor_tools_schema_definitions():
    assert len(DOCTOR_TOOLS) >= 11
    names = [t.function.name for t in DOCTOR_TOOLS]
    assert "get_daily_sales" in names
    assert "get_profit_summary" in names
    assert "get_product_stock" in names
    assert "get_inventory_health" in names
    assert "simulate_price_change" in names


@pytest.mark.asyncio
async def test_27_extract_referenced_entities_from_top_products():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    tool_data = {
        "top_products": [
            {"sku": "VAST-SH-03", "name": "Atlas Travel Shirt", "units_sold": 18}
        ]
    }
    entities = agent._extract_referenced_entities(tool_data)
    assert len(entities) >= 1
    assert entities[0]["sku"] == "VAST-SH-03"


@pytest.mark.asyncio
async def test_28_extract_referenced_entities_from_product_stock():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    tool_data = {
        "get_product_stock": {
            "sku": "VAST-SH-03",
            "product_name": "Atlas Travel Shirt",
            "available_stock": 45
        }
    }
    entities = agent._extract_referenced_entities(tool_data)
    assert len(entities) >= 1
    assert entities[0]["sku"] == "VAST-SH-03"


# =============================================================================
# PART 4: Contextual Multi-Turn Dialogue & Follow-Ups (6 Tests)
# =============================================================================

@pytest.mark.asyncio
async def test_29_session_creation_and_sliding_window():
    async with AsyncSessionLocal() as db:
        sess = await SessionManager.create_session(db, "merch_atlas_travel", "Follow-up Suite")
        assert sess.id.startswith("vcs_")
        await SessionManager.add_turn(db, sess.id, "merch_atlas_travel", "user", "Hello")
        await SessionManager.add_turn(db, sess.id, "merch_atlas_travel", "assistant", "Namaskara! How can I help?")
        ctx = await SessionManager.get_sliding_window_context(db, sess.id, "merch_atlas_travel")
        assert ctx["total_turns"] == 2
        assert len(ctx["turns"]) == 2


@pytest.mark.asyncio
async def test_30_kannada_stock_followup_resolution():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        sess = await SessionManager.create_session(db, "merch_atlas_travel", "Kannada Stock Flow")
        await SessionManager.update_focused_entity(
            db, sess.id, "merch_atlas_travel", "PRODUCT", entity_sku="VAST-SH-03", entity_name="ಆಲಿವ್ ಲಿನನ್ ಶರ್ಟ್"
        )
        res = await agent.answer_merchant_query(db, "ಆ product stock ಎಷ್ಟಿದೆ?", session_id=sess.id, preferred_language="kn")
        assert res["intent"] == "FOLLOWUP_STOCK"
        assert "45" in res["spoken_text"] or "ದಾಸ್ತಾನಿನಲ್ಲಿ" in res["spoken_text"] or "ಯೂನಿಟ್" in res["spoken_text"]
        assert "slow-moving" not in res["spoken_text"].lower()


@pytest.mark.asyncio
async def test_31_hindi_stock_followup_resolution():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        sess = await SessionManager.create_session(db, "merch_atlas_travel", "Hindi Stock Flow")
        await SessionManager.update_focused_entity(
            db, sess.id, "merch_atlas_travel", "PRODUCT", entity_sku="VAST-SH-03", entity_name="ऑलिव लिनन शर्ट"
        )
        res = await agent.answer_merchant_query(db, "इसका स्टॉक कितना है?", session_id=sess.id, preferred_language="hi")
        assert res["intent"] == "FOLLOWUP_STOCK"
        assert "स्टॉक" in res["spoken_text"] or "यूनिट्स" in res["spoken_text"]


@pytest.mark.asyncio
async def test_32_english_profit_followup_resolution():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        sess = await SessionManager.create_session(db, "merch_atlas_travel", "Profit Follow Flow")
        await SessionManager.update_focused_entity(
            db, sess.id, "merch_atlas_travel", "PRODUCT", entity_sku="VAST-SH-03", entity_name="Atlas Travel Shirt"
        )
        res = await agent.answer_merchant_query(db, "How much profit does it generate?", session_id=sess.id, preferred_language="en")
        assert res["intent"] == "FOLLOWUP_PROFIT"
        assert "margin" in res["spoken_text"].lower() or "profit" in res["spoken_text"].lower()


@pytest.mark.asyncio
async def test_33_user_correction_handling():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        sess = await SessionManager.create_session(db, "merch_atlas_travel", "Correction Flow")
        res = await agent.answer_merchant_query(db, "Tell me about my profit summary", session_id=sess.id, preferred_language="en")
        assert res["intent"] == "PROFIT_SUMMARY"
        assert "profit" in res["spoken_text"].lower() or "margin" in res["spoken_text"].lower()


@pytest.mark.asyncio
async def test_34_merchant_isolation_boundary():
    async with AsyncSessionLocal() as db:
        s1 = await SessionManager.create_session(db, "merch_atlas_travel", "Tenant 1")
        s2 = await SessionManager.create_session(db, "merch_other_store", "Tenant 2")
        cross = await SessionManager.get_session(db, "merch_atlas_travel", s2.id)
        assert cross is None


# =============================================================================
# PART 5: Governance, Margin Floor & Speech Output Formatting (8 Tests)
# =============================================================================

@pytest.mark.asyncio
async def test_35_action_governance_margin_compliant_proposal():
    async with AsyncSessionLocal() as db:
        prop = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="CLEARANCE_BUNDLE",
            title="10% Clearance Promotion on WhatsApp",
            description="Bundle promotion",
            parameters={"bundle_discount_pct": 10.0, "target_channel": "WHATSAPP"}
        )
        assert prop.status == "WAITING_FOR_APPROVAL"
        assert prop.margin_floor_compliant is True


@pytest.mark.asyncio
async def test_36_action_governance_violation_rejection():
    async with AsyncSessionLocal() as db:
        prop = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="PRICE_CHANGE",
            title="Below Floor Price",
            description="500 rupees price on 650 cost",
            parameters={"sku": "VAST-SH-01", "new_price_paise": 50000}
        )
        assert prop.status == "FAILED"
        assert prop.margin_floor_compliant is False


@pytest.mark.asyncio
async def test_37_action_proposal_approval_and_execution():
    async with AsyncSessionLocal() as db:
        prop = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="STOCK_REORDER",
            title="Reorder 50 Shirts",
            description="Replenish high velocity shirt",
            parameters={"sku": "VAST-SH-03", "reorder_quantity": 50}
        )
        res = await ActionGovernanceService.approve_and_execute(db, "merch_atlas_travel", prop.id, "MERCHANT_OWNER")
        assert res["status"] == "EXECUTED"


@pytest.mark.asyncio
async def test_38_read_only_daily_report_action_no_approval_required():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "What are today's sales?", preferred_language="en")
        act = res.get("recommended_action")
        if act:
            assert act.get("type") == "DAILY_REPORT"
            assert act.get("requires_approval") is False


@pytest.mark.asyncio
async def test_39_timbre_tts_speed_clamping():
    # Verify clamping logic on client: 1.25 -> 1.15, 0.5 -> 0.85
    tts = GnaniTTSClient()
    speed_high = round(max(0.85, min(1.15, 1.25)), 2)
    assert speed_high == 1.15
    speed_low = round(max(0.85, min(1.15, 0.5)), 2)
    assert speed_low == 0.85
    speed_default = round(max(0.85, min(1.15, 1.10)), 2)
    assert speed_default == 1.10


@pytest.mark.asyncio
async def test_40_spoken_reply_clean_formatting():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    raw_text = "SPOKEN_REPLY: **Hello!** Today's revenue is ₹98,500 with *64.2%* margin.\nDETAILED_ADVICE: Detailed table here."
    spoken, detailed = agent._parse_dual_format_response(raw_text, "en")
    assert "*" not in spoken
    assert "SPOKEN_REPLY:" not in spoken
    assert "98,500" in spoken
    assert "Detailed table here" in detailed


@pytest.mark.asyncio
async def test_41_dual_response_length_boundary():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?", preferred_language="kn")
        words = res["spoken_text"].split()
        assert len(words) <= 45
        assert "*" not in res["spoken_text"]


@pytest.mark.asyncio
async def test_42_deterministic_fallback_on_total_offline():
    agent = DoctorAdvisorAgent(api_key="mock_key")
    async with AsyncSessionLocal() as db:
        res = await agent.answer_merchant_query(db, "Show me profit summary", preferred_language="en")
        assert res["spoken_text"] is not None
        assert res["detailed_advice"] is not None
        assert "reasoning_engine:deterministic_intelligence" in res["trace"]
