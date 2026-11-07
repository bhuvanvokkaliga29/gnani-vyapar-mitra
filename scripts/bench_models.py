import asyncio
import httpx
import time
from apps.api.core.config import settings

async def main():
    key = settings.GEMINI_API_KEY
    print("Gemini key configured:", bool(key))
    models = ['gemini-2.5-flash', 'gemini-3.5-flash', 'gemini-3.1-flash-lite', 'gemini-3-flash-preview', 'gemma-4-26b-a4b-it']
    async with httpx.AsyncClient(timeout=10.0) as client:
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
            t0 = time.perf_counter()
            try:
                res = await client.post(url, json={'contents': [{'parts': [{'text': 'Hello, who are you? Reply in 6 words.'}]}]})
                lat = round(time.perf_counter() - t0, 3)
                if res.status_code == 200:
                    text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                    print(f"{m}: 200 OK in {lat}s -> '{text}'")
                else:
                    print(f"{m}: {res.status_code} in {lat}s -> {res.text[:100]}")
            except Exception as e:
                print(f"{m}: Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

