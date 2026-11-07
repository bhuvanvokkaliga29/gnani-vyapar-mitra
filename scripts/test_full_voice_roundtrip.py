import asyncio
from fastapi.testclient import TestClient
from apps.api.main import app
from services.voice.gnani_tts_client import GnaniTTSClient

async def test_full_roundtrip():
    # 1. Synthesize real Kannada question
    tts = GnaniTTSClient()
    t_synth = await tts.synthesize_speech_async("ನನ್ನ ವ್ಯಾಪಾರ ಹೇಗಿದೆ?", language="kn")
    wav_bytes = t_synth["audio_bytes"]
    print(f"1. Synthesized audio: {len(wav_bytes)} bytes")

    # 2. Upload to FastAPI /api/v1/voice/transcribe
    client = TestClient(app)
    stt_res = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("merchant_audio.wav", wav_bytes, "audio/wav")},
        data={"language_code": "indic-auto", "format_type": "codemix"}
    )
    print(f"2. Transcribe endpoint: status={stt_res.status_code}")
    print(f"   Response JSON: {stt_res.json()}")
    transcript = stt_res.json().get("transcript", "")

    # 3. Query Doctor Advisor with transcript
    doc_res = client.post(
        "/api/v1/doctor/query",
        json={
            "merchant_id": "merch_atlas_travel",
            "query": transcript,
            "preferred_language": "kn",
            "synthesize_audio": True
        }
    )
    print(f"3. Doctor query: status={doc_res.status_code}")
    doc_data = doc_res.json()
    print(f"   Spoken reply: \"{doc_data.get('spoken_text')}\"")
    audio_obj = doc_data.get("audio") or {}
    print(f"   Audio generated: length={len(audio_obj.get('audio_base64', ''))} chars, voice={audio_obj.get('voice')}")

if __name__ == "__main__":
    asyncio.run(test_full_roundtrip())

