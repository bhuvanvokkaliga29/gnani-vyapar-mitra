"""Unit and Integration Tests for Vyapar Mitra Voice & Doctor Subsystem."""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.database import AsyncSessionLocal
from services.commerce.business_intelligence import BusinessIntelligenceService, VASTRAM_MINIMUM_MARGIN_FLOOR_PERCENT
from services.voice.gnani_stt_client import GnaniSTTClient
from services.voice.gnani_tts_client import GnaniTTSClient
from services.agent.doctor_advisor import DoctorAdvisorAgent


@pytest.fixture
def api_client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Business Intelligence Deterministic Calculations
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_business_intelligence_daily_sales():
    async with AsyncSessionLocal() as db:
        daily = await BusinessIntelligenceService.get_daily_sales(db, "merch_atlas_travel")
        assert daily is not None
        assert daily["total_orders"] >= 18
        assert daily["revenue_paise"] > 0
        assert "₹" in daily["revenue_formatted"]
        assert daily["gross_margin_percent"] > 0
        assert "WHATSAPP" in daily["channels"]


@pytest.mark.asyncio
async def test_business_intelligence_inventory_health():
    async with AsyncSessionLocal() as db:
        inv = await BusinessIntelligenceService.get_inventory_health(db, "merch_atlas_travel")
        assert inv is not None
        assert inv["total_products_count"] >= 64
        assert inv["dead_stock_count"] >= 2
        assert inv["total_trapped_capital_paise"] > 0
        assert inv["annual_holding_cost_paise"] > 0


@pytest.mark.asyncio
async def test_business_intelligence_profit_and_margin_floor():
    assert VASTRAM_MINIMUM_MARGIN_FLOOR_PERCENT == Decimal("25.00")
    async with AsyncSessionLocal() as db:
        profit = await BusinessIntelligenceService.get_profit_and_margin_summary(db, "merch_atlas_travel")
        assert profit["gross_margin_percent"] >= 25.0
        assert profit["is_above_policy_floor"] is True


# -----------------------------------------------------------------------------
# 2. Gnani Voice Clients
# -----------------------------------------------------------------------------

def test_gnani_stt_format_normalization():
    from services.voice.gnani_stt_client import normalize_format
    # Supported values
    assert normalize_format("codemix") == "codemix"
    assert normalize_format("transcribe") == "transcribe"
    assert normalize_format("verbatim") == "verbatim"
    assert normalize_format("transliterate") == "transliterate"
    
    # Hyphenated & code-mixed variations
    assert normalize_format("code-mix") == "codemix"
    assert normalize_format("code_mix") == "codemix"
    assert normalize_format("codemixed") == "codemix"
    assert normalize_format("kanglish") == "codemix"
    
    # Omission & empty
    assert normalize_format(None) is None
    assert normalize_format("") is None
    assert normalize_format("omit") is None
    assert normalize_format("none") is None
    
    # Fallback to safe default codemix
    assert normalize_format("some_other_value") == "codemix"


@pytest.mark.asyncio
async def test_gnani_stt_client_validation():
    client = GnaniSTTClient()
    # Empty audio should be cleanly rejected
    res = await client.transcribe_audio_async(b"")
    assert res["success"] is False
    assert "empty" in res["error"].lower()


@pytest.mark.asyncio
async def test_gnani_tts_client_validation():
    client = GnaniTTSClient()
    # Empty text should be cleanly rejected
    res = await client.synthesize_speech_async("")
    assert res["success"] is False
    assert "empty" in res["error"].lower()


@pytest.mark.asyncio
async def test_gnani_tts_pcm_to_wav_wrapping():
    # Verify that raw PCM is wrapped in valid RIFF/WAVE header
    raw_pcm = b"\x00" * 4800
    wav_bytes = GnaniTTSClient._pcm_to_wav(raw_pcm, sample_rate=24000, channels=1)
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:16]
    import wave, io
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getframerate() == 24000
        assert wf.getnchannels() == 1


# -----------------------------------------------------------------------------
# 3. Doctor Advisor Intent & Language Classification
# -----------------------------------------------------------------------------

