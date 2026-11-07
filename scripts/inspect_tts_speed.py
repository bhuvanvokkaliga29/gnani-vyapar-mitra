import httpx
import os
import wave
import io
import numpy as np
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GNANI_API_KEY")
url = "https://api.vachana.ai/api/v1/tts/inference"
headers = {"X-API-Key-ID": api_key, "Content-Type": "application/json"}

text = "Today's sales are doing great with 30 orders bringing in 67,570 rupees, and a strong gross margin of 64.5%. WhatsApp is leading the channel performance."

print(f"Text word count: {len(text.split())} words")
print(f"Text: {text}\n")

for spd in [0.85, 1.0, 1.1, 1.15]:
    payload = {
        "text": text,
        "voice": "Lakshmi",
        "model": "timbre-v3.0",
        "language": "en",
        "speed": spd
    }
    try:
        res = httpx.post(url, headers=headers, json=payload, timeout=20)
        raw = res.content
        samples = len(raw) // 2
        dur_24k = samples / 24000.0
        dur_16k = samples / 16000.0
        dur_48k = samples / 48000.0
        
        # Check audio energy / silence
        pcm = np.frombuffer(raw, dtype=np.int16)
        rms = np.sqrt(np.mean(pcm.astype(float)**2))
        
        # Voiced frames pitch
        frame = pcm[int(len(pcm)*0.3):int(len(pcm)*0.3) + 2400]
        corr = np.correlate(frame - np.mean(frame), frame - np.mean(frame), mode='full')
        corr = corr[len(corr)//2:]
        peak = 60 + np.argmax(corr[60:340]) if len(corr) > 340 else 1
        pitch_24k = 24000 / peak if peak > 0 else 0
        
        print(f"Speed={spd}: {len(raw)} bytes, RMS={rms:.1f}, 24kHz_dur={dur_24k:.2f}s (F0={pitch_24k:.1f}Hz), 48kHz_dur={dur_48k:.2f}s")
    except Exception as e:
        print(f"Speed={spd} error: {e}")

