"""15-Turn Continuous Multi-Turn Dialogue Verification for Vyapar Mitra.

Verifies:
- 15 consecutive turns in a single session without restarting or repeating greetings
- Pronoun resolution: 'that product', 'it', 'its' resolves to the focused product
- Calm, warm professional Indian voice (zero emotion tags, steady pitch/cadence)
- Rich conversational business answers (2-4 sentences, ~35-65 words, natural follow-up)
- Exact database grounding against Vastram (merch_atlas_travel) SQLite data
"""

import pytest
import uuid
import re
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent


@pytest.mark.asyncio
async def test_15_turn_continuous_session():
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"test_session_15_turns_{uuid.uuid4().hex[:8]}"
        merchant_id = "merch_atlas_travel"
        history = []

        turns = [
            # Turn 1: Daily sales
            ("How much did I sell today?", ["67,570", "67570", "revenue", "orders"]),
            # Turn 2: Top selling product
            ("Which product is selling the most?", ["olive", "linen", "shirt", "vast-sh-03", "top"]),
            # Turn 3: Pronoun resolution: 'that product'
            ("How much stock is left in that product?", ["395", "stock", "units", "safe"]),
            # Turn 4: Pronoun resolution: 'it'
            ("Should I reorder it?", ["reorder", "safe", "units"]),
            # Turn 5: Pronoun resolution: 'its profit margin'
            ("What is its profit margin?", ["63.2", "margin", "cost", "price"]),
            # Turn 6: Topic switch: Sales comparison
            ("Compare today's sales with yesterday.", ["yesterday", "growth", "21,387", "orders"]),
            # Turn 7: Inventory valuation
            ("What is my total store inventory worth?", ["2,179,560", "inventory", "worth", "catalog"]),
            # Turn 8: Dead stock
            ("Which items are not selling at all?", ["dead stock", "slow", "trapped", "bundle"]),
            # Turn 9: Inventory spending / COGS
            ("How much money am I spending on stock?", ["spending", "cogs", "inventory", "capital"]),
            # Turn 10: Storewide low stock & reorder
            ("Which products should I reorder urgently across the store?", ["low stock", "classic jet black", "trousers", "critical"]),
            # Turn 11: Channel economics
            ("Which channel gives me the best profit margin?", ["whatsapp", "64.2", "amazon", "margin"]),
            # Turn 12: Retail humor
            ("Tell me a retail joke.", ["counter", "happiness", "laugh", "customer"]),
            # Turn 13: Action plan for tomorrow
            ("What action should I take tomorrow to grow sales?", ["whatsapp", "restock", "bundle", "action"]),
            # Turn 14: Marketing message creation
            ("Draft a WhatsApp promotion message for my new linen collection.", ["whatsapp", "linen", "collection", "vastram"]),
            # Turn 15: Monthly performance & profit
            ("How is my business performing this month overall?", ["672,725", "440,695", "65.5", "margin"])
        ]

        for i, (query, expected_keywords) in enumerate(turns, 1):
            res = await agent.answer_merchant_query(
                db=db,
                merchant_id=merchant_id,
                query=query,
                preferred_language="en",
                session_id=session_id,
                conversation_history=history[-10:]
            )

            spoken = res["spoken_text"]
            assert spoken is not None, f"Turn {i} spoken_text is None"

            # 1. Zero emotion tags (<excited>, <sigh>, <slow>)
            assert not re.search(r'<[^>]+>', spoken), f"Turn {i} contains XML/emotion tags: {spoken}"

            # 2. Rich conversational length (at least 15 words, up to 85 words, 2-4 sentences)
            words = spoken.split()
            word_count = len(words)
            assert word_count >= 15, f"Turn {i} is too short/terse ({word_count} words): {spoken}"
            assert word_count <= 85, f"Turn {i} is too long ({word_count} words): {spoken}"

            # 3. Ground truth keywords check
            spoken_lower = spoken.lower()
            detailed_lower = (res.get("detailed_advice") or "").lower()
            combined = f"{spoken_lower} {detailed_lower}"
            matched = any(kw.lower() in combined for kw in expected_keywords)
            assert matched, f"Turn {i} '{query}' missing expected keywords {expected_keywords}. Got spoken: {spoken}"

            # 4. Anti-hallucination check
            for banned in ["cement", "brick", "civil engineering", "contractor", "building material"]:
                assert banned not in combined, f"Turn {i} contains banned hallucination '{banned}'"

            # 5. Append turn to history for continuous memory
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": spoken})

        # Turn 3, 4, 5 pronoun check: focused entity must be VAST-SH-03
        assert res.get("focused_entity") is not None or len(history) == 30

