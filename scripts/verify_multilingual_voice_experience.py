import asyncio
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def test_full_multilingual_suite():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=35.0) as client:
        print("=================================================================")
        print("=== 1. CASUAL GREETING & MULTILINGUAL BRO BANTER TESTS ===")
        print("=================================================================")

        # 1A: Kannada Casual Bro Greeting
        res_kn = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "ಏನ್ ಬ್ರೋ, ಹೇಗಿದ್ದೀಯಾ?",
            "synthesize_audio": True
        })
        d_kn = res_kn.json()
        print("\n[Kannada Casual Greeting]")
        print("Query: ಏನ್ ಬ್ರೋ, ಹೇಗಿದ್ದೀಯಾ?")
        print("Detected Lang:", d_kn.get("language"))
        print("Spoken Reply:", d_kn.get("spoken_text"))
        print("Audio Present:", bool(d_kn.get("audio", {}).get("audio_base64")))
        assert d_kn.get("language") == "kn", f"Expected kn, got {d_kn.get('language')}"
        assert any('\u0c80' <= c <= '\u0cff' for c in d_kn.get("spoken_text", "")), "Expected Kannada script in response"

        # 1B: English Casual Bro Greeting
        res_en = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "Hey bro, how are you?",
            "synthesize_audio": True
        })
        d_en = res_en.json()
        print("\n[English Casual Greeting]")
        print("Query: Hey bro, how are you?")
        print("Detected Lang:", d_en.get("language"))
        print("Spoken Reply:", d_en.get("spoken_text"))
        print("Audio Present:", bool(d_en.get("audio", {}).get("audio_base64")))
        assert d_en.get("language") == "en", f"Expected en, got {d_en.get('language')}"
        assert any(w in d_en.get("spoken_text", "").lower() for w in ["great", "good", "doing", "bro", "hello"]), "Expected natural English greeting"

        print("\n=================================================================")
        print("=== 2. TAMIL, MALAYALAM, HINDI & TELUGU BUSINESS DATA TESTS ===")
        print("=================================================================")

        # 2A: Tamil Daily Sales Query
        res_ta = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "வணக்கம்! இன்று என் கடையின் விற்பனை எவ்வளவு?",
            "synthesize_audio": True
        })
        d_ta = res_ta.json()
        print("\n[Tamil Business Query]")
        print("Query: வணக்கம்! இன்று என் கடையின் விற்பனை எவ்வளவு?")
        print("Detected Lang:", d_ta.get("language"))
        print("Spoken Reply:", d_ta.get("spoken_text"))
        assert d_ta.get("language") == "ta", f"Expected ta, got {d_ta.get('language')}"
        assert any('\u0b80' <= c <= '\u0bff' for c in d_ta.get("spoken_text", "")), "Expected Tamil script in response"
        assert "67,570" in d_ta.get("spoken_text", "") or "67570" in d_ta.get("spoken_text", "") or "30" in d_ta.get("spoken_text", ""), "Missing store sales data in Tamil response"

        # 2B: Malayalam Daily Sales Query
        res_ml = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "നമസ്കാരം! ഇന്നത്തെ വിൽപ്പന എത്രയാണ്?",
            "synthesize_audio": True
        })
        d_ml = res_ml.json()
        print("\n[Malayalam Business Query]")
        print("Query: നമസ്കാരം! ഇന്നത്തെ വിൽപ്പന എത്രയാണ്?")
        print("Detected Lang:", d_ml.get("language"))
        print("Spoken Reply:", d_ml.get("spoken_text"))
        assert d_ml.get("language") == "ml", f"Expected ml, got {d_ml.get('language')}"
        assert any('\u0d00' <= c <= '\u0d7f' for c in d_ml.get("spoken_text", "")), "Expected Malayalam script in response"
        assert "67,570" in d_ml.get("spoken_text", "") or "67570" in d_ml.get("spoken_text", "") or "30" in d_ml.get("spoken_text", ""), "Missing store sales data in Malayalam response"

        # 2C: Hindi Daily Sales Query
        res_hi = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "नमस्ते भाई! आज की कुल बिक्री कितनी हुई?",
            "synthesize_audio": True
        })
        d_hi = res_hi.json()
        print("\n[Hindi Business Query]")
        print("Query: नमस्ते भाई! आज की कुल बिक्री कितनी हुई?")
        print("Detected Lang:", d_hi.get("language"))
        print("Spoken Reply:", d_hi.get("spoken_text"))
        assert d_hi.get("language") == "hi", f"Expected hi, got {d_hi.get('language')}"
        assert any('\u0900' <= c <= '\u097f' for c in d_hi.get("spoken_text", "")), "Expected Devanagari script in response"
        assert "67,570" in d_hi.get("spoken_text", "") or "67570" in d_hi.get("spoken_text", "") or "30" in d_hi.get("spoken_text", ""), "Missing store sales data in Hindi response"

        print("\n=================================================================")
        print("=== 3. CONSECUTIVE DYNAMIC LANGUAGE SWITCHING (EXAMPLE 5) ===")
        print("=================================================================")

        # Session Turn 1: User speaks Kannada
        # User: "ಇವತ್ತು ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?" -> Assistant responds in Kannada
        res_t1 = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "ಇವತ್ತು ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?",
            "synthesize_audio": False
        })
        d_t1 = res_t1.json()
        sess_id = d_t1.get("session_id")
        spk_t1 = d_t1.get("spoken_text", "")
        print("\n[Turn 1 — User speaks Kannada]")
        print("User: ಇವತ್ತು ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?")
        print("Detected Lang:", d_t1.get("language"))
        print("Assistant Spoken:", spk_t1)
        assert d_t1.get("language") == "kn", f"Turn 1 expected kn, got {d_t1.get('language')}"
        assert any('\u0c80' <= c <= '\u0cff' for c in spk_t1), "Turn 1 expected Kannada script"

        # Session Turn 2: User switches to English
        # User: "Okay, now tell me yesterday's profit." -> Assistant switches to English!
        res_t2 = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "Okay, now tell me yesterday's profit.",
            "session_id": sess_id,
            "conversation_history": [
                {"role": "user", "content": "ಇವತ್ತು ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?"},
                {"role": "assistant", "spoken_content": spk_t1}
            ],
            "synthesize_audio": False
        })
        d_t2 = res_t2.json()
        spk_t2 = d_t2.get("spoken_text", "")
        print("\n[Turn 2 — User switches to English]")
        print("User: Okay, now tell me yesterday's profit.")
        print("Detected Lang:", d_t2.get("language"))
        print("Assistant Spoken:", spk_t2)
        assert d_t2.get("language") == "en", f"Turn 2 expected en, got {d_t2.get('language')}"
        assert not any(g in spk_t2.lower() for g in ["namaskara", "hello!"]), "Turn 2 should not repeat greeting"

        # Session Turn 3: User switches back to Kannada/Kanglish
        # User: "ಇವಾಗ stock ಎಷ್ಟು ಇದೆ?" -> Assistant switches back to Kannada!
        res_t3 = await client.post("/api/v1/doctor/query", json={
            "merchant_id": "merch_atlas_travel",
            "query": "ಇವಾಗ stock ಎಷ್ಟು ಇದೆ?",
            "session_id": sess_id,
            "conversation_history": [
                {"role": "user", "content": "ಇವತ್ತು ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?"},
                {"role": "assistant", "spoken_content": spk_t1},
                {"role": "user", "content": "Okay, now tell me yesterday's profit."},
                {"role": "assistant", "spoken_content": spk_t2}
            ],
            "synthesize_audio": False
        })
        d_t3 = res_t3.json()
        spk_t3 = d_t3.get("spoken_text", "")
        print("\n[Turn 3 — User switches back to Kannada]")
        print("User: ಇವಾಗ stock ಎಷ್ಟು ಇದೆ?")
        print("Detected Lang:", d_t3.get("language"))
        print("Assistant Spoken:", spk_t3)
        assert d_t3.get("language") == "kn", f"Turn 3 expected kn, got {d_t3.get('language')}"
        assert any('\u0c80' <= c <= '\u0cff' for c in spk_t3), "Turn 3 expected Kannada script"

        print("\n=================================================================")
        print("=== ALL MULTILINGUAL TESTS & DYNAMIC SWITCHING PASSED! ===")
        print("=================================================================")

if __name__ == "__main__":
    asyncio.run(test_full_multilingual_suite())

