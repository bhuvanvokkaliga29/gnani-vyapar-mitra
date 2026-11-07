import asyncio
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.api.core.database import AsyncSessionLocal
from services.whatsapp.service import WhatsAppService

test_messages = [
    "Download the previous week sales report",
    "Show my products",
    "Which products have low margins?",
    "Suggest an offer for Product A",
    "Update Product A stock to 25",
    "Change Product A price to 499"
]

async def run_tests():
    svc = WhatsAppService()
    for msg in test_messages:
        async with AsyncSessionLocal() as db:
            print("=" * 60)
            print(f"INPUT: {msg}")
            res = await svc.process_connector_message(
                db=db,
                sender_phone="+919113960498",
                message_text=msg,
                message_id=f"test_wweb_{uuid.uuid4().hex[:10]}"
            )
            print(f"STATUS: {res.get('status')}")
            print(f"INTENT: {res.get('intent')}")
            print(f"REPLY:\n{res.get('reply')}\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
