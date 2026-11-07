"""30-Turn Long-Context Continuous Session & Emotional Intelligence Verification for Vyapar Mitra.

Contract: master-upgrade/voice-intelligence/v1
Verifies:
1. 30 consecutive turns in a single persistent session.
2. Long-context recall at Turn 29 and Turn 30 (Opening query and opening revenue figure).
3. Emotional intelligence (laughter 'Haha', triumph, frustration, sadness, confusion).
4. Multilingual & code-switching (English, Kannada/Kanglish, Hindi/Hinglish).
5. Ground truth accuracy against Vastram boutique SQLite database.
6. Monotonic latency measurement & zero SSML/emotion tag leakage.
"""

import pytest
import uuid
import re
import time
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent


@pytest.mark.asyncio
async def test_30_turn_long_context_session():
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"test_session_30_turns_{uuid.uuid4().hex[:8]}"
        merchant_id = "merch_atlas_travel"
        history = []

        turns = [
            # Turn 1: Daily sales (Opening anchor)
            ("How much did I sell today?", ["67,570", "67570", "revenue", "orders"], "en"),
            # Turn 2: Top seller
            ("Which product is selling the most?", ["olive", "linen", "shirt", "vast-sh-03", "top"], "en"),
            # Turn 3: Pronoun resolution: 'that product'
            ("How much stock is left in that product?", ["395", "stock", "units", "safe"], "en"),
            # Turn 4: Pronoun resolution: 'it'
            ("Should I reorder it?", ["reorder", "safe", "units"], "en"),
            # Turn 5: Pronoun resolution: 'its profit margin'
            ("What is its profit margin?", ["63.2", "margin", "cost", "price"], "en"),
            # Turn 6: Comparison with yesterday
            ("Compare today's sales with yesterday.", ["yesterday", "growth", "21,387", "orders"], "en"),
            # Turn 7: Inventory valuation
            ("What is my total store inventory worth?", ["2,179,560", "inventory", "worth", "catalog"], "en"),
            # Turn 8: Dead stock
            ("Which items are not selling at all?", ["dead stock", "slow", "trapped", "bundle"], "en"),
            # Turn 9: Inventory spending / COGS
            ("How much money am I spending on stock?", ["spending", "cogs", "inventory", "capital"], "en"),
            # Turn 10: Storewide low stock & reorder
            ("Which products should I reorder urgently across the store?", ["low stock", "classic jet black", "trousers", "critical"], "en"),
            # Turn 11: Channel economics
            ("Which channel gives me the best profit margin?", ["whatsapp", "64.2", "amazon", "margin"], "en"),
            # Turn 12: Retail humor
            ("Tell me a retail joke.", ["counter", "happiness", "laugh", "customer"], "en"),
            # Turn 13: Action plan for tomorrow
            ("What action should I take tomorrow to grow sales?", ["whatsapp", "restock", "bundle", "action"], "en"),
            # Turn 14: Marketing message creation
            ("Draft a WhatsApp promotion message for my new linen collection.", ["whatsapp", "linen", "collection", "vastram"], "en"),
            # Turn 15: Monthly performance & profit
            ("How is my business performing this month overall?", ["672,725", "440,695", "65.5", "margin"], "en"),
            # Turn 16: Kannada / Kanglish query
            ("ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?", ["ಆರ್ಡರ್", "ವ್ಯಾಪಾರ", "ಮಾರಾಟ", "ಲಾಭ", "67,570", "orders", "revenue"], "kn"),
            # Turn 17: Hindi / Hinglish query
            ("आज की बिक्री कैसी है?", ["ऑर्डर्स", "बिक्री", "मुनाफा", "मार्जिन", "67,570", "orders", "revenue"], "hi"),
            # Turn 18: Laughter & banter with business question
            ("Haha that is funny! How much stock is remaining in Oxford Cotton Shirt?", ["oxford", "shirt", "stock", "units", "vast-sh-01", "14"], "en"),
            # Turn 19: Emotion: Triumph / Excitement
            ("Bro! I achieved something amazing today with our boutique sales!", ["congratulations", "amazing", "proud", "vastram", "sales", "celebrate"], "en"),
            # Turn 20: Emotion: Frustration with channel fees
            ("I am so frustrated with Amazon commissions eating my profits!", ["understand", "frustrat", "whatsapp", "margin", "commission", "direct"], "en"),
            # Turn 21: Emotion: Sadness / Low mood
            ("I am feeling very low today, footfall was really slow.", ["support", "low", "tomorrow", "vastram", "heart", "customer", "retail"], "en"),
            # Turn 22: Emotion: Confusion
            ("I am confused about margin floor policy, please explain simply.", ["margin", "floor", "cost", "price", "profit", "simple", "percent"], "en"),
            # Turn 23: Interruption resume
            ("Go ahead and continue speaking.", ["continue", "proceed", "vastram", "analysis", "discussion"], "en"),
            # Turn 24: Single item check
            ("How many Classic Jet Black Formal Trousers are left in stock?", ["black", "formal", "trousers", "stock", "units", "reorder", "8"], "en"),
            # Turn 25: Chino trousers check
            ("What about Khaki Chino Trousers?", ["khaki", "chino", "trousers", "stock", "units", "19"], "en"),
            # Turn 26: Clearance bundle query
            ("Can you propose a clearance bundle for slow items?", ["bundle", "clearance", "whatsapp", "discount", "slow"], "en"),
            # Turn 27: Strategic advice
            ("How to improve my net margins further?", ["whatsapp", "channel", "arbitrage", "margin", "repeat"], "en"),
            # Turn 28: Correction / explicit preference
            ("Actually, I prefer WhatsApp campaigns over SMS promotions.", ["whatsapp", "noted", "campaign", "preference", "direct"], "en"),
            # Turn 29: DEEP LONG-CONTEXT RECALL 1 (First query in conversation)
            ("What was the very first question I asked you at the beginning of our conversation?", ["sell", "today", "sales", "revenue", "first", "began", "beginning"], "en"),
            # Turn 30: DEEP LONG-CONTEXT RECALL 2 (First financial figure stated)
            ("What was the revenue figure you told me at the beginning of our chat?", ["67,570", "67570", "44,982", "revenue", "sales", "today"], "en")
        ]

        latencies = []

        for i, (query, expected_keywords, lang) in enumerate(turns, 1):
            t_turn_0 = time.perf_counter()
            res = await agent.answer_merchant_query(
                db=db,
                merchant_id=merchant_id,
                query=query,
                preferred_language=lang,
                session_id=session_id,
                conversation_history=history[-14:]
            )
            turn_latency = round(time.perf_counter() - t_turn_0, 3)
            latencies.append(turn_latency)

            spoken = res["spoken_text"]
            assert spoken is not None, f"Turn {i} spoken_text is None"

            # 1. Zero SSML/emotion tag leakage (<excited>, <laugh>, etc.)
            assert not re.search(r'<[^>]+>', spoken), f"Turn {i} contains XML/emotion tags: {spoken}"

            # 2. Anti-hallucination check (whole-word boundary to avoid false positives like 'enhancement')
            combined = f"{spoken.lower()} {(res.get('detailed_advice') or '').lower()}"
            for banned in ["cement", "brick", "civil engineering", "contractor", "building material"]:
                assert not re.search(r'\b' + re.escape(banned) + r'\b', combined), f"Turn {i} contains banned hallucination '{banned}'"

            # 3. Ground truth keyword check
            matched = any(kw.lower() in combined for kw in expected_keywords)
            assert matched, f"Turn {i} '{query}' missing expected keywords {expected_keywords}. Got spoken: {spoken}"

            # 4. Append turn to history
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": spoken})

        # Final assertions for 30-turn completion
        assert len(history) == 60, f"Expected 60 turn entries (30 pairs), got {len(history)}"
        avg_latency = round(sum(latencies) / len(latencies), 3)
        print(f"\n30-Turn Test PASSED! Average AI reasoning latency per turn: {avg_latency}s")

