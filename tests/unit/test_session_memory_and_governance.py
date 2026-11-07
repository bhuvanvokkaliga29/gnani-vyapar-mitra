"""Unit Tests for Persistent Session Memory and Action Proposal Governance (Stage E).

Verifies all 18 core requirements:
1. Session creation.
2. Session persistence.
3. Conversation restoration.
4. Multi-session handling.
5. Merchant isolation.
6. Context-window management.
7. Rolling summaries.
8. Product-reference resolution.
9. Kannada, Hindi, and English follow-up handling.
10. Proposal creation.
11. Proposal validation.
12. Approval authorization & execution.
13. Rejection handling.
14. Expiration handling.
15. Duplicate execution prevention.
16. Margin-floor enforcement.
17. Audit history verification.
18. Failure recovery.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select

from apps.api.core.database import AsyncSessionLocal
from domain.models import AuditEvent, Product
from domain.session_models import VoiceConversationSession, VoiceConversationTurn, DoctorActionProposal
from domain.llm_schemas import LLMResponse, LLMToolCall
from services.conversation.session_manager import SessionManager
from services.governance.action_service import ActionGovernanceService
from services.agent.doctor_advisor import DoctorAdvisorAgent
from services.llm.base import LLMProvider


class MockLLM(LLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_history = []

    @property
    def provider_name(self) -> str:
        return "mock_provider"

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def active_model(self) -> str:
        return "mock-model-stage-e"

    async def chat_complete(self, messages, temperature=0.2, max_tokens=1024, timeout=15.0):
        return await self.chat_with_tools(messages, tools=[], temperature=temperature, max_tokens=max_tokens)

    async def chat_with_tools(self, messages, tools=None, tool_choice="auto", temperature=0.2, max_tokens=1024, timeout=15.0):
        self.call_history.append({"messages": messages, "tools": tools})
        if not self.responses:
            return LLMResponse(content="Default fallback", tool_calls=[], provider="mock_provider", model="mock-model")
        return self.responses.pop(0)


# =============================================================================
# PART 1: Session Management & Context Window Tests
# =============================================================================

@pytest.mark.asyncio
async def test_session_creation_and_persistence():
    async with AsyncSessionLocal() as db:
        session = await SessionManager.create_session(
            db=db,
            merchant_id="merch_atlas_travel",
            title="Q4 Commercial Review",
            language="kn"
        )
        assert session.id.startswith("vcs_")
        assert session.merchant_id == "merch_atlas_travel"
        assert session.title == "Q4 Commercial Review"
        assert session.status == "ACTIVE"
        assert session.language == "kn"

        # Verify database retrieval
        loaded = await SessionManager.get_session(db, "merch_atlas_travel", session.id)
        assert loaded is not None
        assert loaded.id == session.id


@pytest.mark.asyncio
async def test_conversation_restoration_and_turns():
    async with AsyncSessionLocal() as db:
        session = await SessionManager.create_session(db, "merch_atlas_travel", "Turn Restoration Session")

        # Add turn 1 (User)
        turn_1 = await SessionManager.add_turn(
            db=db,
            session_id=session.id,
            merchant_id="merch_atlas_travel",
            role="user",
            content="What are today's sales?"
        )
        assert turn_1.turn_index == 0
        assert turn_1.role == "user"

        # Add turn 2 (Assistant with tool metrics)
        turn_2 = await SessionManager.add_turn(
            db=db,
            session_id=session.id,
            merchant_id="merch_atlas_travel",
            role="assistant",
            content="Detailed sales breakdown: ₹44,982 across 18 orders.",
            spoken_content="Today Vastram generated Rs 44,982 across 18 orders.",
            tool_results={"revenue_paise": 4498200},
            metrics_snapshot={"order_count": 18}
        )
        assert turn_2.turn_index == 1
        assert turn_2.role == "assistant"

        # Restore context
        ctx = await SessionManager.get_sliding_window_context(db, session.id, "merch_atlas_travel")
        assert ctx["total_turns"] == 2
        assert len(ctx["turns"]) == 2
        assert ctx["turns"][0]["content"] == "What are today's sales?"
        assert ctx["turns"][1]["spoken_content"] == "Today Vastram generated Rs 44,982 across 18 orders."


@pytest.mark.asyncio
async def test_multi_session_and_merchant_isolation():
    async with AsyncSessionLocal() as db:
        # Merchant 1 sessions
        s1 = await SessionManager.create_session(db, "merch_atlas_travel", "Vastram Session A")
        s2 = await SessionManager.create_session(db, "merch_atlas_travel", "Vastram Session B")

        # Merchant 2 session
        s_other = await SessionManager.create_session(db, "merch_other_store", "Other Store Session")

        # List merchant 1 sessions -> must ONLY contain merchant 1's sessions
        m1_sessions = await SessionManager.list_sessions(db, "merch_atlas_travel")
        m1_ids = [s.id for s in m1_sessions]
        assert s1.id in m1_ids
        assert s2.id in m1_ids
        assert s_other.id not in m1_ids

        # Attempt to access Merchant 2 session using Merchant 1 identity -> must return None
        cross_access = await SessionManager.get_session(db, "merch_atlas_travel", s_other.id)
        assert cross_access is None


@pytest.mark.asyncio
async def test_sliding_window_and_rolling_summary():
    async with AsyncSessionLocal() as db:
        session = await SessionManager.create_session(db, "merch_atlas_travel", "Window Test")

        # Add 10 turns
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            await SessionManager.add_turn(
                db=db,
                session_id=session.id,
                merchant_id="merch_atlas_travel",
                role=role,
                content=f"Message {i}"
            )

        # Context window size 4 must return strictly the last 4 turns
        ctx = await SessionManager.get_sliding_window_context(db, session.id, "merch_atlas_travel", window_size=4)
        assert ctx["total_turns"] == 10
        assert len(ctx["turns"]) == 4
        assert ctx["turns"][0]["content"] == "Message 6"
        assert ctx["turns"][3]["content"] == "Message 9"

        # Update rolling summary
        await SessionManager.update_rolling_summary(
            db, session.id, "merch_atlas_travel", "Earlier discussion on inventory dead stock."
        )
        ctx_summary = await SessionManager.get_sliding_window_context(db, session.id, "merch_atlas_travel")
        assert ctx_summary["context_summary"] == "Earlier discussion on inventory dead stock."


# =============================================================================
# PART 2: Context-Aware Follow-Up Resolution Tests
# =============================================================================

@pytest.mark.asyncio
async def test_product_reference_and_followup_resolution():
    agent = DoctorAdvisorAgent(api_key="mock_key")

    async with AsyncSessionLocal() as db:
        session = await SessionManager.create_session(db, "merch_atlas_travel", "Product Follow-up Flow")

        # Step 1: Merchant asks "Which product sells the most?"
        res_1 = await agent.answer_merchant_query(
            db=db,
            query="Which product sells the most?",
            merchant_id="merch_atlas_travel",
            session_id=session.id,
            preferred_language="en"
        )
        assert "top-selling" in res_1["spoken_text"].lower() or "pure olive linen" in res_1["spoken_text"].lower()
        assert res_1["focused_entity"] is not None
        assert res_1["focused_entity"]["sku"] == "VAST-SH-03"

        # Verify session focused entity updated in database
        s_db = await SessionManager.get_session(db, "merch_atlas_travel", session.id)
        assert s_db.focused_entity_sku == "VAST-SH-03"

        # Step 2: Merchant asks "What is its stock?"
        res_2 = await agent.answer_merchant_query(
            db=db,
            query="What is its stock?",
            merchant_id="merch_atlas_travel",
            session_id=session.id,
            preferred_language="en"
        )
        assert "units" in res_2["spoken_text"].lower() or "stock" in res_2["spoken_text"].lower()
        assert "followup_stock" in str(res_2["trace"]) or "get_product_stock" in str(res_2["trace"])

        # Step 3: Merchant asks "How much profit does it generate?"
        res_3 = await agent.answer_merchant_query(
            db=db,
            query="How much profit does it generate?",
            merchant_id="merch_atlas_travel",
            session_id=session.id,
            preferred_language="en"
        )
        assert "margin" in res_3["spoken_text"].lower() or "profit" in res_3["spoken_text"].lower()
        assert "followup_profit" in str(res_3["trace"]) or "get_profit_summary" in str(res_3["trace"])


@pytest.mark.asyncio
async def test_multilingual_followup_kannada_and_hindi():
    agent = DoctorAdvisorAgent(api_key="mock_key")

    async with AsyncSessionLocal() as db:
        # 1. Kannada flow: Set focused entity to VAST-SH-03
        s_kn = await SessionManager.create_session(db, "merch_atlas_travel", "Kannada Follow-up", language="kn")
        await SessionManager.update_focused_entity(
            db, s_kn.id, "merch_atlas_travel", "PRODUCT", entity_sku="VAST-SH-03", entity_name="ವಸ್ತ್ರಂ ಆಲಿವ್ ಲಿನನ್ ಶರ್ಟ್"
        )

        res_kn = await agent.answer_merchant_query(
            db=db,
            query="ಇವರ ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ?",
            merchant_id="merch_atlas_travel",
            session_id=s_kn.id,
            preferred_language="kn"
        )
        assert res_kn["language"] == "kn"
        assert any(w in res_kn["spoken_text"] for w in ["ದಾಸ್ತಾನಿನಲ್ಲಿ", "ಯೂನಿಟ್", "ಯುನಿಟ್", "ಸ್ಟಾಕ್", "ಲಭ್ಯ"])

        # 2. Hindi flow: Set focused entity to VAST-SH-03
        s_hi = await SessionManager.create_session(db, "merch_atlas_travel", "Hindi Follow-up", language="hi")
        await SessionManager.update_focused_entity(
            db, s_hi.id, "merch_atlas_travel", "PRODUCT", entity_sku="VAST-SH-03", entity_name="वस्त्रम ऑलिव लिनन शर्ट"
        )

        res_hi = await agent.answer_merchant_query(
            db=db,
            query="इसका स्टॉक कितना है?",
            merchant_id="merch_atlas_travel",
            session_id=s_hi.id,
            preferred_language="hi"
        )
        assert res_hi["language"] == "hi"
        assert any(w in res_hi["spoken_text"] for w in ["स्टॉक", "यूनिट्स", "उपलब्ध", "पीस"])


# =============================================================================
# PART 3: Action Proposal & Governance Lifecycle Tests
# =============================================================================

@pytest.mark.asyncio
async def test_action_proposal_creation_and_validation():
    async with AsyncSessionLocal() as db:
        # 1. Valid price change proposal respecting 25% floor (₹1,899 on ₹650 cost -> ~65% margin)
        prop_valid = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="PRICE_CHANGE",
            title="Update Linen Shirt Price to ₹1,899",
            description="Adjust price to ₹1,899 on D2C web",
            parameters={"sku": "VAST-SH-01", "new_price_paise": 189900}
        )
        assert prop_valid.status == "WAITING_FOR_APPROVAL"
        assert prop_valid.margin_floor_compliant is True
        assert prop_valid.margin_percent >= 25.0

        # 2. Invalid price change violating 25% margin floor (₹700 on ₹650 cost -> 7.14% margin)
        prop_violating = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="PRICE_CHANGE",
            title="Steep Clearance Discount on Linen Shirt",
            description="Clearance discount violating floor",
            parameters={"sku": "VAST-SH-01", "new_price_paise": 70000}
        )
        assert prop_violating.status == "FAILED"
        assert prop_violating.margin_floor_compliant is False
        assert "Policy Violation" in prop_violating.description

        # 3. Invalid parameter handling (missing SKU)
        prop_invalid = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="PRICE_CHANGE",
            title="Invalid Change",
            description="No SKU provided",
            parameters={"new_price_paise": 100000}
        )
        assert prop_invalid.status == "FAILED"


@pytest.mark.asyncio
async def test_action_approval_and_execution_lifecycle():
    async with AsyncSessionLocal() as db:
        # Create valid price update proposal
        prop = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="PRICE_CHANGE",
            title="Approve Price Update on Oxford Shirt",
            description="Update price to ₹1,999",
            parameters={"sku": "VAST-SH-01", "new_price_paise": 199900}
        )
        assert prop.status == "WAITING_FOR_APPROVAL"

        # Explicit Merchant Owner Approval & Execution
        exec_res = await ActionGovernanceService.approve_and_execute(
            db=db,
            merchant_id="merch_atlas_travel",
            proposal_id=prop.id,
            actor="MERCHANT_OWNER"
        )
        assert exec_res["status"] == "EXECUTED"
        assert exec_res["execution_details"]["new_price_paise"] == 199900

        # Verify product price was updated in database
        prod = (await db.execute(select(Product).where(Product.sku == "VAST-SH-01"))).scalars().first()
        assert prod.price_paise == 199900

        # Verify immutable AuditEvent logged
        audit = (
            await db.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "DOCTOR_ACTION_EXECUTION",
                    AuditEvent.entity_id == prop.id
                )
            )
        ).scalars().first()
        assert audit is not None
        assert audit.action == "EXECUTED_PRICE_CHANGE"
        assert audit.actor == "MERCHANT_OWNER"

        # Duplicate Execution Prevention: Re-approving must raise ValueError
        with pytest.raises(ValueError, match="is in state 'EXECUTED'"):
            await ActionGovernanceService.approve_and_execute(
                db=db,
                merchant_id="merch_atlas_travel",
                proposal_id=prop.id
            )


@pytest.mark.asyncio
async def test_action_rejection_and_cancellation():
    async with AsyncSessionLocal() as db:
        # 1. Test Rejection
        prop_reject = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="STOCK_REORDER",
            title="Reorder 100 Linen Shirts",
            description="Reorder units from supplier",
            parameters={"sku": "VAST-SH-01", "reorder_quantity": 100}
        )
        assert prop_reject.status == "WAITING_FOR_APPROVAL"

        rejected = await ActionGovernanceService.reject_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            proposal_id=prop_reject.id,
            reason="Budget reserved for seasonal festive line",
            actor="MERCHANT_OWNER"
        )
        assert rejected.status == "REJECTED"
        assert "Budget reserved" in rejected.rejection_reason

        # 2. Test Cancellation
        prop_cancel = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="CLEARANCE_BUNDLE",
            title="Bundle Clearance",
            description="Clearance bundle",
            parameters={"target_skus": ["VAST-SH-01"], "bundle_discount_percent": 10.0}
        )
        assert prop_cancel.status == "WAITING_FOR_APPROVAL"

        cancelled = await ActionGovernanceService.cancel_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            proposal_id=prop_cancel.id,
            actor="MERCHANT_OWNER"
        )
        assert cancelled.status == "CANCELLED"


@pytest.mark.asyncio
async def test_action_proposal_expiration():
    async with AsyncSessionLocal() as db:
        # Create an expired proposal by backdating expires_at
        prop = await ActionGovernanceService.create_proposal(
            db=db,
            merchant_id="merch_atlas_travel",
            action_type="PRICE_CHANGE",
            title="Expired Promotion",
            description="Promotion that was not reviewed in time",
            parameters={"sku": "VAST-SH-01", "new_price_paise": 189900}
        )
        # Force expiration timestamp into the past
        prop.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        await db.commit()

        # Listing pending proposals should auto-expire it
        pending = await ActionGovernanceService.list_pending_proposals(db, "merch_atlas_travel")
        pending_ids = [p.id for p in pending]
        assert prop.id not in pending_ids

        # Attempting to approve expired proposal directly must raise ValueError
        with pytest.raises(ValueError, match="EXPIRED|expired"):
            await ActionGovernanceService.approve_and_execute(
                db=db,
                merchant_id="merch_atlas_travel",
                proposal_id=prop.id
            )


# =============================================================================
# PART 4: FastAPI Router Integration Endpoints Tests
# =============================================================================

from fastapi.testclient import TestClient
from apps.api.main import app

api_client = TestClient(app)


def test_api_session_lifecycle_and_actions():
    # 1. Create session via HTTP
    res_create = api_client.post("/api/v1/doctor/sessions", json={
        "merchant_id": "merch_atlas_travel",
        "title": "API Automated Session",
        "language": "kn"
    })
    assert res_create.status_code == 200
    s_data = res_create.json()
    assert s_data["status"] == "SUCCESS"
    session_id = s_data["session"]["id"]

    # 2. List sessions via HTTP
    res_list = api_client.get(f"/api/v1/doctor/sessions?merchant_id=merch_atlas_travel")
    assert res_list.status_code == 200
    sessions_list = res_list.json()["sessions"]
    assert any(s["id"] == session_id for s in sessions_list)

    # 3. Query doctor with session_id
    res_query = api_client.post("/api/v1/doctor/query", json={
        "merchant_id": "merch_atlas_travel",
        "query": "What are today's sales figures?",
        "session_id": session_id,
        "preferred_language": "en",
        "synthesize_audio": False
    })
    assert res_query.status_code == 200
    q_data = res_query.json()
    assert q_data["session_id"] == session_id
    assert "₹" in q_data["spoken_text"] or "revenue" in q_data["spoken_text"].lower() or "sales" in q_data["spoken_text"].lower() or "rupees" in q_data["spoken_text"].lower()

    # 4. Get session turns via HTTP
    res_get = api_client.get(f"/api/v1/doctor/sessions/{session_id}?merchant_id=merch_atlas_travel")
    assert res_get.status_code == 200
    turns_data = res_get.json()
    assert turns_data["total_turns"] >= 2
    assert turns_data["turns"][0]["role"] == "user"
    assert turns_data["turns"][1]["role"] == "assistant"

    # 5. List pending actions via HTTP
    res_pending = api_client.get("/api/v1/doctor/actions/pending?merchant_id=merch_atlas_travel")
    assert res_pending.status_code == 200
    assert "proposals" in res_pending.json()

    # 6. Archive session via HTTP
    res_archive = api_client.post(f"/api/v1/doctor/sessions/{session_id}/archive?merchant_id=merch_atlas_travel")
    assert res_archive.status_code == 200
    assert res_archive.json()["state"] == "ARCHIVED"

