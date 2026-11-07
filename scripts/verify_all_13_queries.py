"""Comprehensive Verification for the 13 Priority Zero Queries across Kannada, Hindi, and English."""

import sys, os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import json
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent, prepare_spoken_response

TEST_QUERIES = [
    # English
    {"id": 1, "lang": "en", "query": "Hello, how are you?", "type": "social"},
    {"id": 2, "lang": "en", "query": "I sent a WhatsApp message yesterday.", "type": "casual_mention"},
    {"id": 3, "lang": "en", "query": "Create a WhatsApp promotion for my new collection.", "type": "content_creation"},
    {"id": 4, "lang": "en", "query": "How are my sales today?", "type": "business"},

    # Kannada
    {"id": 5, "lang": "kn", "query": "ನಮಸ್ಕಾರ, ಹೇಗಿದ್ದೀರಿ?", "type": "social"},
    {"id": 6, "lang": "kn", "query": "ನಿನ್ನ ಹೆಸರೇನು?", "type": "social"},
    {"id": 7, "lang": "kn", "query": "ನಾನು ನಿನ್ನೆ ವಾಟ್ಸಾಪ್ ಮೆಸೇಜ್ ಕಳಿಸಿದ್ದೆ", "type": "casual_mention"},
    {"id": 8, "lang": "kn", "query": "ನನ್ನ ಹೊಸ ಕಲೆಕ್ಷನ್‌ಗೆ ವಾಟ್ಸಾಪ್ ಪ್ರಮೋಷನ್ ಮೆಸೇಜ್ ರೆಡಿ ಮಾಡು", "type": "content_creation"},
    {"id": 9, "lang": "kn", "query": "ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?", "type": "business"},

    # Hindi
    {"id": 10, "lang": "hi", "query": "नमस्ते, आप कैसे हैं?", "type": "social"},
    {"id": 11, "lang": "hi", "query": "मैंने कल व्हाट्सएप मैसेज भेजा था", "type": "casual_mention"},
    {"id": 12, "lang": "hi", "query": "मेरे नए कलेक्शन के लिए एक व्हाट्सएप प्रमोशन मैसेज बनाओ", "type": "content_creation"},
    {"id": 13, "lang": "hi", "query": "आज की बिक्री कैसी है?", "type": "business"},
]

async def run_verification():
    agent = DoctorAdvisorAgent()
    results = []

    async with AsyncSessionLocal() as db:
        for t in TEST_QUERIES:
            print(f"\n[{t['id']}/13] Query: '{t['query']}' ({t['type']} | {t['lang']})")
            res = await agent.answer_merchant_query(
                db=db,
                query=t["query"],
                merchant_id="merch_atlas_travel",
                preferred_language=t["lang"]
            )

            spoken = res.get("spoken_text") or ""
            detailed = res.get("detailed_advice") or ""
            action = res.get("recommended_action")
            traces = res.get("trace", [])
            engine = next((tr for tr in traces if "reasoning_engine" in tr), "unknown")
            tools = [tr for tr in traces if "tool_executed" in tr]

            has_hashtags = "#" in spoken
            has_asterisks = "*" in spoken

            # Assertions based on type
            passed = True
            notes = []

            if has_hashtags:
                passed = False
                notes.append("Spoken reply contains hashtag '#'")
            if has_asterisks:
                passed = False
                notes.append("Spoken reply contains markdown asterisks '*'")

            if t["type"] in ("social", "casual_mention"):
                if tools:
                    passed = False
                    notes.append(f"Unexpected tool called: {tools}")
                if action and action.get("type") in ("CLEARANCE_BUNDLE", "PRICE_CHANGE"):
                    passed = False
                    notes.append(f"Unexpected marketing action proposal: {action.get('type')}")

            elif t["type"] == "business":
                if not tools and "tool_executed:get_daily_sales" not in str(traces):
                    passed = False
                    notes.append("Expected business tool get_daily_sales not executed")

            status_str = "PASS" if passed else "FAIL"
            print(f"  -> Engine: {engine}")
            print(f"  -> Spoken: \"{spoken}\"")
            print(f"  -> Tools: {tools}")
            print(f"  -> Action: {action.get('type') if action else None}")
            print(f"  -> Status: {status_str} {notes}")

            results.append({
                "id": t["id"],
                "query": t["query"],
                "lang": t["lang"],
                "type": t["type"],
                "spoken": spoken,
                "engine": engine,
                "tools": tools,
                "action": action.get("type") if action else None,
                "passed": passed,
                "notes": notes
            })

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"\n==========================================")
    print(f"SUMMARY: {passed_count}/{total} PASSED")
    print(f"==========================================")

    with open("scripts/verification_results.json", "w", encoding="utf-8") as out_f:
        json.dump(results, out_f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(run_verification())
