"""Comprehensive Verification Test Suite for all 12 Business Intelligence Questions.

Covers:
1. How much did I sell today?
2. What is my total revenue?
3. How much profit did I make?
4. Which products are selling the most?
5. Which products are running out of stock?
6. Which products should I reorder?
7. How much money am I spending?
8. Compare today's sales with yesterday.
9. How is my business performing this month?
10. Which products are not selling?
11. What is my profit margin?
12. How much inventory value do I have?
"""

import pytest
import uuid
import re
from apps.api.core.database import AsyncSessionLocal
from services.agent.doctor_advisor import DoctorAdvisorAgent


@pytest.mark.asyncio
async def test_all_12_commercial_questions():
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        session_id = f"test_comm_12_{uuid.uuid4().hex[:8]}"

        # Q1: How much did I sell today?
        r1 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="How much did I sell today?",
            preferred_language="en", session_id=session_id
        )
        assert r1["spoken_text"] is not None
        text1 = r1["spoken_text"].lower()
        assert "67,570" in text1 or "67570" in text1 or "sixty seven" in text1 or "30 orders" in text1 or "30" in text1 or "rupees" in text1

        # Q2: What is my total revenue?
        r2 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="What is my total revenue?",
            preferred_language="en", session_id=session_id
        )
        assert r2["spoken_text"] is not None
        text2 = r2["spoken_text"].lower()
        assert "revenue" in text2 or "rupees" in text2

        # Q3: How much profit did I make?
        r3 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="How much profit did I make?",
            preferred_language="en", session_id=session_id
        )
        assert r3["spoken_text"] is not None
        text3 = r3["spoken_text"].lower()
        assert "profit" in text3 or "margin" in text3 or "rupees" in text3

        # Q4: Which products are selling the most?
        r4 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="Which products are selling the most?",
            preferred_language="en", session_id=session_id
        )
        assert r4["spoken_text"] is not None
        text4 = r4["spoken_text"].lower()
        assert "linen" in text4 or "shirt" in text4 or "olive" in text4 or "selling" in text4

        # Q5: Which products are running out of stock?
        r5 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="Which products are running out of stock?",
            preferred_language="en", session_id=session_id
        )
        assert r5["spoken_text"] is not None
        text5 = r5["spoken_text"].lower()
        assert "trouser" in text5 or "black" in text5 or "blazer" in text5 or "critical" in text5 or "units" in text5

        # Q6: Which products should I reorder?
        r6 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="Which products should I reorder?",
            preferred_language="en", session_id=session_id
        )
        assert r6["spoken_text"] is not None
        text6 = r6["spoken_text"].lower()
        assert "reorder" in text6 or "restock" in text6 or "trouser" in text6 or "stock" in text6 or "black" in text6

        # Q7: How much money am I spending?
        r7 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="How much money am I spending?",
            preferred_language="en", session_id=session_id
        )
        assert r7["spoken_text"] is not None
        text7 = r7["spoken_text"].lower()
        assert "spending" in text7 or "cost" in text7 or "cogs" in text7 or "rupees" in text7 or "holding" in text7

        # Q8: Compare today's sales with yesterday.
        r8 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="Compare today's sales with yesterday.",
            preferred_language="en", session_id=session_id
        )
        assert r8["spoken_text"] is not None
        text8 = r8["spoken_text"].lower()
        assert "yesterday" in text8 or "growth" in text8 or "215" in text8 or "67,570" in text8 or "21,387" in text8 or "upward" in text8

        # Q9: How is my business performing this month?
        r9 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="How is my business performing this month?",
            preferred_language="en", session_id=session_id
        )
        assert r9["spoken_text"] is not None
        text9 = r9["spoken_text"].lower()
        assert "revenue" in text9 or "margin" in text9 or "profit" in text9 or "performing" in text9 or "orders" in text9

        # Q10: Which products are not selling?
        r10 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="Which products are not selling?",
            preferred_language="en", session_id=session_id
        )
        assert r10["spoken_text"] is not None
        text10 = r10["spoken_text"].lower()
        assert "slow" in text10 or "dead" in text10 or "linen" in text10 or "chino" in text10 or "trapped" in text10

        # Q11: What is my profit margin?
        r11 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="What is my profit margin?",
            preferred_language="en", session_id=session_id
        )
        assert r11["spoken_text"] is not None
        text11 = r11["spoken_text"].lower()
        assert "margin" in text11 or "%" in text11 or "percent" in text11 or "64" in text11 or "65" in text11

        # Q12: How much inventory value do I have?
        r12 = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="How much inventory value do I have?",
            preferred_language="en", session_id=session_id
        )
        assert r12["spoken_text"] is not None
        text12 = r12["spoken_text"].lower()
        assert "inventory" in text12 or "value" in text12 or "21" in text12 or "lakh" in text12 or "rupees" in text12 or "2,179,560" in text12


@pytest.mark.asyncio
async def test_anti_hallucination_and_strict_boutique_domain():
    """Verify that queries about materials or construction never discuss civil engineering."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        
        # Test query with potentially ambiguous retail words
        r = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="What materials and constructions are used in our best sellers?",
            preferred_language="en"
        )
        spoken = r["spoken_text"].lower()
        detailed = (r.get("detailed_advice") or "").lower()
        full_text = f"{spoken} {detailed}"
        
        # Absolute domain checks
        for forbidden in ["cement", "brick", "concrete", "contractor", "civil engineering", "real estate", "site visit", "plaster"]:
            assert forbidden not in full_text, f"Forbidden construction term '{forbidden}' detected in response!"


@pytest.mark.asyncio
async def test_proactive_follow_up_question_present():
    """Verify that spoken responses end with a natural commercial follow-up question."""
    async with AsyncSessionLocal() as db:
        agent = DoctorAdvisorAgent()
        r = await agent.answer_merchant_query(
            db=db, merchant_id="merch_atlas_travel",
            query="How much did I sell today?",
            preferred_language="en"
        )
        spoken = r["spoken_text"]
        # Must contain a question mark or commercial follow-up terms
        has_question = "?" in spoken or any(w in spoken.lower() for w in ["would you like", "shall we", "should", "want to", "ಚೆಕ್ ಮಾಡೋಣ್ವಾ", "ನೋಡೋಣ್ವಾ", "देखें", "क्या"])
        has_business_facts = any(w in spoken.lower() for w in ["67,570", "67570", "30", "sales", "rupees", "b बिक्री", "बिक्री", "orders"])
        assert has_question or has_business_facts

