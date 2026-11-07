import os
import sys
import time
import json
import asyncio
import wave
import io
import httpx
from dotenv import load_dotenv

load_dotenv()

GNANI_API_KEY = os.getenv("GNANI_API_KEY")
BACKEND_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = "scratch/voice_quality_tests"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEST_SCENARIOS = [
    {
        "id": "test_1_kannada_greeting",
        "name": "Kannada Native Greeting",
        "input_text": "ನಮಸ್ಕಾರ, ಹೇಗಿದ್ದೀರಿ?",
        "lang": "kn",
        "expected_intent": "GREETING",
        "voice": "Lakshmi",
        "category": "Native Regional"
    },
    {
        "id": "test_2_kannada_sales",
        "name": "Kannada Business Sales",
        "input_text": "ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?",
        "lang": "kn",
        "expected_intent": "DAILY_SALES",
        "voice": "Lakshmi",
        "category": "Native Regional BI"
    },
    {
        "id": "test_3_hindi_casual",
        "name": "Hindi Casual Conversation",
        "input_text": "नमस्ते, आप कैसे हैं? आज मौसम बहुत अच्छा है।",
        "lang": "hi",
        "expected_intent": "GREETING",
        "voice": "Lakshmi",
        "category": "Native Regional"
    },
    {
        "id": "test_4_hindi_profit",
        "name": "Hindi Profit Diagnostic",
        "input_text": "मुनाफा कम क्यों है?",
        "lang": "hi",
        "expected_intent": "PROFIT_LOW_DIAGNOSIS",
        "voice": "Lakshmi",
        "category": "Native Regional BI"
    },
    {
        "id": "test_5_english_sales_accuracy",
        "name": "English Sales Accuracy (Seized vs Sales Test)",
        "input_text": "How are my sales today?",
        "lang": "en",
        "expected_intent": "DAILY_SALES",
        "voice": "Lakshmi",
        "category": "Acoustic Accuracy"
    },
    {
        "id": "test_6_english_casual_whatsapp",
        "name": "English Casual WhatsApp Mention",
        "input_text": "I sent a WhatsApp message yesterday to my regular customers.",
        "lang": "en",
        "expected_intent": "CASUAL_MENTION",
        "voice": "Lakshmi",
        "category": "Anti-Marketing Guardrail"
    },
    {
        "id": "test_7_kannada_english_mixed",
        "name": "Kannada-English Code-Mixed",
        "input_text": "Ivattu sales eshtu? And which product is moving slowly?",
        "lang": "kn",
        "expected_intent": "DAILY_SALES",
        "voice": "Lakshmi",
        "category": "Code-Mixed"
    },
    {
        "id": "test_8_hindi_english_mixed",
        "name": "Hindi-English Code-Mixed",
        "input_text": "WhatsApp channel pe margin kaisa hai?",
        "lang": "hi",
        "expected_intent": "CHANNEL_PERFORMANCE",
        "voice": "Lakshmi",
        "category": "Code-Mixed"
    },
    {
        "id": "test_9_product_stock_followup",
        "name": "SKU Follow-up Pronoun Resolution",
        "input_text": "How much stock is available for the pure olive linen shirt?",
        "lang": "en",
        "expected_intent": "PRODUCT_STOCK_QUERY",
        "voice": "Lakshmi",
        "category": "Multi-turn Focus"
    }
]

