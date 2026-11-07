import asyncio
import uuid
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent

async def run_dialogue():
    sid = "vcs_test_" + uuid.uuid4().hex[:8]
    agent = DoctorAdvisorAgent()
    queries = [
        "How much revenue did my shop generate today?",
        "Which product contributed the most?",
        "How much stock is remaining in that product?",
        "Should I reorder it right now?",
        "What about its profit margin?"
    ]
    print(f"=== TESTING 5-TURN CONTINUOUS CONVERSATION (Session: {sid}) ===")
    async with AsyncSessionLocal() as db:
        for i, q in enumerate(queries, 1):
            t0 = time.perf_counter()
            res = await agent.answer_merchant_query(
                db=db,
                query=q,
                merchant_id="merch_atlas_travel",
                session_id=sid,
                preferred_language="en"
            )
            elapsed = time.perf_counter() - t0
            print(f"\n[Turn {i}] User: {q}")
            print(f"[Turn {i}] Assistant Spoken ({elapsed:.2f}s): {res.get('spoken_text')}")
            f_ent = res.get("focused_entity")
            if f_ent:
                print(f"[Turn {i}] Focused Product: {f_ent.get('name')} (SKU: {f_ent.get('sku')})")
            else:
                print(f"[Turn {i}] Focused Product: None")

if __name__ == "__main__":
    asyncio.run(run_dialogue())
