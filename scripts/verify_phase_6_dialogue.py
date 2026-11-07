import sys, os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import json
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent

CONVERSATIONS = [
    {
        "language_name": "English",
        "lang_code": "en",
        "turns": [
            {"turn": 1, "query": "Hello.", "expected": "Greeting / welcome"},
            {"turn": 2, "query": "How are you?", "expected": "Warm conversational status, no tools"},
            {"turn": 3, "query": "Tell me a joke.", "expected": "Clean retail humor, no tools"},
            {"turn": 4, "query": "What is WhatsApp?", "expected": "Platform explanation, no marketing dump"},
            {"turn": 5, "query": "I sent a WhatsApp message.", "expected": "Casual acknowledgment, no marketing campaign"},
            {"turn": 6, "query": "Create a WhatsApp promotion.", "expected": "Promotional copy in details, concise spoken"},
            {"turn": 7, "query": "How is my business doing?", "expected": "Executes sales/inventory BI tools, factual data"},
            {"turn": 8, "query": "Why is profit low?", "expected": "Amazon marketplace commission vs WhatsApp margin arbitrage"},
            {"turn": 9, "query": "What should I do tomorrow?", "expected": "3 actionable retail steps (VIP broadcast, restock, clearance)"},
            {"turn": 10, "query": "Correct the previous answer.", "expected": "Courteous clarification without repetition"}
        ]
    },
    {
        "language_name": "Kannada",
        "lang_code": "kn",
        "turns": [
            {"turn": 1, "query": "ನಮಸ್ಕಾರ.", "expected": "Greeting"},
            {"turn": 2, "query": "ಹೇಗಿದ್ದೀರಿ?", "expected": "Conversational greeting"},
            {"turn": 3, "query": "ಒಂದು ಜೋಕ್ ಹೇಳು.", "expected": "Kannada retail joke"},
            {"turn": 4, "query": "ವಾಟ್ಸಾಪ್ ಅಂದರೆ ಏನು?", "expected": "Explanation without marketing"},
            {"turn": 5, "query": "ನಾನು ವಾಟ್ಸಾಪ್ ಮೆಸೇಜ್ ಕಳಿಸಿದ್ದೆ.", "expected": "Casual conversation"},
            {"turn": 6, "query": "ವಾಟ್ಸಾಪ್ ಪ್ರಮೋಷನ್ ಮೆಸೇಜ್ ರೆಡಿ ಮಾಡು.", "expected": "Marketing template"},
            {"turn": 7, "query": "ನನ್ನ ವ್ಯಾಪಾರ ಹೇಗೆ ನಡೆಯುತ್ತಿದೆ?", "expected": "Daily sales figures"},
            {"turn": 8, "query": "ಲಾಭ ಏಕೆ ಕಡಿಮೆಯಾಗಿದೆ?", "expected": "Amazon fees explanation"},
            {"turn": 9, "query": "ನಾಳೆ ನಾನು ಏನು ಮಾಡಬೇಕು?", "expected": "Tomorrow action roadmap"},
            {"turn": 10, "query": "ಹಿಂದಿನ ಉತ್ತರ ಸರಿಪಡಿಸು.", "expected": "Polite clarification"}
        ]
    },
    {
        "language_name": "Hindi",
        "lang_code": "hi",
        "turns": [
            {"turn": 1, "query": "नमस्ते।", "expected": "Greeting"},
            {"turn": 2, "query": "आप कैसे हैं?", "expected": "Conversational greeting"},
            {"turn": 3, "query": "एक चुटकुला सुनाओ।", "expected": "Hindi retail joke"},
            {"turn": 4, "query": "व्हाट्सएप क्या है?", "expected": "Explanation without marketing"},
            {"turn": 5, "query": "मैंने व्हाट्सएप मैसेज भेजा था।", "expected": "Casual conversation"},
            {"turn": 6, "query": "एक व्हाट्सएप प्रमोशन बनाओ।", "expected": "Marketing template"},
            {"turn": 7, "query": "मेरा व्यापार कैसा चल रहा है?", "expected": "Daily sales figures"},
            {"turn": 8, "query": "मुनाफा कम क्यों है?", "expected": "Amazon fees vs Direct margin"},
            {"turn": 9, "query": "कल मुझे क्या करना चाहिए?", "expected": "Tomorrow action roadmap"},
            {"turn": 10, "query": "पिछला उत्तर सही करो।", "expected": "Polite clarification"}
        ]
    }
]

async def verify_dialogues():
    agent = DoctorAdvisorAgent()
    overall_results = {}

    async with AsyncSessionLocal() as db:
        for conv in CONVERSATIONS:
            lang_name = conv["language_name"]
            lang_code = conv["lang_code"]
            print(f"\n=======================================================")
            print(f"TESTING 10-TURN DIALOGUE: {lang_name.upper()} ({lang_code})")
            print(f"=======================================================")

            history = []
            conv_log = []

            for t in conv["turns"]:
                q = t["query"]
                turn_no = t["turn"]
                await asyncio.sleep(1.0)
                res = await agent.answer_merchant_query(
                    db=db,
                    query=q,
                    merchant_id="merch_atlas_travel",
                    preferred_language=lang_code,
                    conversation_history=history
                )

                spoken = res.get("spoken_text") or ""
                intent = res.get("intent")
                action = res.get("recommended_action")
                traces = res.get("trace", [])
                tools = [tr for tr in traces if "tool_executed" in tr]
                engine = next((tr for tr in traces if "reasoning_engine" in tr), "unknown")

                # Validate no hashtags or asterisks in spoken output
                has_hashtags = "#" in spoken
                has_asterisks = "*" in spoken
                passed = not has_hashtags and not has_asterisks

                print(f"[Turn {turn_no}] Merchant: '{q}'")
                print(f"   Intent: {intent} | Engine: {engine}")
                print(f"   Tools: {tools} | Action: {action.get('type') if action else None}")
                print(f"   Spoken: \"{spoken}\"")

                # Append turn to history
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": res.get("detailed_advice") or spoken})

                conv_log.append({
                    "turn": turn_no,
                    "query": q,
                    "intent": intent,
                    "engine": engine,
                    "tools": tools,
                    "action": action.get("type") if action else None,
                    "spoken": spoken,
                    "passed": passed
                })

            overall_results[lang_name] = conv_log

    with open("scripts/phase_6_dialogue_results.json", "w", encoding="utf-8") as f:
        json.dump(overall_results, f, indent=2, ensure_ascii=False)

    print("\nPhase 6 dialogue verification complete! Results written to scripts/phase_6_dialogue_results.json")

if __name__ == "__main__":
    asyncio.run(verify_dialogues())