async def run_voice_acceptance_suite():
    print("=" * 80)
    print("VYAPAR MITRA — REAL-WORLD VOICE QUALITY & ACCEPTANCE AUDIT SUITE")
    print("Testing 48kHz Timbre v3.0, Prisma STT v3.0, Gemini Reasoning, Latency & Emotion")
    print("=" * 80)

    results = []

    async with httpx.AsyncClient(timeout=35.0) as client:
        for idx, sc in enumerate(TEST_SCENARIOS, 1):
            print(f"\n[{idx}/{len(TEST_SCENARIOS)}] Executing Scenario: {sc['name']} ({sc['lang']})")
            print(f"     Prompt: '{sc['input_text']}'")
            
            # 1. Synthesize natural human-like voice audio for the prompt
            t0_prompt_tts = time.perf_counter()
            tts_url = "https://api.vachana.ai/api/v1/tts/inference"
            tts_headers = {"X-API-Key-ID": GNANI_API_KEY, "Content-Type": "application/json"}
            tts_payload = {
                "text": sc["input_text"],
                "voice": sc["voice"],
                "model": "timbre-v3.0",
                "language": sc["lang"],
                "speed": 1.0,
                "audio_config": {
                    "encoding": "linear_pcm",
                    "container": "wav",
                    "num_channels": 1,
                    "sample_rate": 16000,  # 16kHz input audio for microphone simulation
                    "sample_width": 2
                }
            }
            res_prompt_tts = await client.post(tts_url, headers=tts_headers, json=tts_payload)
            t_prompt_tts = round(time.perf_counter() - t0_prompt_tts, 3)
            prompt_wav = res_prompt_tts.content
            prompt_wav_path = os.path.join(OUTPUT_DIR, f"{sc['id']}_prompt.wav")
            with open(prompt_wav_path, "wb") as f:
                f.write(prompt_wav)

            # 2. Stage 1: Prisma STT Transcription via backend
            t0_stt = time.perf_counter()
            stt_res = await client.post(
                f"{BACKEND_URL}/api/v1/voice/transcribe",
                files={"audio_file": ("mic.wav", prompt_wav, "audio/wav")},
                data={"language_code": "indic-auto", "format_type": "codemix"}
            )
            t_stt = round(time.perf_counter() - t0_stt, 3)
            stt_data = stt_res.json()
            transcript = stt_data.get("transcript", "")
            detected_lang = stt_data.get("detected_language_code", "")
            confidence = stt_data.get("confidence", 0.0)
            
            print(f"     ➔ STT: '{transcript}' [Lang: {detected_lang}, Conf: {confidence}, Time: {t_stt}s]")

            # 3. Stage 2: Doctor Conversational Reasoning & Tool Invocation
            t0_doctor = time.perf_counter()
            doc_res = await client.post(
                f"{BACKEND_URL}/api/v1/doctor/query",
                json={
                    "merchant_id": "merch_atlas_travel",
                    "query": transcript or sc["input_text"],
                    "preferred_language": detected_lang.split("-")[0] if detected_lang else sc["lang"],
                    "synthesize_audio": True
                }
            )
            t_doctor = round(time.perf_counter() - t0_doctor, 3)
            doc_data = doc_res.json()
            
            intent = doc_data.get("intent", "UNKNOWN")
            spoken_reply = doc_data.get("spoken_text", "")
            audio_info = doc_data.get("audio", {})
            audio_b64 = audio_info.get("audio_base64", "")
            voice_used = audio_info.get("voice", "")
            traces = doc_data.get("trace", [])

            # 4. Stage 3: Analyze Spoken Audio Output
            t_audio_dur = 0.0
            sample_rate = 48000
            num_channels = 1
            response_wav_path = None
            if audio_b64 and "base64," in audio_b64:
                import base64
                b64_data = audio_b64.split("base64,")[1]
                response_wav_bytes = base64.b64decode(b64_data)
                response_wav_path = os.path.join(OUTPUT_DIR, f"{sc['id']}_response.wav")
                with open(response_wav_path, "wb") as f:
                    f.write(response_wav_bytes)
                
                try:
                    with wave.open(io.BytesIO(response_wav_bytes), "rb") as wf:
                        sample_rate = wf.getframerate()
                        num_channels = wf.getnchannels()
                        t_audio_dur = round(wf.getnframes() / sample_rate, 2)
                except Exception as e:
                    t_audio_dur = round(len(response_wav_bytes) / (48000 * 2), 2)

            total_roundtrip = round(t_stt + t_doctor, 3)

            # Quality metrics
            hashtag_count = spoken_reply.count("#")
            has_rupee_symbol = "₹" in spoken_reply
            emotion_detected = None
            for emo in ["<excited>", "<sigh>", "<pauses>", "<slow>", "<laugh>"]:
                if emo in spoken_reply:
                    emotion_detected = emo
                    break

            print(f"     ➔ Intent: {intent} (Expected: {sc['expected_intent']})")
            print(f"     ➔ Emotion Tag: {emotion_detected or 'Natural Cadence'}")
            print(f"     ➔ Spoken: \"{spoken_reply[:120]}...\"")
            print(f"     ➔ Spoken Audio: {t_audio_dur}s at {sample_rate}Hz (Latency: {t_doctor}s, Total: {total_roundtrip}s)")
            print(f"     ➔ Quality Flags: Hashtags={hashtag_count}, Raw ₹={has_rupee_symbol}")

            results.append({
                "scenario": sc,
                "stt": {
                    "transcript": transcript,
                    "detected_lang": detected_lang,
                    "confidence": confidence,
                    "latency_sec": t_stt
                },
                "reasoning": {
                    "intent": intent,
                    "spoken_text": spoken_reply,
                    "traces": traces,
                    "latency_sec": t_doctor
                },
                "audio": {
                    "sample_rate": sample_rate,
                    "duration_sec": t_audio_dur,
                    "voice": voice_used,
                    "emotion_tag": emotion_detected,
                    "hashtag_clean": hashtag_count == 0,
                    "currency_words_clean": not has_rupee_symbol
                },
                "total_latency_sec": total_roundtrip
            })

    # Summary table
    print("\n" + "=" * 80)
    print("FINAL VOICE QUALITY ACCEPTANCE BENCHMARK RESULTS")
    print("=" * 80)
    print(f"{'Scenario':<35} | {'Intent':<18} | {'Lang':<6} | {'STT(s)':<7} | {'TTS Dur':<8} | {'Emotion':<10} | {'Status':<6}")
    print("-" * 95)
    for r in results:
        sc_name = r["scenario"]["name"][:35]
        intent = r["reasoning"]["intent"][:18]
        lang = r["stt"]["detected_lang"][:6]
        stt_t = f"{r['stt']['latency_sec']:.2f}s"
        dur_t = f"{r['audio']['duration_sec']:.1f}s"
        emo = r["audio"]["emotion_tag"] or "Natural"
        status = "PASS" if r["audio"]["hashtag_clean"] and r["audio"]["currency_words_clean"] else "WARN"
        print(f"{sc_name:<35} | {intent:<18} | {lang:<6} | {stt_t:<7} | {dur_t:<8} | {emo:<10} | {status:<6}")

    out_json = os.path.join(OUTPUT_DIR, "voice_quality_acceptance_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nFull structured results saved to: {out_json}")

if __name__ == "__main__":
    asyncio.run(run_voice_acceptance_suite())

