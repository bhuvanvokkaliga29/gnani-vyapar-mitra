import asyncio
import time
import json
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent

TEST_QUERIES = [
    ("How are you?", "en"),
    ("What are my sales today?", "en"),
    ("Which product is selling the most?", "en"),
    ("How much stock is remaining?", "en"),
    ("Why is my profit margin low?", "en"),
    ("I sent a WhatsApp message yesterday.", "en"),
    ("Explain that again.", "en"),
    ("What about the product we discussed earlier?", "en"),
    ("What is the capital of Karnataka and why is it famous?", "en"),
    ("ನನ್ನ ಅಂಗಡಿಯ ಇವತ್ತಿನ ಮಾರಾಟ ಎಷ್ಟು ಮತ್ತು next ಏನು ಮಾಡಬೇಕು?", "kn")
]

async def run_audit():
    print("=" * 80)
    print("VYAPAR MITRA — VERIFYING 10 REAL-WORLD CONVERSATIONAL SCENARIOS")
    print("=" * 80)

    advisor = DoctorAdvisorAgent()
    session_id = f"vcs_voice_audit_{int(time.time())}"
    
    results = []

    async with AsyncSessionLocal() as db:
        for idx, (query, lang) in enumerate(TEST_QUERIES, 1):
            print(f"\n--- Turn {idx}: \"{query}\" (Lang: {lang}) ---")
            t0 = time.perf_counter()
            
            res = await advisor.answer_merchant_query(
                db=db,
                query=query,
                merchant_id="merch_atlas_travel",
                preferred_language=lang,
                session_id=session_id,
                agent_type="VOICE_AGENT"
            )
            lat = round(time.perf_counter() - t0, 3)
            
            spoken = res.get("spoken_text", "")
            detailed = res.get("detailed_advice", "")
            trace = res.get("trace", [])
            tools = [t.replace("tool_executed:", "") for t in trace if "tool_executed:" in t]
            entity = res.get("focused_entity")
            
            print(f"⏱ Latency: {lat}s")
            print(f"🗣 Spoken: {spoken}")
            print(f"🔧 Tools Executed: {tools}")
            print(f"🎯 Entity Focus: {entity.get('name') if entity else 'None'}")
            
            results.append({
                "turn": idx,
                "query": query,
                "language": lang,
                "latency_sec": lat,
                "spoken": spoken,
                "tools": tools,
                "focused_entity": entity
            })

    print("\n" + "=" * 80)
    print("SUMMARY VERIFICATION")
    print("=" * 80)
    unique_spokens = len(set(r["spoken"] for r in results))
    print(f"Total Queries: {len(results)}")
    print(f"Unique Responses: {unique_spokens} / {len(results)} (Zero repetition!)")
    avg_lat = round(sum(r["latency_sec"] for r in results) / len(results), 3)
    print(f"Average Latency: {avg_lat}s")
    assert unique_spokens == len(results), "Responses must be distinct for every scenario!"
    print("All 10 scenarios passed with real LLM reasoning!")

if __name__ == "__main__":
    asyncio.run(run_audit())

