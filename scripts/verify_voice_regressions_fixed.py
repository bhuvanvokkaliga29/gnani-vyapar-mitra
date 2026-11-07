import asyncio
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def test_regression_fixes():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print("--- TEST 1: Kannada input -> English understanding -> English response ---")
        payload1 = {
            "merchant_id": "merch_atlas_travel",
            "query": "ಇವತ್ತು ನನ್ನ ಸೇಲ್ಸ್ ಎಷ್ಟು ಆಗಿದೆ?",
            "preferred_language": "en",
            "synthesize_audio": True
        }
        res1 = await client.post("/api/v1/doctor/query", json=payload1)
        data1 = res1.json()
        print("Status:", res1.status_code)
        print("Detected/Resolved Language:", data1.get("language"))
        spoken1 = data1.get("spoken_text", "")
        detailed1 = data1.get("detailed_advice", "")
        print("Spoken Reply:", spoken1)
        print("Detailed Advice (first 120 chars):", detailed1[:120])
        print("Audio Present:", bool(data1.get("audio", {}).get("audio_base64")))
        print("Audio Voice:", data1.get("audio", {}).get("voice"))
        
        # Assertions for Test 1
        assert data1.get("language") == "en", f"Expected language 'en', got {data1.get('language')}"
        assert "67,570" in spoken1 or "67570" in spoken1, f"Missing sales figure in spoken text: {spoken1}"
        assert "DETAILED_BOX" not in spoken1, "Found DETAILED_BOX in spoken text!"
        assert "LANGUAGE PREFERENCE" not in spoken1, "Found LANGUAGE PREFERENCE in spoken text!"
        assert "|" not in spoken1, "Found table pipes in spoken text!"
        assert "DETAILED_BOX" not in detailed1, "Found DETAILED_BOX in detailed advice!"
        print(">>> TEST 1 PASSED: Kannada input answered in pure English with verified sales data & zero metadata leaks!\n")

        print("--- TEST 2: Multi-turn session & Zero Greeting Repetition ---")
        session_id = data1.get("session_id")
        
        # Turn 2: Greeting
        payload2 = {
            "merchant_id": "merch_atlas_travel",
            "query": "Hello, how are you?",
            "session_id": session_id,
            "conversation_history": [
                {"role": "user", "content": "ಇವತ್ತು ನನ್ನ ಸೇಲ್ಸ್ ಎಷ್ಟು ಆಗಿದೆ?"},
                {"role": "assistant", "spoken_content": spoken1}
            ],
            "preferred_language": "en",
            "synthesize_audio": False
        }
        res2 = await client.post("/api/v1/doctor/query", json=payload2)
        data2 = res2.json()
        spoken2 = data2.get("spoken_text", "")
        print("Turn 2 Spoken Reply:", spoken2)

        # Turn 3: Follow-up business query (Must NOT repeat greeting!)
        payload3 = {
            "merchant_id": "merch_atlas_travel",
            "query": "What about my profit margin?",
            "session_id": session_id,
            "conversation_history": [
                {"role": "user", "content": "ಇವತ್ತು ನನ್ನ ಸೇಲ್ಸ್ ಎಷ್ಟು ಆಗಿದೆ?"},
                {"role": "assistant", "spoken_content": spoken1},
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "assistant", "spoken_content": spoken2}
            ],
            "preferred_language": "en",
            "synthesize_audio": False
        }
        res3 = await client.post("/api/v1/doctor/query", json=payload3)
        data3 = res3.json()
        spoken3 = data3.get("spoken_text", "")
        print("Turn 3 Spoken Reply:", spoken3)
        
        # Check that Turn 3 does NOT say "Hello!", "Namaskara!", or repeat greetings
        assert not any(g in spoken3.lower() for g in ["namaskara", "hello!", "hey there!", "welcome back!"]), \
            f"Turn 3 repeated greetings: {spoken3}"
        assert "DETAILED_BOX" not in spoken3, "Found DETAILED_BOX in spoken text!"
        assert "|" not in spoken3, "Found table pipes in spoken text!"
        print(">>> TEST 2 PASSED: Zero greeting repetition in follow-up turn!\n")

        print("--- TEST 3: Multi-question in one turn ---")
        payload4 = {
            "merchant_id": "merch_atlas_travel",
            "query": "Hello, how are you? Tell me today's profit and which product sold best.",
            "preferred_language": "en",
            "synthesize_audio": False
        }
        res4 = await client.post("/api/v1/doctor/query", json=payload4)
        data4 = res4.json()
        spoken4 = data4.get("spoken_text", "")
        print("Turn 4 Spoken Reply:", spoken4)
        assert "DETAILED_BOX" not in spoken4, "Found DETAILED_BOX in spoken text!"
        assert "|" not in spoken4, "Found table pipes in spoken text!"
        print(">>> TEST 3 PASSED: Multi-question handled directly without metadata leak!\n")

        print("--- TEST 4: Explicit Language Switch Command ---")
        payload5 = {
            "merchant_id": "merch_atlas_travel",
            "query": "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡು. ಇವತ್ತಿನ ಮಾರಾಟ ಎಷ್ಟು?",
            "preferred_language": "en",
            "synthesize_audio": True
        }
        res5 = await client.post("/api/v1/doctor/query", json=payload5)
        data5 = res5.json()
        spoken5 = data5.get("spoken_text", "")
        print("Turn 5 Language:", data5.get("language"))
        print("Turn 5 Spoken Reply:", spoken5)
        assert data5.get("language") == "kn", f"Expected language 'kn' on explicit command, got {data5.get('language')}"
        print(">>> TEST 4 PASSED: Explicit Kannada switch command respected!\n")

        print("=== ALL 4 VOICE REGRESSION TESTS COMPLETED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(test_regression_fixes())
