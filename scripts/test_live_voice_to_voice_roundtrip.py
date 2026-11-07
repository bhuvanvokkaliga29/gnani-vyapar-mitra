"""End-to-End Live Voice-to-Voice Roundtrip Verification (Prisma STT v3.0 + Gemini + Timbre TTS v3.0)."""

import sys, os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import io
import time
import httpx
from apps.api.core.config import settings
from services.voice.gnani_stt_client import GnaniSTTClient
from services.voice.gnani_tts_client import GnaniTTSClient
from services.agent.doctor_advisor import DoctorAdvisorAgent, prepare_spoken_response
from apps.api.core.database import AsyncSessionLocal

TEST_SCENARIOS = [
    {
        "name": "English Sales Inquiry",
        "input_text": "How are my sales today?",
        "lang": "en",
        "expected_intent": "DAILY_SALES",
        "tool_expected": True
    },
    {
        "name": "Kannada Greeting & Chit-chat",
        "input_text": "ನಮಸ್ಕಾರ, ಹೇಗಿದ್ದೀರಿ?",
        "lang": "kn",
        "expected_intent": "GREETING",
        "tool_expected": False
    },
    {
        "name": "English Casual WhatsApp Mention",
        "input_text": "I sent a WhatsApp message yesterday.",
        "lang": "en",
        "expected_intent": "CASUAL_MENTION",
        "tool_expected": False
    },
    {
        "name": "Hindi Business Profit Question",
        "input_text": "मुनाफा कम क्यों है?",
        "lang": "hi",
        "expected_intent": "PROFIT_LOW_DIAGNOSIS",
        "tool_expected": False
    }
]

async def run_voice_to_voice():
    print("="*65)
    print("LIVE VOICE-TO-VOICE PIPELINE AUDIT (PRISMA v3.0 ➔ GEMINI ➔ TIMBRE v3.0)")
    print("="*65)

    tts_client = GnaniTTSClient()
    stt_client = GnaniSTTClient()
    advisor = DoctorAdvisorAgent()

    for idx, sc in enumerate(TEST_SCENARIOS, 1):
        print(f"\n--- Scenario [{idx}/4]: {sc['name']} ---")
        t_start = time.perf_counter()

        # Step 1: Synthesize voice query via Gnani Timbre
        t0 = time.perf_counter()
        synth_res = await tts_client.synthesize_speech_async(
            text=sc["input_text"],
            language=sc["lang"],
            speed=1.0
        )
        t_synth = round(time.perf_counter() - t0, 3)
        audio_bytes = synth_res.get("audio_bytes", b"")
        is_tts_fallback = synth_res.get("is_fallback", False)
        print(f"1. Timbre TTS Generator : {len(audio_bytes)} bytes WAV in {t_synth}s (Fallback: {is_tts_fallback})")

        # Step 2: Ingest audio into Gnani Prisma STT v3.0
        t0 = time.perf_counter()
        stt_res = await stt_client.transcribe_audio_async(
            audio_bytes=audio_bytes,
            filename="input_voice.wav",
            content_type="audio/wav",
            language_code=sc["lang"]
        )
        t_stt = round(time.perf_counter() - t0, 3)
        transcript = stt_res.get("transcript", "")
        stt_conf = stt_res.get("confidence", 0.0)
        is_stt_fallback = stt_res.get("is_fallback", False)
        print(f"2. Prisma STT Transcribe: \"{transcript}\" (Conf: {stt_conf}, Time: {t_stt}s, Fallback: {is_stt_fallback})")

        # Step 3: Reason via DoctorAdvisorAgent (Gemini Flash Lite + BI Tools)
        t0 = time.perf_counter()
        async with AsyncSessionLocal() as db:
            doctor_res = await advisor.answer_merchant_query(
                db=db,
                query=transcript or sc["input_text"],
                merchant_id="merch_atlas_travel",
                preferred_language=sc["lang"]
            )
        t_llm = round(time.perf_counter() - t0, 3)
        spoken_text = doctor_res.get("spoken_text") or ""
        intent = doctor_res.get("intent")
        tools = [tr for tr in doctor_res.get("trace", []) if "tool_executed" in tr]
        engine = next((tr for tr in doctor_res.get("trace", []) if "reasoning_engine" in tr), "unknown")
        print(f"3. Doctor Reasoning    : Intent={intent} | Tools={tools} | Time={t_llm}s")
        print(f"   Engine              : {engine}")
        print(f"   Spoken Reply        : \"{spoken_text}\"")

        # Step 4: Synthesize Spoken Response via Gnani Timbre
        t0 = time.perf_counter()
        clean_spoken = prepare_spoken_response(spoken_text)
        reply_tts = await tts_client.synthesize_speech_async(
            text=clean_spoken,
            language=sc["lang"],
            speed=1.0
        )
        t_reply_tts = round(time.perf_counter() - t0, 3)
        reply_audio = reply_tts.get("audio_bytes", b"")
        total_time = round(time.perf_counter() - t_start, 3)
        print(f"4. Timbre Spoken Audio : {len(reply_audio)} bytes in {t_reply_tts}s")
        print(f"   Total Roundtrip Latency: {total_time}s")
        
        # Validation checks
        has_hashtags = "#" in spoken_text
        print(f"   Hashtag Leakage Check: {'❌ FAILED' if has_hashtags else '✅ CLEAN (0 Hashtags)'}")

if __name__ == "__main__":
    asyncio.run(run_voice_to_voice())

