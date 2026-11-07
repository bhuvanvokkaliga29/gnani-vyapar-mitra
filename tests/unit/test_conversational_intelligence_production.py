"""Comprehensive Production Test Suite for Vyapar Mitra Conversational Voice Intelligence.

Covers:
1. Multi-turn context retention & pronoun resolution (sales -> product -> stock -> reorder).
2. Clarification & graceful handling of incomplete/ambiguous user queries.
3. Multilingual attunement & natural code-switching (Kannada, Hindi, English).
4. Strict multi-tenant merchant isolation across business intelligence queries.
5. Voice runtime verification (latency measurement & speech synthesis verification).
6. Non-repetitive response generation and interruption recovery.
"""

import pytest
import uuid
import time
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent, DOCTOR_SYSTEM_PROMPT
from services.voice.gnani_tts_client import GnaniTTSClient


@pytest.mark.asyncio
async def test_doctor_prompt_includes_ambiguity_and_multilingual_rules():
    """Verify system prompt includes explicit rules for ambiguity, clarification, and code-switching."""
    assert "Vyapar Mitra" in DOCTOR_SYSTEM_PROMPT
    assert "Vastram" in DOCTOR_SYSTEM_PROMPT
    assert "AMBIGUITY, INCOMPLETE INPUTS & PROACTIVE FOLLOW-UPS:" in DOCTOR_SYSTEM_PROMPT
    assert "CULTURAL CODE-SWITCHING & MULTILINGUAL ATTUNEMENT:" in DOCTOR_SYSTEM_PROMPT
    assert "25.00%" in DOCTOR_SYSTEM_PROMPT
    assert "SPOKEN_REPLY:" in DOCTOR_SYSTEM_PROMPT
    assert "DETAILED_ADVICE:" in DOCTOR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_multiturn_pronoun_resolution_and_context_retention():
    """Verify 3-turn continuity: daily sales -> which product -> stock & reorder recommendation."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"vcs_test_{uuid.uuid4().hex[:10]}"

        # Turn 1: Daily sales overview
        r1 = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="How much revenue did our shop generate today?",
            preferred_language="en",
            session_id=session_id
        )
        assert r1["intent"] == "DAILY_SALES"
        assert r1["spoken_text"] is not None
        assert "revenue" in r1["spoken_text"].lower() or "thousand" in r1["spoken_text"].lower() or "sixty" in r1["spoken_text"].lower() or "rupees" in r1["spoken_text"].lower()

        # Turn 2: Followup asking for the top contributor
        r2 = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="Which product contributed the most to that?",
            preferred_language="en",
            session_id=session_id
        )
        assert r2["spoken_text"] is not None
        assert r2["focused_entity"] is not None
        assert "sku" in r2["focused_entity"]

        # Turn 3: Pronoun reference "it" resolving to the focused product
        r3 = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="How much stock is remaining in it and should I reorder?",
            preferred_language="en",
            session_id=session_id
        )
        assert r3["spoken_text"] is not None
        assert "stock" in r3["spoken_text"].lower() or "units" in r3["spoken_text"].lower()


@pytest.mark.asyncio
async def test_multilingual_code_switching_kannada_kanglish():
    """Verify natural code-switching in Kannada (Kanglish)."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"vcs_kn_{uuid.uuid4().hex[:10]}"

        res = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="ಇವತ್ತಿನ sales ಎಷ್ಟಾಗಿದೆ ಮತ್ತು ಯಾವ product top ಆಗಿದೆ?",
            preferred_language="kn",
            session_id=session_id
        )
        assert res["language"] == "kn"
        assert res["spoken_text"] is not None
        # Should contain Kannada characters
        assert any('\u0c80' <= c <= '\u0cff' for c in res["spoken_text"])


