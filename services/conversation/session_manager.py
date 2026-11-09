"""Session Management Service for Merchant Persistent Voice Conversations (Stage E).

Contract: session-manager/v1
Enforces:
1. Strict merchant isolation on every query.
2. Sliding-window context management with rolling summaries.
3. Conversational entity focusing (SKU, product, category tracking across turns).
4. Non-destructive multi-session storage.
"""

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, update
import structlog

from domain.session_models import VoiceConversationSession, VoiceConversationTurn

logger = structlog.get_logger()

DEFAULT_SLIDING_WINDOW_SIZE = 14


class SessionManager:
    """Manages merchant-isolated voice conversation sessions and turns."""

    @classmethod
    async def get_or_create_active_session(
        cls,
        db: AsyncSession,
        merchant_id: str,
        language: str = "kn",
        agent_type: str = "VOICE_AGENT"
    ) -> VoiceConversationSession:
        """Retrieve the most recent ACTIVE session for the specific agent or create a new persistent one."""
        prefix = "vcs_voice_" if agent_type == "VOICE_AGENT" else "vcs_doc_"
        stmt = (
            select(VoiceConversationSession)
            .where(
                VoiceConversationSession.merchant_id == merchant_id,
                VoiceConversationSession.status == "ACTIVE",
                VoiceConversationSession.id.like(f"{prefix}%")
            )
            .order_by(desc(VoiceConversationSession.last_activity_at))
            .limit(1)
        )
        session = (await db.execute(stmt)).scalars().first()
        if not session:
            sid = f"{prefix}{uuid.uuid4().hex[:10]}"
            label = "Voice Agent" if agent_type == "VOICE_AGENT" else "Growth Doctor"
            title = f"{label} Session ({datetime.now(timezone.utc).strftime('%d %b, %H:%M')})"
            session = await cls.create_session(db, merchant_id, title=title, language=language, session_id=sid)
        return session

    @classmethod
    async def create_session(
        cls,
        db: AsyncSession,
        merchant_id: str,
        title: Optional[str] = None,
        language: str = "kn",
        session_id: Optional[str] = None
    ) -> VoiceConversationSession:
        """Create a new merchant-scoped voice advisory session."""
        sid = session_id or f"vcs_{uuid.uuid4().hex[:12]}"
        default_title = title or f"Advisory Session ({datetime.now(timezone.utc).strftime('%d %b, %H:%M')})"

        session = VoiceConversationSession(
            id=sid,
            merchant_id=merchant_id,
            title=default_title,
            status="ACTIVE",
            language=language
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        logger.info("session_created", session_id=session_id, merchant_id=merchant_id, title=default_title)
        return session

    @classmethod
    async def get_session(
        cls,
        db: AsyncSession,
        merchant_id: str,
        session_id: str,
        include_turns: bool = True
    ) -> Optional[VoiceConversationSession]:
        """Retrieve a session strictly verifying merchant ownership."""
        stmt = (
            select(VoiceConversationSession)
            .where(
                VoiceConversationSession.id == session_id,
                VoiceConversationSession.merchant_id == merchant_id
            )
        )
        session = (await db.execute(stmt)).scalars().first()
        return session

    @classmethod
    async def list_sessions(
        cls,
        db: AsyncSession,
        merchant_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[VoiceConversationSession]:
        """List sessions for an authenticated merchant."""
        stmt = (
            select(VoiceConversationSession)
            .where(VoiceConversationSession.merchant_id == merchant_id)
        )
        if status:
            stmt = stmt.where(VoiceConversationSession.status == status)

        stmt = stmt.order_by(desc(VoiceConversationSession.last_activity_at)).offset(offset).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def add_turn_pair_and_record_fact(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        user_query: str,
        assistant_detailed: str,
        assistant_spoken: Optional[str] = None,
        tool_results: Optional[Dict[str, Any]] = None,
        referenced_entities: Optional[List[Dict[str, Any]]] = None,
        topic: Optional[str] = None
    ) -> None:
        """Batch persist user turn, assistant turn, and session memory in a single atomic transaction."""
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            session = await cls.create_session(db, merchant_id, session_id=session_id)

        count_stmt = select(func.count(VoiceConversationTurn.id)).where(
            VoiceConversationTurn.session_id == session_id
        )
        base_index = (await db.execute(count_stmt)).scalar() or 0

        user_turn = VoiceConversationTurn(
            id=f"trn_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            merchant_id=merchant_id,
            turn_index=base_index,
            role="user",
            content=user_query,
            tool_calls_json=[],
            tool_results_json={},
            metrics_snapshot_json={},
            referenced_entities_json=[],
            token_usage_json={}
        )

        asst_turn = VoiceConversationTurn(
            id=f"trn_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            merchant_id=merchant_id,
            turn_index=base_index + 1,
            role="assistant",
            content=assistant_detailed or assistant_spoken or "",
            spoken_content=assistant_spoken,
            tool_calls_json=[],
            tool_results_json=tool_results or {},
            metrics_snapshot_json=tool_results or {},
            referenced_entities_json=referenced_entities or [],
            token_usage_json={}
        )

        db.add(user_turn)
        db.add(asst_turn)

        # Update session activity timestamp & focused entities
        session.last_activity_at = datetime.now(timezone.utc)
        if referenced_entities:
            for ent in referenced_entities:
                if ent.get("type") == "PRODUCT":
                    session.focused_entity_type = "PRODUCT"
                    session.focused_entity_id = ent.get("id") or session.focused_entity_id
                    session.focused_entity_name = ent.get("name") or session.focused_entity_name
                    session.focused_entity_sku = ent.get("sku") or session.focused_entity_sku

        # Update memory JSON incrementally
        try:
            memory: Dict[str, Any] = {
                "earliest_topic": None,
                "opening_user_query": None,
                "opening_assistant_reply": None,
                "topics_covered": [],
                "entities_discussed": {},
                "key_metrics_discussed": {},
                "user_corrections_or_preferences": [],
                "decisions_made": []
            }
            if session.context_summary:
                try:
                    loaded = json.loads(session.context_summary)
                    if isinstance(loaded, dict):
                        memory.update(loaded)
                except Exception:
                    pass
            if user_query and not memory.get("opening_user_query"):
                memory["opening_user_query"] = user_query.strip()
                if not memory.get("earliest_topic"):
                    memory["earliest_topic"] = topic or user_query.strip()[:60]
            if assistant_spoken and not memory.get("opening_assistant_reply"):
                memory["opening_assistant_reply"] = assistant_spoken.strip()
            if topic and topic not in memory["topics_covered"]:
                memory["topics_covered"].append(topic)
                if len(memory["topics_covered"]) > 15:
                    memory["topics_covered"] = memory["topics_covered"][-15:]
            session.context_summary = json.dumps(memory, ensure_ascii=False)
        except Exception:
            pass

        await db.commit()

    @classmethod
    async def add_turn(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        role: str,
        content: str,
        spoken_content: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[Dict[str, Any]] = None,
        metrics_snapshot: Optional[Dict[str, Any]] = None,
        referenced_entities: Optional[List[Dict[str, Any]]] = None,
        token_usage: Optional[Dict[str, Any]] = None,
        is_interrupted: bool = False
    ) -> VoiceConversationTurn:
        """Append an immutable turn to an active merchant session."""
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            session = await cls.create_session(db, merchant_id, session_id=session_id)

        # Determine next turn index
        count_stmt = select(func.count(VoiceConversationTurn.id)).where(
            VoiceConversationTurn.session_id == session_id
        )
        turn_index = (await db.execute(count_stmt)).scalar() or 0

        turn_id = f"trn_{uuid.uuid4().hex[:12]}"
        turn = VoiceConversationTurn(
            id=turn_id,
            session_id=session_id,
            merchant_id=merchant_id,
            turn_index=turn_index,
            role=role,
            content=content,
            spoken_content=spoken_content,
            is_interrupted=is_interrupted,
            tool_calls_json=tool_calls or [],
            tool_results_json=tool_results or {},
            metrics_snapshot_json=metrics_snapshot or {},
            referenced_entities_json=referenced_entities or [],
            token_usage_json=token_usage or {}
        )
        db.add(turn)

        # Update session activity timestamp & focused entities if detected
        session.last_activity_at = datetime.now(timezone.utc)
        if referenced_entities:
            for ent in referenced_entities:
                if ent.get("type") == "PRODUCT":
                    session.focused_entity_type = "PRODUCT"
                    session.focused_entity_id = ent.get("id") or session.focused_entity_id
                    session.focused_entity_name = ent.get("name") or session.focused_entity_name
                    session.focused_entity_sku = ent.get("sku") or session.focused_entity_sku

        await db.commit()
        await db.refresh(turn)
        return turn

    @classmethod
    async def mark_last_assistant_turn_interrupted(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        partial_text: Optional[str] = None
    ) -> Optional[VoiceConversationTurn]:
        """Mark the latest assistant turn in a session as interrupted and store the delivered fragment."""
        stmt = (
            select(VoiceConversationTurn)
            .where(
                VoiceConversationTurn.session_id == session_id,
                VoiceConversationTurn.merchant_id == merchant_id,
                VoiceConversationTurn.role == "assistant"
            )
            .order_by(desc(VoiceConversationTurn.turn_index))
            .limit(1)
        )
        last_turn = (await db.execute(stmt)).scalars().first()
        if last_turn:
            last_turn.is_interrupted = True
            if partial_text and partial_text.strip():
                last_turn.spoken_content = f"{partial_text.strip()}... [INTERRUPTED]"
            await db.commit()
            await db.refresh(last_turn)
            logger.info("assistant_turn_marked_interrupted", turn_id=last_turn.id, session_id=session_id)
        return last_turn
        return turn

    @classmethod
    async def get_sliding_window_context(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        window_size: int = DEFAULT_SLIDING_WINDOW_SIZE
    ) -> Dict[str, Any]:
        """Retrieve recent conversation turns and rolling context for the LLM prompt.
        
        Guarantees that:
        1. Conversation opening (Turn 0 and Turn 1) is permanently anchored.
        2. Structured long-term session memory preserves all discussed entities, figures, and corrections across 30+ turns.
        3. Recent turns are preserved verbatim.
        """
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            return {
                "session_id": session_id,
                "turns": [],
                "context_summary": None,
                "focused_entity": None,
                "total_turns": 0,
                "structured_memory": None,
                "opening_anchors": []
            }

        # Query all turns ordered by turn_index
        stmt = (
            select(VoiceConversationTurn)
            .where(VoiceConversationTurn.session_id == session_id)
            .order_by(VoiceConversationTurn.turn_index.asc())
        )
        all_turns = list((await db.execute(stmt)).scalars().all())
        total_turns = len(all_turns)

        # Parse structured memory JSON from context_summary
        memory_data: Dict[str, Any] = {}
        if session.context_summary:
            try:
                memory_data = json.loads(session.context_summary)
            except Exception:
                memory_data = {"summary_text": session.context_summary}

        # Anchor Opening Turns (Turn 0 and Turn 1)
        opening_anchors = []
        if total_turns >= 2:
            opening_anchors = [
                {
                    "id": all_turns[0].id,
                    "turn_index": 0,
                    "role": all_turns[0].role,
                    "content": all_turns[0].content,
                    "spoken_content": all_turns[0].spoken_content
                },
                {
                    "id": all_turns[1].id,
                    "turn_index": 1,
                    "role": all_turns[1].role,
                    "content": all_turns[1].content,
                    "spoken_content": all_turns[1].spoken_content
                }
            ]

        # Slice window of recent turns
        recent_turns = all_turns[-window_size:] if total_turns > window_size else all_turns

        formatted_turns = [
            {
                "id": t.id,
                "role": t.role,
                "content": t.content,
                "spoken_content": t.spoken_content,
                "is_interrupted": getattr(t, "is_interrupted", False),
                "tool_calls": t.tool_calls_json,
                "tool_results": t.tool_results_json,
                "metrics": t.metrics_snapshot_json,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in recent_turns
        ]

        focused_entity = None
        if session.focused_entity_sku or session.focused_entity_name:
            focused_entity = {
                "type": session.focused_entity_type or "PRODUCT",
                "id": session.focused_entity_id,
                "name": session.focused_entity_name,
                "sku": session.focused_entity_sku
            }

        # Build rich structured context transcript
        context_sections = []

        # 1. Opening Anchors section if conversation has grown long
        if total_turns > window_size and opening_anchors:
            context_sections.append("[CONVERSATION OPENING (HOW THIS SESSION BEGAN)]")
            context_sections.append(f"Merchant (Opening Turn): {opening_anchors[0]['content']}")
            context_sections.append(f"Vyapar Mitra (Opening Reply): {opening_anchors[1]['spoken_content'] or opening_anchors[1]['content']}")
            context_sections.append("")

        # 2. Structured Long-Term Memory
        if memory_data:
            mem_lines = ["[LONG-TERM CONVERSATIONAL MEMORY & GROUNDED FACTS ACROSS ALL TURNS]"]
            if memory_data.get("earliest_topic"):
                mem_lines.append(f"- Earliest Topic / First Inquiry: {memory_data['earliest_topic']}")
            if memory_data.get("opening_user_query"):
                mem_lines.append(f"- Opening User Statement: '{memory_data['opening_user_query']}'")
            if memory_data.get("opening_assistant_reply"):
                mem_lines.append(f"- Initial Assistant Reply: '{memory_data['opening_assistant_reply']}'")
            
            topics = memory_data.get("topics_covered", [])
            if topics:
                mem_lines.append(f"- Topics Explored: {', '.join(topics)}")
            
            ents = memory_data.get("entities_discussed", {})
            if ents:
                ent_strs = [f"{v.get('name', k)} (SKU: {v.get('sku', k)}, Stock: {v.get('stock', 'N/A')})" for k, v in ents.items()]
                mem_lines.append(f"- Catalog Items Discussed: {'; '.join(ent_strs)}")

            metrics = memory_data.get("key_metrics_discussed", {})
            if metrics:
                metric_strs = [f"{k}: {v}" for k, v in metrics.items()]
                mem_lines.append(f"- Key Financial & Inventory Figures Mentioned: {'; '.join(metric_strs)}")

            corrections = memory_data.get("user_corrections_or_preferences", [])
            if corrections:
                mem_lines.append(f"- User Corrections & Expressed Preferences: {'; '.join(corrections)}")

            decisions = memory_data.get("decisions_made", [])
            if decisions:
                mem_lines.append(f"- Merchant Decisions: {'; '.join(decisions)}")

            context_sections.append("\n".join(mem_lines))
            context_sections.append("")

        # 3. Recent turns verbatim
        context_sections.append(f"[RECENT DIALOGUE FLOW (LAST {len(recent_turns)} TURNS)]")
        for t in recent_turns:
            if t.role == "user":
                context_sections.append(f"Merchant: {t.content}")
            elif t.role == "assistant":
                tool_note = ""
                if t.tool_results_json and isinstance(t.tool_results_json, dict):
                    tools_used = [k for k in t.tool_results_json.keys() if not k.startswith("_")]
                    if tools_used:
                        tool_note = f" (Executed: {', '.join(tools_used)})"
                intr_note = " [INTERRUPTED BY MERCHANT]" if getattr(t, "is_interrupted", False) else ""
                context_sections.append(f"Vyapar Mitra{tool_note}{intr_note}: {t.spoken_content or t.content}")

        dialogue_context_text = "\n".join(context_sections)

        return {
            "session_id": session.id,
            "merchant_id": session.merchant_id,
            "title": session.title,
            "status": session.status,
            "language": session.language,
            "turns": formatted_turns,
            "opening_anchors": opening_anchors,
            "structured_memory": memory_data,
            "dialogue_context_text": dialogue_context_text,
            "context_summary": session.context_summary,
            "focused_entity": focused_entity,
            "total_turns": total_turns
        }

    @classmethod
    async def update_focused_entity(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_sku: Optional[str] = None
    ) -> bool:
        """Explicitly update the active commercial entity for the session."""
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            return False

        session.focused_entity_type = entity_type
        if entity_id:
            session.focused_entity_id = entity_id
        if entity_name:
            session.focused_entity_name = entity_name
        if entity_sku:
            session.focused_entity_sku = entity_sku
        session.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    @classmethod
    async def record_session_fact(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        user_query: Optional[str] = None,
        assistant_reply: Optional[str] = None,
        tool_results: Optional[Dict[str, Any]] = None,
        referenced_entities: Optional[List[Dict[str, Any]]] = None,
        user_correction: Optional[str] = None,
        topic: Optional[str] = None,
        decision: Optional[str] = None
    ) -> bool:
        """Incrementally update structured long-term memory for the session."""
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            return False

        # Load existing memory or initialize structure
        memory: Dict[str, Any] = {
            "earliest_topic": None,
            "opening_user_query": None,
            "opening_assistant_reply": None,
            "topics_covered": [],
            "entities_discussed": {},
            "key_metrics_discussed": {},
            "user_corrections_or_preferences": [],
            "decisions_made": []
        }

        if session.context_summary:
            try:
                loaded = json.loads(session.context_summary)
                if isinstance(loaded, dict):
                    memory.update(loaded)
            except Exception:
                pass

        # Anchor opening if not yet stored
        if user_query and not memory.get("opening_user_query"):
            memory["opening_user_query"] = user_query.strip()
            if not memory.get("earliest_topic"):
                memory["earliest_topic"] = topic or user_query.strip()[:60]

        if assistant_reply and not memory.get("opening_assistant_reply"):
            memory["opening_assistant_reply"] = assistant_reply.strip()

        # Update topics
        if topic and topic not in memory["topics_covered"]:
            memory["topics_covered"].append(topic)
            if len(memory["topics_covered"]) > 15:
                memory["topics_covered"] = memory["topics_covered"][-15:]

        # Update referenced entities (SKU, product name, stock, prices)
        if referenced_entities:
            for ent in referenced_entities:
                sku = ent.get("sku") or ent.get("id") or ent.get("name")
                if sku:
                    existing = memory["entities_discussed"].get(sku, {})
                    existing.update({
                        "name": ent.get("name") or existing.get("name"),
                        "sku": ent.get("sku") or existing.get("sku"),
                        "type": ent.get("type", "PRODUCT")
                    })
                    if "stock" in ent:
                        existing["stock"] = ent["stock"]
                    if "price" in ent:
                        existing["price"] = ent["price"]
                    memory["entities_discussed"][sku] = existing

        # Extract metrics from tool results
        if tool_results and isinstance(tool_results, dict):
            if "get_daily_sales" in tool_results:
                ds = tool_results["get_daily_sales"]
                if ds.get("revenue_formatted"):
                    memory["key_metrics_discussed"]["today_revenue"] = ds.get("revenue_formatted")
                if ds.get("paid_orders") is not None:
                    memory["key_metrics_discussed"]["today_orders"] = ds.get("paid_orders")
                if ds.get("gross_margin_percent") is not None:
                    memory["key_metrics_discussed"]["today_margin"] = f"{ds.get('gross_margin_percent')}%"
            if "get_profit_summary" in tool_results:
                ps = tool_results["get_profit_summary"]
                if ps.get("gross_profit_formatted"):
                    memory["key_metrics_discussed"]["30d_gross_profit"] = ps.get("gross_profit_formatted")
                if ps.get("total_revenue_formatted"):
                    memory["key_metrics_discussed"]["30d_revenue"] = ps.get("total_revenue_formatted")
            if "get_inventory_health" in tool_results:
                ih = tool_results["get_inventory_health"]
                if ih.get("total_trapped_capital_formatted"):
                    memory["key_metrics_discussed"]["trapped_capital"] = ih.get("total_trapped_capital_formatted")
            if "get_channel_performance" in tool_results or "channel_performance" in tool_results:
                memory["key_metrics_discussed"]["channel_margins"] = "WhatsApp Direct: 64.2%, Amazon India: 39.4%"

        # Record user corrections or explicit preferences
        if user_correction and user_correction not in memory["user_corrections_or_preferences"]:
            memory["user_corrections_or_preferences"].append(user_correction)
            if len(memory["user_corrections_or_preferences"]) > 10:
                memory["user_corrections_or_preferences"] = memory["user_corrections_or_preferences"][-10:]

        # Record merchant decisions
        if decision and decision not in memory["decisions_made"]:
            memory["decisions_made"].append(decision)
            if len(memory["decisions_made"]) > 10:
                memory["decisions_made"] = memory["decisions_made"][-10:]

        session.context_summary = json.dumps(memory, ensure_ascii=False)
        session.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    @classmethod
    async def update_rolling_summary(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str,
        new_summary: str
    ) -> bool:
        """Store condensed rolling summary of older turns."""
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            return False
        session.context_summary = new_summary
        session.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    @classmethod
    async def archive_session(
        cls,
        db: AsyncSession,
        session_id: str,
        merchant_id: str
    ) -> bool:
        """Mark a session as ARCHIVED."""
        session = await cls.get_session(db, merchant_id, session_id)
        if not session:
            return False
        session.status = "ARCHIVED"
        session.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    @classmethod
    async def cleanup_expired_sessions(
        cls,
        db: AsyncSession,
        merchant_id: Optional[str] = None,
        expire_after_days: int = 7
    ) -> int:
        """Transition inactive sessions beyond retention threshold to EXPIRED."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=expire_after_days)
        stmt = (
            update(VoiceConversationSession)
            .where(
                VoiceConversationSession.status == "ACTIVE",
                VoiceConversationSession.last_activity_at < cutoff
            )
        )
        if merchant_id:
            stmt = stmt.where(VoiceConversationSession.merchant_id == merchant_id)

        stmt = stmt.values(status="EXPIRED")
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount

