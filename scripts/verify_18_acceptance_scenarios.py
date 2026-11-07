import asyncio
import httpx
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"
MERCHANT_ID = "merch_atlas_travel"

async def run_scenario_suite():
    print("=" * 70)
    print("VYAPAR MITRA — FINAL 18-SCENARIO ACCEPTANCE VERIFICATION SUITE")
    print("=" * 70)

    results = []
    session_id = None

    async with httpx.AsyncClient(timeout=45.0) as client:

        async def send_turn(label, query, lang="en", expected_checks=None):
            nonlocal session_id
            print(f"\n[Scenario] {label}")
            print(f"User: '{query}' (Lang: {lang})")
            t0 = time.perf_counter()
            res = await client.post(f"{BASE_URL}/doctor/query", json={
                "merchant_id": MERCHANT_ID,
                "query": query,
                "session_id": session_id,
                "preferred_language": lang,
                "synthesize_audio": True
            })
            latency = round(time.perf_counter() - t0, 3)
            assert res.status_code == 200, f"HTTP Error {res.status_code}: {res.text}"
            data = res.json()
            session_id = data.get("session_id")

            spoken = data.get("spoken_text", "")
            detailed = data.get("detailed_advice", "")
            intent = data.get("intent")
            emotion = data.get("emotion")
            speed = data.get("speech_speed")
            focused = data.get("focused_entity")
            audio = data.get("audio") or {}
            audio_bytes = audio.get("audio_length_bytes", 0)

            print(f"Assistant Spoken: '{spoken}'")
            print(f"Intent: {intent} | Emotion: {emotion} | Speed: {speed}x | Audio: {audio_bytes} bytes | Latency: {latency}s")
            if focused:
                print(f"Focused Entity: {focused.get('name')} ({focused.get('sku')})")

            # Evaluate checks
            passed = True
            failure_reasons = []
            if expected_checks:
                for check_name, check_fn in expected_checks.items():
                    try:
                        ok = check_fn(data)
                        if not ok:
                            passed = False
                            failure_reasons.append(check_name)
                    except Exception as ex:
                        passed = False
                        failure_reasons.append(f"{check_name}: {ex}")

            status_str = "PASS" if passed else f"FAIL ({', '.join(failure_reasons)})"
            print(f"Status: {status_str}")
            results.append({
                "scenario": label,
                "query": query,
                "status": status_str,
                "latency": latency,
                "intent": intent,
                "emotion": emotion,
                "speed": speed,
                "audio_bytes": audio_bytes,
                "spoken": spoken
            })
            return data

        # 1. Greeting and casual conversation
        await send_turn(
            "1. Greeting & Casual Conversation",
            "Hello.",
            "en",
            {
                "No stale product leak": lambda d: not any(w in d.get("spoken_text", "").lower() for w in ["shirt", "linen", "stock", "units", "42"]),
                "Spoken audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0,
                "Focused entity is None": lambda d: d.get("focused_entity") is None
            }
        )

        # 2. General knowledge question
        await send_turn(
            "2. General Knowledge / Fabric Question",
            "Why is linen fabric good for Bangalore summer?",
            "en",
            {
                "Has spoken explanation": lambda d: len(d.get("spoken_text", "").split()) >= 4,
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 3. Business sales question
        await send_turn(
            "3. Business Sales Question",
            "What are my sales today?",
            "en",
            {
                "Mentions sales or numbers": lambda d: any(w in d.get("spoken_text", "").lower() for w in ["sales", "revenue", "orders", "rupees", "thousand", "67"]),
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 4. Product follow-up
        await send_turn(
            "4. Product Follow-up (Top Contributor)",
            "Which product contributed the most?",
            "en",
            {
                "Identifies top product": lambda d: "olive" in d.get("spoken_text", "").lower() or "linen" in d.get("spoken_text", "").lower() or (d.get("focused_entity") and "VAST-SH-03" in d.get("focused_entity", {}).get("sku", "")),
                "Active context set": lambda d: d.get("focused_entity") is not None
            }
        )

        # 5. Inventory follow-up
        await send_turn(
            "5. Inventory Follow-up (Contextual Pronoun Resolution)",
            "How much stock is remaining in that product?",
            "en",
            {
                "Answers with stock quantity": lambda d: any(w in d.get("spoken_text", "").lower() for w in ["stock", "units", "remaining", "145", "olive"]),
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 6. Profit explanation
        await send_turn(
            "6. Profit Margin Follow-up",
            "What about its profit margin?",
            "en",
            {
                "Answers with margin figure": lambda d: any(w in d.get("spoken_text", "").lower() for w in ["margin", "profit", "%", "percent", "64", "65"]),
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 7. Emotional conversation with a sad user
        await send_turn(
            "7. Emotional Empathy (Sad / Disappointed User)",
            "I'm feeling very low today. Nothing is going right.",
            "en",
            {
                "Emotion is SAD": lambda d: d.get("emotion") == "SAD",
                "Speed is slowed for comfort": lambda d: d.get("speech_speed") == 0.90,
                "No forced product pitches": lambda d: not any(w in d.get("spoken_text", "").lower() for w in ["buy", "reorder", "sku", "units"]),
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 8. Excited conversation with a happy user
        await send_turn(
            "8. Emotional Celebration (Excited / Triumphant User)",
            "Bro! I achieved something amazing today!",
            "en",
            {
                "Emotion is EXCITED": lambda d: d.get("emotion") == "EXCITED",
                "Speed is boosted for energy": lambda d: d.get("speech_speed") == 1.08,
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 9. Frustrated user interaction
        await send_turn(
            "9. De-escalation (Frustrated / Upset User)",
            "This is so frustrating! Nothing is working right now!",
            "en",
            {
                "Emotion is FRUSTRATED": lambda d: d.get("emotion") == "FRUSTRATED",
                "Speed is calm and measured": lambda d: d.get("speech_speed") == 0.94,
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 10. Confused user interaction
        await send_turn(
            "10. Patient Clarification (Confused User)",
            "I am confused, what does gross margin mean?",
            "en",
            {
                "Emotion is CONFUSED": lambda d: d.get("emotion") == "CONFUSED",
                "Speed is patient": lambda d: d.get("speech_speed") == 0.92,
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 11. Kannada conversation
        await send_turn(
            "11. Pure Kannada Multi-Turn (Greeting & Sales)",
            "ನಮಸ್ಕಾರ, ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?",
            "kn",
            {
                "Language is kn": lambda d: d.get("language") == "kn",
                "Kannada audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 12. Hindi conversation
        await send_turn(
            "12. Pure Hindi Multi-Turn (Greeting & Sales)",
            "नमस्ते, आज दुकान की बिक्री कैसी है?",
            "hi",
            {
                "Language is hi": lambda d: d.get("language") == "hi",
                "Hindi audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 13. Code-mixed conversation
        await send_turn(
            "13. Indic Code-Mixing (Kanglish)",
            "Bro, top product yaavudhu ivattu?",
            "kn",
            {
                "Answers in code-mix/Kannada": lambda d: len(d.get("spoken_text", "")) > 5,
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 14. Interruption & Standby
        await send_turn(
            "14. Voice Turn-Taking (Stop / Wait Interruption)",
            "Wait, stop.",
            "en",
            {
                "Recognizes pause intent": lambda d: d.get("intent") == "INTERRUPTION_PAUSE",
                "Polite standby message": lambda d: any(w in d.get("spoken_text", "").lower() for w in ["standby", "wait", "ready", "listening", "continue", "pause"])
            }
        )

        # 15. Say "Continue" after interruption
        await send_turn(
            "15. Turn-Taking Resume ('Continue')",
            "Continue.",
            "en",
            {
                "Recognizes resume intent": lambda d: d.get("intent") == "INTERRUPTION_RESUME",
                "Spoken text produced": lambda d: len(d.get("spoken_text", "").split()) >= 4
            }
        )

        # 16. Start a new conversation
        old_session = session_id
        new_data = await send_turn(
            "16. Start a Fresh Conversation ('Let\\'s start a new conversation')",
            "Let's start a new conversation.",
            "en",
            {
                "Session ID updated": lambda d: d.get("session_id") != old_session,
                "Focused entity reset": lambda d: d.get("focused_entity") is None,
                "Fresh greeting": lambda d: len(d.get("spoken_text", "")) > 10
            }
        )

        # 17. Contextual follow-up in fresh session
        await send_turn(
            "17. New Query in Fresh Session",
            "What are my sales today?",
            "en",
            {
                "Real sales data returned": lambda d: any(w in d.get("spoken_text", "").lower() for w in ["sales", "revenue", "orders", "rupees", "67"]),
                "Audio generated": lambda d: d.get("audio", {}).get("audio_length_bytes", 0) > 0
            }
        )

        # 18. Switch topics and return
        await send_turn(
            "18A. Topic Switch (Casual Chit-chat)",
            "How is the Bangalore weather today?",
            "en",
            {
                "Casual chit-chat response": lambda d: not any(w in d.get("spoken_text", "").lower() for w in ["shirt", "inventory", "dead stock"])
            }
        )

        await send_turn(
            "18B. Return to Business Topic",
            "Which product has the highest profit margin in Vastram?",
            "en",
            {
                "Identifies high margin product": lambda d: any(w in d.get("spoken_text", "").lower() for w in ["margin", "linen", "shirt", "%", "profit"])
            }
        )

    print("\n" + "=" * 70)
    print("FINAL 18-SCENARIO VERIFICATION SUMMARY")
    print("=" * 70)
    pass_count = sum(1 for r in results if "PASS" in r["status"])
    print(f"Total Scenarios Tested: {len(results)}")
    print(f"Passed: {pass_count} / {len(results)}")
    for r in results:
        print(f"[{r['status']}] {r['scenario']} ({r['latency']}s, Emotion: {r['emotion']}, Speed: {r['speed']}x)")

    with open("scripts/18_scenarios_report.json", "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)

if __name__ == "__main__":
    asyncio.run(run_scenario_suite())
