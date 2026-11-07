import asyncio, os, time
from services.voice.gnani_stt_client import GnaniSTTClient
from services.voice.gnani_tts_client import GnaniTTSClient
from services.llm.gemini_provider import GeminiProvider
from services.llm.openrouter_provider import OpenRouterProvider
from services.llm.evon_provider import GnaniEvonProvider
from apps.api.core.config import settings

async def audit_apis():
    print("=== LIVE API AUDIT ===")
    
    # 1. TTS Test
    tts = GnaniTTSClient()
    t0 = time.perf_counter()
    res_tts = await tts.synthesize_speech_async(text="ನಮಸ್ಕಾರ, ವ್ಯಾಪಾರ ಮಿತ್ರಕ್ಕೆ ಸುಸ್ವಾಗತ", language="kn")
    t_tts = round(time.perf_counter() - t0, 3)
    audio_bytes = res_tts.get("audio_bytes", b"")
    print(f"1. Gnani Timbre TTS: success={res_tts.get('success')} is_mock={res_tts.get('is_mock')} is_fallback={res_tts.get('is_fallback')} latency={t_tts}s audio_bytes={len(audio_bytes)}")

    # 2. STT Test (using the audio produced by Timbre!)
    if audio_bytes:
        stt = GnaniSTTClient()
        t0 = time.perf_counter()
        res_stt = await stt.transcribe_audio_async(
            audio_bytes,
            filename="test.wav",
            content_type="audio/wav",
            language_code="kn",
            format_type="codemix"
        )
        t_stt = round(time.perf_counter() - t0, 3)
        tr = res_stt.get("transcript") or res_stt.get("text", "")
        print(f"2. Gnani Prisma STT: success={res_stt.get('success')} is_mock={res_stt.get('is_mock')} latency={t_stt}s transcript='{tr}'")
    else:
        print("2. Gnani Prisma STT: Skipped (no audio bytes)")

    # 3. Gemini Provider
    gem = GeminiProvider()
    print(f"3. Gemini Provider: configured={gem.is_configured} model={gem.active_model}")
    if gem.is_configured:
        t0 = time.perf_counter()
        try:
            r = await gem.chat_complete([{"role": "user", "content": "Hello, reply with only 'OK'"}])
            print(f"   Gemini Live Result: content='{r.content.strip()}' latency={round(time.perf_counter() - t0, 3)}s")
        except Exception as e:
            print(f"   Gemini Live Error: {type(e).__name__}: {str(e)[:120]}")

    # 4. OpenRouter Provider
    opr = OpenRouterProvider()
    print(f"4. OpenRouter Provider: configured={opr.is_configured} model={opr.active_model}")
    if opr.is_configured:
        t0 = time.perf_counter()
        try:
            r = await opr.chat_complete([{"role": "user", "content": "Hello, reply with only 'OK'"}])
            print(f"   OpenRouter Live Result: content='{r.content.strip()}' latency={round(time.perf_counter() - t0, 3)}s")
        except Exception as e:
            print(f"   OpenRouter Live Error: {type(e).__name__}: {str(e)[:120]}")

    # 5. Evon Provider
    evon = GnaniEvonProvider()
    print(f"5. Gnani Evon Provider: configured={evon.is_configured} model={evon.active_model}")
    if evon.is_configured:
        t0 = time.perf_counter()
        try:
            r = await evon.chat_complete([{"role": "user", "content": "Hello"}])
            print(f"   Evon Live Result: content='{r.content.strip()}' latency={round(time.perf_counter() - t0, 3)}s")
        except Exception as e:
            print(f"   Evon Live Error: {type(e).__name__}: {str(e)[:120]}")

if __name__ == "__main__":
    asyncio.run(audit_apis())