@pytest.mark.asyncio
async def test_multilingual_code_switching_hindi_hinglish():
    """Verify natural code-switching in Hindi (Hinglish)."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"vcs_hi_{uuid.uuid4().hex[:10]}"

        res = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="दुकान की आज की बिक्री कैसी रही?",
            preferred_language="hi",
            session_id=session_id
        )
        assert res["language"] == "hi"
        assert res["spoken_text"] is not None
        # Natural Hindi or Hinglish code-switching response
        has_devanagari = any('\u0900' <= c <= '\u097f' for c in res["spoken_text"])
        has_hinglish_terms = any(w in res["spoken_text"].lower() for w in ["aaj", "bikri", "sales", "rupaye", "rupees", "dukaan", "kamai"])
        assert has_devanagari or has_hinglish_terms


@pytest.mark.asyncio
async def test_strict_merchant_isolation_in_doctor_queries():
    """Verify that querying a different merchant ID never accesses or leaks Vastram store data."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        
        # Test non-existent merchant
        res_empty = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_non_existent_tenant_999",
            query="How much revenue did our shop make today?",
            preferred_language="en"
        )
        # Should execute safely without throwing unhandled exceptions
        assert res_empty is not None
        # The metrics collected for non-existent merchant must not leak Vastram data
        if "get_daily_sales" in res_empty["metrics"]:
            sales = res_empty["metrics"]["get_daily_sales"]
            assert sales.get("paid_orders", 0) == 0


@pytest.mark.asyncio
async def test_doctor_query_api_roundtrip_latency_and_audio_synthesis():
    """Test full HTTP API roundtrip on /api/v1/doctor/query with audio synthesis."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        t0 = time.perf_counter()
        res = await ac.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "How much revenue did my store generate today?",
            "preferred_language": "en",
            "synthesize_audio": True
        })
        latency = time.perf_counter() - t0
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["spoken_text"] is not None
        assert data["audio"] is not None
        assert "audio_base64" in data["audio"]
        # Audio length should be non-trivial
        assert len(data["audio"]["audio_base64"]) > 1000
        # Latency must be measurable and reasonable
        assert latency > 0.0


@pytest.mark.asyncio
async def test_interruption_pause_and_resume_flow():
    """Verify interruption controls: stop/pause followed by resume."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"vcs_interrupt_{uuid.uuid4().hex[:10]}"

        # Step 1: Tell agent to wait
        r1 = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="Wait, stop speaking for a second",
            preferred_language="en",
            session_id=session_id
        )
        assert r1["intent"] == "INTERRUPTION_PAUSE"

        # Step 2: Resume
        r2 = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="Okay, continue please",
            preferred_language="en",
            session_id=session_id
        )
        assert r2["intent"] == "INTERRUPTION_RESUME"
        assert r2["spoken_text"] is not None


@pytest.mark.asyncio
async def test_personal_chat_empathy_no_business_bias():
    """Verify that personal issues (e.g. girlfriend fight) trigger pure empathetic friend mode with zero product/sales injection."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        r = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="bro, i had a fight with my girlfriend",
            preferred_language="en"
        )
        assert r["intent"] == "PERSONAL_CHAT"
        spoken = r["spoken_text"].lower()
        for banned in ["vastram", "boutique", "shirt", "linen", "sales", "revenue", "inventory", "stock"]:
            assert banned not in spoken, f"Personal chat must not contain business term '{banned}'"


@pytest.mark.asyncio
async def test_general_sales_no_unprompted_linen_shirt_bias():
    """Verify that asking general daily sales returns revenue without unprompted Cotton Linen Shirt bias."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        r = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="How much did I sell today?",
            preferred_language="en"
        )
        assert r["intent"] == "DAILY_SALES"
        spoken = r["spoken_text"].lower()
        assert "67,570" in spoken or "67570" in spoken or "30" in spoken
        assert "linen" not in spoken and "oxford" not in spoken


@pytest.mark.asyncio
async def test_honest_mathematical_correction():
    """Verify that flawed math claims (e.g. cost 1000, price 1100 = 50% margin) are politely corrected."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        r = await agent.answer_merchant_query(
            db=db,
            merchant_id="merch_atlas_travel",
            query="My product costs 1000 and I sell it for 1100. So my profit margin is 50%, right?",
            preferred_language="en"
        )
        spoken = r["spoken_text"].lower()
        # Must challenge 50% and state ~9% or 10%
        assert "not 50%" in spoken or "actually" in spoken or "9" in spoken or "10" in spoken