def test_doctor_language_detection():
    advisor = DoctorAdvisorAgent()
    # Kannada Unicode
    assert advisor._detect_language("ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?") == "kn"
    # Romanized Kannada
    assert advisor._detect_language("Ivattu sales eshtu?") == "kn"
    # Hindi Devanagari
    assert advisor._detect_language("आज की बिक्री कितनी है?") == "hi"
    # English
    assert advisor._detect_language("What is my actual profit today?") == "en"


def test_doctor_intent_classification():
    advisor = DoctorAdvisorAgent()
    assert advisor._classify_intent("ivattu sales eshtu?") == "DAILY_SALES"
    assert advisor._classify_intent("which product gives me the highest profit?") == "PROFIT_SUMMARY"
    assert advisor._classify_intent("which products are moving slowly?") == "DEAD_STOCK"
    assert advisor._classify_intent("what should i reorder right now?") == "REORDER_ALERT"
    assert advisor._classify_intent("is whatsapp or amazon better for my business?") == "CHANNEL_PERFORMANCE"


# -----------------------------------------------------------------------------
# 4. API Endpoints
# -----------------------------------------------------------------------------

def test_doctor_query_api_endpoint(api_client):
    res = api_client.post("/api/v1/doctor/query", json={
        "merchant_id": "merch_atlas_travel",
        "query": "Ivattu sales eshtu?",
        "synthesize_audio": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["intent"] == "DAILY_SALES"
    assert data["language"] == "kn"
    assert len(data["spoken_text"]) > 0
    assert "DAILY_SALES" in str(data["trace"])


@pytest.mark.asyncio
async def test_doctor_gemini_path_distinction():
    from unittest.mock import AsyncMock
    # 1. Unconfigured Gemini must use deterministic intelligence
    advisor_no_gemini = DoctorAdvisorAgent(api_key="")
    assert advisor_no_gemini.is_gemini_configured is False
    async with AsyncSessionLocal() as db:
        res_det = await advisor_no_gemini.answer_merchant_query(db, "What are today's sales?", "merch_atlas_travel")
        assert res_det["gemini_live"] is False
        assert "reasoning_engine:deterministic_intelligence" in res_det["trace"]

    # 2. Configured Gemini must genuinely invoke Gemini reasoning
    advisor_with_gemini = DoctorAdvisorAgent(api_key="real_configured_gemini_key")
    # Override api_key directly
    advisor_with_gemini.api_key = "real_configured_gemini_key"
    mock_gemini_reply = {
        "spoken_reply": "Gemini live spoken analysis for Vastram.",
        "detailed_advice": "Detailed points from Google Gemini.",
        "recommended_action": None
    }
    advisor_with_gemini._call_gemini_advisor = AsyncMock(return_value=mock_gemini_reply)
    async with AsyncSessionLocal() as db:
        res_gem = await advisor_with_gemini.answer_merchant_query(db, "What are today's sales?", "merch_atlas_travel")
        assert res_gem["gemini_live"] is True
        assert res_gem["spoken_text"] == "Gemini live spoken analysis for Vastram."
        assert "reasoning_engine:google_gemini_live" in res_gem["trace"]


def test_callback_request_api_endpoint(api_client):
    res = api_client.post("/api/v1/doctor/callback", json={
        "merchant_id": "merch_atlas_travel",
        "phone_number": "+919113960498",
        "preferred_language": "kn",
        "topic": "SALES_SUMMARY",
        "reason": "Need sales walkthrough"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["callback_id"].startswith("cb_")


def test_doctor_action_approval_api_endpoint(api_client):
    res = api_client.post("/api/v1/doctor/action/approve", json={
        "merchant_id": "merch_atlas_travel",
        "action_type": "CLEARANCE_BUNDLE",
        "action_title": "Approve Executive Summer Duo Bundle",
        "payload": {"primary_sku": "VAST-SH-03", "secondary_sku": "VAST-TR-01"}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "EXECUTED"
    assert data["approval_id"].startswith("appr_")

