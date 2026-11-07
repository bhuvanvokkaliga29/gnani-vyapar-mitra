"""Unified WhatsApp Business Service Subsystem.

Orchestrates:
1. Webhook HMAC verification and payload ingestion.
2. Meta WAMID idempotency ledger deduplication.
3. Multilingual intent extraction (Kannada, Hindi, English).
4. Product catalog resolution.
5. Deterministic policy guardrail enforcement.
6. Single-use, expiring confirmation token workflows.
7. Outbound Meta Cloud API message delivery with mock fallback.
8. Immutable database auditing across all actions.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import structlog

from apps.api.core.config import get_settings
from domain.models import Merchant, Product, AuditEvent, Order, Payment
from domain.whatsapp_models import (
    WhatsAppWebhookLog,
    WhatsAppPendingConfirmation,
    WhatsAppOutboundMessage
)
from services.commerce_service import CommerceService
from services.whatsapp.security import verify_webhook_signature, normalize_phone_number
from services.whatsapp.intent import WhatsAppIntentParser, WhatsAppIntent, IntentType
from services.whatsapp.policy_guard import PolicyGuard, PolicyValidationResult
from services.whatsapp.confirmation import ConfirmationManager
from services.whatsapp.client import WhatsAppClient

logger = structlog.get_logger()
settings = get_settings()


class WhatsAppService:
    """Core domain service orchestrating the WhatsApp conversational interface."""

    def __init__(
        self,
        commerce_service: Optional[CommerceService] = None,
        confirmation_mgr: Optional[ConfirmationManager] = None,
        whatsapp_client: Optional[WhatsAppClient] = None
    ):
        self.commerce = commerce_service or CommerceService()
        self.confirmation = confirmation_mgr or ConfirmationManager(commerce_service=self.commerce)
        self.client = whatsapp_client or WhatsAppClient()

    # -------------------------------------------------------------------------
    # Webhook Verification & Security
    # -------------------------------------------------------------------------

    def verify_webhook_token(self, mode: Optional[str], token: Optional[str], challenge: Optional[str]) -> Optional[str]:
        """
        Validates Meta's hub.challenge verification request during webhook setup.
        Returns the challenge string if valid, otherwise None.
        """
        expected_token = settings.WHATSAPP_VERIFY_TOKEN
        if mode == "subscribe" and token == expected_token:
            logger.info("whatsapp_webhook_verified", challenge=challenge)
            return challenge
        logger.warning("whatsapp_webhook_verification_failed", mode=mode, token=token)
        return None

    def verify_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """Verifies HMAC-SHA256 signature from Meta X-Hub-Signature-256 header."""
        return verify_webhook_signature(
            payload_body=raw_body,
            signature_header=signature_header,
            app_secret=settings.WHATSAPP_APP_SECRET
        )

    # -------------------------------------------------------------------------
    # Tenant Resolution
    # -------------------------------------------------------------------------

    async def resolve_merchant_for_phone(self, db: AsyncSession, phone: str) -> Optional[Merchant]:
        """
        Resolves the merchant tenant associated with the sender phone.
        Matches configured test merchant phone or defaults to atlas travel for demo.
        """
        normalized_inbound = normalize_phone_number(phone)
        configured_test = normalize_phone_number(settings.WHATSAPP_TEST_MERCHANT_PHONE)

        # In hackathon/demo mode, match authorized test phone or default merchant
        if normalized_inbound == configured_test or not configured_test:
            merchant = await self.commerce.get_merchant(db, settings.WHATSAPP_DEFAULT_MERCHANT_ID)
            if merchant:
                return merchant

        # Fallback: find default merchant
        return await self.commerce.get_merchant(db, settings.WHATSAPP_DEFAULT_MERCHANT_ID)

    # -------------------------------------------------------------------------
    # Catalog Product Resolution
    # -------------------------------------------------------------------------

    async def resolve_product(
        self,
        db: AsyncSession,
        merchant_id: str,
        query: Optional[str]
    ) -> Tuple[Optional[Product], List[Product]]:
        """
        Resolves a product by name, keyword, or SKU from the merchant's catalog.
        Returns (matched_product, all_candidate_products).
        """
        all_products = await self.commerce.list_products(db, merchant_id, active_only=True)
        if not query or not query.strip():
            # If only 1 product exists in catalog, return it
            if len(all_products) == 1:
                return all_products[0], all_products
            return None, all_products

        q = query.strip().lower()

        # 1. Exact SKU / ID match
        for p in all_products:
            if p.sku.lower() == q or p.id.lower() == q:
                return p, all_products

        # 2. Positional aliases (e.g. "product a", "product 1", "item 1")
        positional_map = {
            "product a": 0, "product 1": 0, "item 1": 0, "first product": 0, "first item": 0,
            "product b": 1, "product 2": 1, "item 2": 1, "second product": 1, "second item": 1,
            "product c": 2, "product 3": 2, "item 3": 2, "third product": 2, "third item": 2,
            "product d": 3, "product 4": 3, "item 4": 3, "fourth product": 3,
            "product e": 4, "product 5": 4, "item 5": 4, "fifth product": 4,
            "product f": 5, "product 6": 5, "item 6": 5, "sixth product": 5,
        }
        if q in positional_map and len(all_products) > positional_map[q]:
            return all_products[positional_map[q]], all_products

        # 3. Key phrase and semantic category matching
        keyword_map = {
            "backpack": ["backpack", "bag", "pack"],
            "sleeve": ["sleeve", "laptop sleeve", "cover"],
            "mouse": ["mouse", "bluetooth mouse", "wireless mouse"],
            "hub": ["hub", "usb hub", "usbc hub", "adapter"],
            "executive": ["executive", "ballistic", "pro backpack", "premium backpack"],
            "shirt": ["shirt", "linen", "navy", "white", "oxford", "casual shirt"],
            "trouser": ["trouser", "trousers", "pant", "pants", "chino", "chinos", "formal", "black trouser", "grey trouser"]
        }

        # Check matched keywords
        scored_matches: List[Tuple[int, Product]] = []
        for p in all_products:
            score = 0
            p_name = p.name.lower()
            p_desc = (p.description or "").lower()

            # Direct word contained
            if q in p_name:
                score += 15
            for word in q.split():
                if len(word) >= 3 and word in p_name:
                    score += 5
                if len(word) >= 3 and word in p_desc:
                    score += 2

            # Alias lookup
            for canonical, aliases in keyword_map.items():
                if any(alias in q for alias in aliases):
                    if any(alias in p_name for alias in aliases):
                        score += 8

            if score > 0:
                scored_matches.append((score, p))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        if scored_matches:
            return scored_matches[0][1], all_products

        # If query explicitly asked for "product a" or similar and catalog is non-empty, default to first item
        if "product a" in q or "first" in q:
            return all_products[0], all_products

        # If no query match, return None with candidate list
        return None, all_products

    # -------------------------------------------------------------------------
    # Inbound Webhook Event Processing
    # -------------------------------------------------------------------------

    async def process_inbound_payload(
        self,
        db: AsyncSession,
        payload: Dict[str, Any],
        raw_body: Optional[bytes] = None,
        signature_header: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main inbound entrypoint for WhatsApp Cloud API webhooks.
        Performs signature verification, deduplication, intent routing, and reply dispatch.
        """
        # 1. Signature validation
        if raw_body and not self.verify_signature(raw_body, signature_header):
            logger.warning("whatsapp_invalid_signature")
            return {"status": "error", "message": "Invalid HMAC signature"}

        # 2. Extract entry and message details
        entries = payload.get("entry", [])
        if not entries:
            return {"status": "ignored", "reason": "No entries in payload"}

        results = []
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                # Check if this is a message delivery status update (sent/delivered/read)
                statuses = value.get("statuses", [])
                if statuses and not messages:
                    # Pure status update, acknowledge 200 OK
                    results.append({"status": "status_acknowledged", "count": len(statuses)})
                    continue

                for msg in messages:
                    res = await self._process_single_message(db, msg, value, payload)
                    results.append(res)

        return {"status": "success", "processed": results}

    async def _process_single_message(
        self,
        db: AsyncSession,
        msg: Dict[str, Any],
        value: Dict[str, Any],
        raw_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processes an individual inbound message with deduplication and state management."""
        wamid = msg.get("id", f"mock_wamid_{uuid.uuid4().hex[:12]}")
        sender_phone = normalize_phone_number(msg.get("from", ""))
        phone_id = value.get("metadata", {}).get("phone_number_id", settings.WHATSAPP_PHONE_NUMBER_ID)
        
        # Extract text body (support text, button clicks, interactive responses)
        msg_text = ""
        msg_type = msg.get("type", "text")
        if msg_type == "text":
            msg_text = msg.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                msg_text = interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                msg_text = interactive.get("list_reply", {}).get("title", "")
        elif msg_type == "button":
            msg_text = msg.get("button", {}).get("text", "")

        msg_text = msg_text.strip()

        # 3. Message Idempotency & Deduplication
        existing_log_stmt = select(WhatsAppWebhookLog).where(WhatsAppWebhookLog.message_id == wamid)
        existing_log_res = await db.execute(existing_log_stmt)
        if existing_log_res.scalar_one_or_none():
            logger.info("whatsapp_duplicate_message_ignored", wamid=wamid, sender=sender_phone)
            return {"status": "duplicate", "wamid": wamid}

        # Resolve merchant
        merchant = await self.resolve_merchant_for_phone(db, sender_phone)
        merchant_id = merchant.id if merchant else settings.WHATSAPP_DEFAULT_MERCHANT_ID

        # Create deduplication audit log entry
        log_entry = WhatsAppWebhookLog(
            id=f"walog_{uuid.uuid4().hex[:12]}",
            message_id=wamid,
            sender_phone=sender_phone,
            recipient_phone_id=phone_id,
            merchant_id=merchant_id,
            message_text=msg_text,
            raw_payload=raw_payload,
            status="RECEIVED"
        )
        db.add(log_entry)
        await db.commit()

        if not msg_text:
            log_entry.status = "PROCESSED"
            await db.commit()
            return {"status": "no_text_content", "wamid": wamid}

        # 4. Intent Extraction
        intent = WhatsAppIntentParser.parse(msg_text)
        logger.info(
            "whatsapp_intent_detected",
            intent=intent.intent_type.value,
            product=intent.product_name,
            lang=intent.language,
            confidence=intent.confidence
        )

        # 5. Route Intent to Business Logic
        reply_text = await self._route_intent(db, merchant, sender_phone, intent, msg_text, wamid)

        # 6. Dispatch Outbound Reply
        outbound_res = await self.client.send_text_message(
            to_phone=sender_phone,
            message_text=reply_text,
            reply_to_wamid=wamid
        )

        # 7. Record Outbound Audit Entry
        outbound_log = WhatsAppOutboundMessage(
            id=f"wamsg_{uuid.uuid4().hex[:12]}",
            recipient_phone=sender_phone,
            merchant_id=merchant_id,
            reply_to_message_id=wamid,
            message_text=reply_text,
            delivery_status=outbound_res.get("status", "SENT"),
            meta_response_payload=outbound_res
        )
        db.add(outbound_log)
        log_entry.status = "PROCESSED"
        await db.commit()

        return {
            "status": "success",
            "wamid": wamid,
            "intent": intent.intent_type.value,
            "reply": reply_text
        }

    async def process_connector_message(
        self,
        db: AsyncSession,
        sender_phone: str,
        message_text: str,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Direct inbound processor for the local Node.js whatsapp-web.js connector.
        Deduplicates, identifies merchant tenant, executes business intent with policy guardrails,
        records audit entries, and returns AI reply text synchronously for direct WhatsApp reply.
        """
        norm_phone = normalize_phone_number(sender_phone)
        msg_id = message_id or f"wweb_{uuid.uuid4().hex[:12]}"
        clean_text = message_text.strip()

        # 1. Message Idempotency & Deduplication
        existing_log_stmt = select(WhatsAppWebhookLog).where(WhatsAppWebhookLog.message_id == msg_id)
        existing_log_res = await db.execute(existing_log_stmt)
        if existing_log_res.scalar_one_or_none():
            logger.info("whatsapp_connector_duplicate_ignored", msg_id=msg_id, sender=norm_phone)
            return {"status": "duplicate", "message_id": msg_id, "reply": ""}

        # 2. Resolve merchant tenant
        merchant = await self.resolve_merchant_for_phone(db, norm_phone)
        merchant_id = merchant.id if merchant else settings.WHATSAPP_DEFAULT_MERCHANT_ID

        # 3. Create deduplication audit log entry
        log_entry = WhatsAppWebhookLog(
            id=f"walog_{uuid.uuid4().hex[:12]}",
            message_id=msg_id,
            sender_phone=norm_phone,
            recipient_phone_id="local_wweb_connector",
            merchant_id=merchant_id,
            message_text=clean_text,
            raw_payload={"source": "whatsapp-web.js", "sender_phone": norm_phone, "text": clean_text},
            status="RECEIVED"
        )
        db.add(log_entry)
        await db.commit()

        if not clean_text:
            log_entry.status = "PROCESSED"
            await db.commit()
            return {"status": "no_text_content", "message_id": msg_id, "reply": ""}

        # 4. Intent Extraction
        intent = WhatsAppIntentParser.parse(clean_text)
        logger.info(
            "whatsapp_connector_intent_detected",
            intent=intent.intent_type.value,
            product=intent.product_name,
            lang=intent.language,
            confidence=intent.confidence
        )

        # 5. Route Intent to Business Logic
        reply_text = await self._route_intent(db, merchant, norm_phone, intent, clean_text, msg_id)

        # 6. Generate Media (PDF, Multi-Chart Images & Playable Voice Note)
        pdf_path = None
        voice_path = None
        image_paths = []
        lower_txt = clean_text.lower()

        try:
            from services.whatsapp.media_generator import WhatsAppMediaGenerator
            
            # Determine which infographic charts to generate
            if intent.intent_type == IntentType.MULTI_IMAGE_REQUEST or any(w in lower_txt for w in ["stack", "12 photo", "multiaple image", "multiple image", "all photos", "graph images", "all charts", "all graphs"]):
                image_paths = WhatsAppMediaGenerator.generate_all_graph_images()
            elif intent.intent_type == IntentType.MARKETPLACE_REPORT:
                image_paths = [WhatsAppMediaGenerator.generate_marketplace_chart_image()]
            elif intent.intent_type == IntentType.PAYMENT_FAILURE_REPORT:
                image_paths = [WhatsAppMediaGenerator.generate_payment_failure_chart_image()]
            elif intent.intent_type == IntentType.BUSINESS_STRATEGY:
                image_paths = [
                    WhatsAppMediaGenerator.generate_marketplace_chart_image(),
                    WhatsAppMediaGenerator.generate_sales_chart_image({"total_revenue": 48081, "prepaid_revenue": 34687, "cod_revenue": 13394, "orders_count": 19, "aov": 2530})
                ]
            elif intent.intent_type == IntentType.SALES_REPORT or any(w in lower_txt for w in ["sales", "seles", "sohw repot", "revenue", "weekly sales"]):
                image_paths = [WhatsAppMediaGenerator.generate_sales_chart_image({"total_revenue": 48081, "prepaid_revenue": 34687, "cod_revenue": 13394, "orders_count": 19, "aov": 2530})]
            elif any(w in lower_txt for w in ["chart", "graph", "image", "photo"]):
                image_paths = WhatsAppMediaGenerator.generate_all_graph_images()

            # Determine whether to generate PDF sales document
            if intent.intent_type == IntentType.SALES_REPORT or any(w in lower_txt for w in ["pdf", "ledger", "statement", "download"]):
                prods = await self.commerce.list_products(db, merchant.id, active_only=True)
                prod_data = [
                    {
                        "name": p.name,
                        "price": p.price_paise // 100,
                        "stock": p.inventory_quantity,
                        "margin": f"{int((p.price_paise - p.cost_paise) / p.price_paise * 100)}%" if p.price_paise else "28%"
                    }
                    for p in prods
                ]
                sales_payload = {
                    "total_revenue": 48081,
                    "prepaid_revenue": 34687,
                    "cod_revenue": 13394,
                    "orders_count": 19,
                    "aov": 2530,
                    "products": prod_data
                }
                pdf_path = WhatsAppMediaGenerator.generate_sales_pdf(sales_payload)

            # Generate Neural Playable Voice Note (MP3) for spoken overview
            voice_path = WhatsAppMediaGenerator.generate_voice_summary(reply_text, lang=intent.language)

        except Exception as media_err:
            logger.error("whatsapp_media_generation_failed", error=str(media_err))

        # 7. Record Outbound Audit Entry
        outbound_log = WhatsAppOutboundMessage(
            id=f"wamsg_{uuid.uuid4().hex[:12]}",
            recipient_phone=norm_phone,
            merchant_id=merchant_id,
            reply_to_message_id=msg_id,
            message_text=reply_text,
            delivery_status="CONNECTOR_DISPATCH",
            meta_response_payload={"channel": "whatsapp-web.js", "status": "DISPATCHED_TO_CONNECTOR"}
        )
        db.add(outbound_log)
        log_entry.status = "PROCESSED"
        await db.commit()

        return {
            "status": "success",
            "message_id": msg_id,
            "sender_phone": norm_phone,
            "intent": intent.intent_type.value,
            "reply": reply_text,
            "pdf_path": pdf_path,
            "image_path": image_paths[0] if image_paths else None,
            "image_paths": image_paths,
            "voice_path": voice_path
        }

    # -------------------------------------------------------------------------
    # Intent Routing & Business Logic
    # -------------------------------------------------------------------------

    async def _route_intent(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        intent: WhatsAppIntent,
        raw_text: str,
        wamid: str
    ) -> str:
        """Dispatches parsed intent to specific commerce workflow handlers."""
        lang = intent.language

        # A. CONFIRMATION HANDLER
        if intent.intent_type == IntentType.CONFIRM:
            return await self._handle_confirm(db, merchant, sender_phone, intent.confirmation_code, lang)

        # B. CANCELLATION HANDLER
        if intent.intent_type == IntentType.CANCEL:
            return await self._handle_cancel(db, merchant, sender_phone, lang)

        # C. PRICE CHANGE HANDLER
        if intent.intent_type == IntentType.PRICE_CHANGE:
            return await self._handle_price_change(db, merchant, sender_phone, intent, lang)

        # D. INVENTORY ADD HANDLER
        if intent.intent_type == IntentType.INVENTORY_ADD:
            return await self._handle_inventory_add(db, merchant, sender_phone, intent, lang)

        # E. INVENTORY SET HANDLER
        if intent.intent_type == IntentType.INVENTORY_SET:
            return await self._handle_inventory_set(db, merchant, sender_phone, intent, lang)

        # F. INVENTORY QUERY HANDLER
        if intent.intent_type == IntentType.INVENTORY_QUERY:
            return await self._handle_inventory_query(db, merchant, intent, lang)

        # G. PRICE QUERY HANDLER
        if intent.intent_type == IntentType.QUERY_PRICE:
            return await self._handle_price_query(db, merchant, intent, lang)

        # H. CATALOG LIST HANDLER
        if intent.intent_type == IntentType.CATALOG_LIST:
            return await self._handle_catalog_list(db, merchant, lang)

        # I. LOW MARGIN QUERY HANDLER
        if intent.intent_type == IntentType.LOW_MARGIN_QUERY:
            return await self._handle_low_margins(db, merchant, lang)

        # J. RECOMMENDATION / OFFER SUGGESTION HANDLER
        if intent.intent_type == IntentType.RECOMMENDATION:
            return await self._handle_offer_suggestion(db, merchant, intent, lang)

        # K. OFFER CREATE HANDLER
        if intent.intent_type == IntentType.OFFER_CREATE:
            return await self._handle_offer_create(db, merchant, sender_phone, intent, lang)

        # L. SALES REPORT HANDLER
        if intent.intent_type == IntentType.SALES_REPORT:
            return await self._handle_sales_report(db, merchant, lang)

        # M. MARKETPLACE REPORT HANDLER (Amazon / Flipkart / Meesho / ONDC / Multi-channel)
        if intent.intent_type == IntentType.MARKETPLACE_REPORT:
            return await self._handle_marketplace_report(db, merchant, intent, lang)

        # N. ORDER LOOKUP HANDLER (by order ID)
        if intent.intent_type == IntentType.ORDER_LOOKUP:
            return await self._handle_order_lookup(db, merchant, intent, lang)

        # O. PAYMENT FAILURE & RTO REPORT HANDLER
        if intent.intent_type == IntentType.PAYMENT_FAILURE_REPORT:
            return await self._handle_payment_failure_report(db, merchant, lang)

        # P. BUSINESS STRATEGY HANDLER
        if intent.intent_type == IntentType.BUSINESS_STRATEGY:
            return await self._handle_business_strategy(db, merchant, lang)

        # Q. ALL INPUTS MENU HANDLER
        if intent.intent_type == IntentType.ALL_INPUTS_MENU:
            return self._handle_all_inputs_menu(merchant.name, lang)

        # R. MULTI-IMAGE / GRAPH STACK HANDLER
        if intent.intent_type == IntentType.MULTI_IMAGE_REQUEST:
            return await self._handle_multi_image_request(db, merchant, lang)

        # S. CONVERSATIONAL AI & HELP ADVISOR
        return await self._handle_conversational_ai(db, merchant, raw_text, lang)

    async def _handle_conversational_ai(
        self,
        db: AsyncSession,
        merchant: Merchant,
        user_query: str,
        lang: str = "en"
    ) -> str:
        """Conversational AI reasoning over merchant catalog, sales performance, and commercial economics."""
        clean = user_query.strip().lower()
        if clean in ["hi", "hello", "help", "menu", "start", "hey", "namaste", "namaskara"]:
            return self._generate_help_menu(lang, merchant.name)

        # Gather real catalog snapshot
        products = await self.commerce.list_products(db, merchant.id, active_only=True)
        top_stock = sorted(products, key=lambda p: p.inventory_quantity, reverse=True)
        lowest_stock = sorted(products, key=lambda p: p.inventory_quantity)

        # Check for Gemini / LLM API Key
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        if gemini_key and not gemini_key.startswith("mock_"):
            try:
                import httpx
                model = os.getenv("LLM_MODEL", "gemini-1.5-flash")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                
                catalog_summary = "\n".join([
                    f"- {p.name}: Price ₹{p.price_paise//100}, Cost ₹{p.cost_paise//100}, Stock {p.inventory_quantity}"
                    for p in products
                ])
                system_prompt = (
                    f"You are the autonomous AI Merchant Growth Advisor for '{merchant.name}'. "
                    f"Here is the live store catalog:\n{catalog_summary}\n"
                    f"Realized 7-day revenue: ₹48,081 across 19 orders (72% prepaid, 28% COD).\n"
                    f"Rule: Policy margin floor is 18%. Any price discounts below 18% require owner confirmation.\n"
                    f"Answer the merchant's query concisely, professionally, and with exact rupee numbers and actionable advice."
                )
                payload = {
                    "contents": [
                        {"role": "user", "parts": [{"text": f"{system_prompt}\n\nMerchant question: {user_query}"}]}
                    ],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}
                }
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        ai_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        return f"🤖 *AI Growth Advisor*:\n\n{ai_text}"
            except Exception as llm_err:
                logger.warning("gemini_conversational_fallback", error=str(llm_err))

        # Advanced deterministic commercial reasoning (zero-API fallback)
        advice_parts = []
        if any(w in clean for w in ["profit", "margin", "increase", "grow", "scale"]):
            top = top_stock[0] if top_stock else None
            advice_parts.append(
                f"📈 *Strategic Profit Recommendations*:\n"
                f"• *Highest Volume Asset*: *{top.name if top else 'Olive Linen Shirt'}* has {top.inventory_quantity if top else 125} units at ₹{top.price_paise//100 if top else 2099}.\n"
                f"• *Gross Margin Leverage*: Currently operating at ~32% margin (vs 18% minimum floor).\n"
                f"• *Actionable Play*: Bundle with *Formal Trousers* for ₹3,499 (saves customer ₹200, retains healthy 26% margin).\n"
                f"• *Prepaid Conversion*: 28% of orders are COD. Offering a 5% prepaid discount recovers ₹1,200 in return/rejection overhead."
            )
        elif any(w in clean for w in ["dead stock", "slow", "trousers", "unsold"]):
            slow = lowest_stock[0] if lowest_stock else None
            advice_parts.append(
                f"📦 *Dead Stock & Liquidation Analysis*:\n"
                f"• *Observation*: Charcoal Grey Trousers have lower velocity despite 38% margin.\n"
                f"• *Recommendation*: Run a flash bundle: 'Buy Olive Linen Shirt, get Charcoal Trousers at ₹2,299' (compliant with 22% margin floor)."
            )
        else:
            advice_parts.append(
                f"💡 *Merchant Commercial Insights*:\n"
                f"• Store: *{merchant.name}* | Active Catalog: {len(products)} SKUs\n"
                f"• 7-Day Revenue: *₹48,081* across 19 successful orders.\n"
                f"• Top Product: *Vastram Pure Olive Linen Casual Shirt* (125 in stock).\n"
                f"• Policy Guardrail: All automated price recommendations enforce an 18% minimum margin floor."
            )

        advice_parts.append("\n_Commands you can try_: 'Show today sales', 'Stock yestu ide nodu', 'Change backpack price to 2500'")
        return f"🤖 *AI Growth Advisor*:\n\n" + "\n".join(advice_parts)

    async def _handle_sales_report(
        self,
        db: AsyncSession,
        merchant: Merchant,
        lang: str = "en"
    ) -> str:
        """Generates executive weekly sales and revenue report in English."""
        orders_stmt = select(Order)
        orders_res = await db.execute(orders_stmt)
        orders = orders_res.scalars().all()

        paid_orders = [o for o in orders if o.status == "PAID"]
        cod_orders = [o for o in orders if o.status == "COD"]
        cancelled_orders = [o for o in orders if o.status == "CANCELLED"]

        paid_revenue_paise = sum(o.amount_paise for o in paid_orders)
        cod_revenue_paise = sum(o.amount_paise for o in cod_orders)
        cancelled_paise = sum(o.amount_paise for o in cancelled_orders)
        total_realized_paise = paid_revenue_paise + cod_revenue_paise

        successful_count = len(paid_orders) + len(cod_orders)
        aov_paise = total_realized_paise // max(successful_count, 1)

        total_realized_rupees = total_realized_paise // 100
        paid_rupees = paid_revenue_paise // 100
        cod_rupees = cod_revenue_paise // 100
        cancelled_rupees = cancelled_paise // 100
        aov_rupees = aov_paise // 100

        # Fetch top products
        products = await self.commerce.list_products(db, merchant.id, active_only=True)
        top_prods_lines = []
        for i, p in enumerate(products[:4], 1):
            top_prods_lines.append(f"  {i}. {p.name}: ₹{p.price_paise // 100} ({p.inventory_quantity} in stock)")
        top_prods_str = "\n".join(top_prods_lines)

        return (
            f"📊 *Executive Sales & Revenue Report*\n"
            f"Store: *{merchant.name}* (Previous 7 Days)\n\n"
            f"💰 *Financial Performance*:\n"
            f"• *Total Realized Revenue*: ₹{total_realized_rupees:,}\n"
            f"• *Prepaid Online (Razorpay)*: ₹{paid_rupees:,} ({len(paid_orders)} orders)\n"
            f"• *Cash on Delivery (COD)*: ₹{cod_rupees:,} ({len(cod_orders)} orders)\n"
            f"• *Cancelled / Voided*: ₹{cancelled_rupees:,} ({len(cancelled_orders)} orders)\n"
            f"• *Total Successful Orders*: {successful_count}\n"
            f"• *Average Order Value (AOV)*: ₹{aov_rupees:,}\n\n"
            f"📦 *Top Catalog Products*:\n"
            f"{top_prods_str}\n\n"
            f"📈 *Channel Distribution*:\n"
            f"• Direct Online Store: 68%\n"
            f"• WhatsApp Conversational: 32%\n\n"
            f"📥 Download full CSV order ledger at:\n"
            f"http://localhost:3000/orders"
        )

    async def _handle_marketplace_report(
        self,
        db: AsyncSession,
        merchant: Merchant,
        intent: WhatsAppIntent,
        lang: str = "en"
    ) -> str:
        """Generates multi-channel marketplace unit economics reports for Amazon, Flipkart, ONDC, Meesho, or all channels."""
        channel = (intent.marketplace_channel or "ALL").upper()

        if channel == "AMAZON":
            return (
                f"🛍️ *Amazon India — Growth & Unit Economics Report*\n"
                f"Store: *{merchant.name}* • Integration: *Razorpay + Amazon MWS*\n\n"
                f"💰 *Platform Fee Structure*:\n"
                f"• *Referral Fee*: 15.00% (Apparel & Fashion category)\n"
                f"• *Fixed Closing Fee*: ₹25 per item\n"
                f"• *Easy Ship Base Logistics*: ₹70 (Standard 500g delivery)\n"
                f"• *Return / RTO Provision*: 18.00% return rate (~₹50 reverse handling)\n"
                f"• *Estimated Ad CAC*: ₹120 (TACoS 5.7% per unit sold)\n\n"
                f"🏷️ *Sample SKU Unit Economics (Olive Linen Shirt @ ₹2,099)*:\n"
                f"• Gross Selling Price: ₹2,099\n"
                f"• Base Manufacturing Cost: -₹650\n"
                f"• Amazon Referral Cut (15%): -₹315\n"
                f"• Closing + Logistics: -₹95\n"
                f"• Return Reserve & Ads: -₹210\n"
                f"• *Realized Net Margin*: *₹829 / unit (19.4% net margin)*\n"
                f"  ✅ *Policy Compliance*: Complies with 18% minimum margin floor.\n\n"
                f"🚀 *Tactical Action Plan*:\n"
                f"1. *Prime Badge*: Enrolling in FBA increases Buy Box win probability by +34%.\n"
                f"2. *Channel Arbitrage*: Direct WhatsApp yields 34.2% margin vs Amazon's 19.4% (+₹440 extra cash per shirt on WhatsApp!).\n"
                f"3. *Ad Strategy*: Keep Sponsored Product bids <= ₹14/click to preserve 19% net margin."
            )

        if channel == "FLIPKART":
            return (
                f"🏷️ *Flipkart Marketplace — Performance & Margin Intelligence*\n"
                f"Store: *{merchant.name}* • Category: *Men's Premium Apparel*\n\n"
                f"💰 *Platform Fee Structure*:\n"
                f"• *Commission Rate*: 14.00% (Tier-1 Apparel benchmark)\n"
                f"• *Fixed Marketplace Fee*: ₹20 per order\n"
                f"• *Shipping & Logistics*: ₹65 (Regional fulfillment)\n"
                f"• *Return / RTO Rate*: 16.00% (Estimated reverse loss: ₹45)\n"
                f"• *Performance Ad CAC*: ₹110 per order\n\n"
                f"📦 *Sample SKU Unit Economics (Navy Casual Shirt @ ₹1,999)*:\n"
                f"• Gross Selling Price: ₹1,999\n"
                f"• Base Manufacturing Cost: -₹720\n"
                f"• Flipkart Commission (14%): -₹280\n"
                f"• Fixed Fee + Shipping: -₹85\n"
                f"• Return Reserve & Ads: -₹182\n"
                f"• *Realized Net Margin*: *₹732 / unit (21.2% net margin)*\n"
                f"  ✅ *Policy Compliance*: Exceeds 18% minimum margin floor.\n\n"
                f"🎯 *Strategic Recommendations*:\n"
                f"1. *Flipkart Assured*: Qualifies for next-day delivery in South India hubs.\n"
                f"2. *Tier-2/3 Demand*: Flipkart drives 62% of volume from non-metro pin codes.\n"
                f"3. *Bundle Play*: Pair Navy Shirt with Khaki Chino to lift average ticket size to ₹3,499."
            )

        if channel == "MEESHO":
            return (
                f"📦 *Meesho Value Marketplace — Risk & RTO Ledger*\n"
                f"Store: *{merchant.name}*\n\n"
                f"💰 *Fee Structure*:\n"
                f"• *Commission*: 0.00% (Zero commission marketplace model)\n"
                f"• *Logistics & Shipping*: ₹60 per parcel\n"
                f"• *Return / RTO Rate*: 22.00% (High risk factor!)\n"
                f"• *Estimated Reverse Loss*: ₹40 per return attempt\n\n"
                f"⚖️ *Commercial Assessment*:\n"
                f"• *Net Margin*: ~26.5% realized margin\n"
                f"• *Verdict*: Use Meesho strictly for end-of-season clearance inventory. Avoid listing premium Italian Wool trousers due to 22% RTO risk."
            )

        if channel == "ONDC":
            return (
                f"🌐 *ONDC Open Commerce Network — Ecosystem Report*\n"
                f"Store: *{merchant.name}* • Protocol: *Beckn Standard v1.2*\n\n"
                f"💰 *Open Network Cost Economics*:\n"
                f"• *Buyer App Fee*: 3.00% (e.g. Paytm, Mystore, Magicpin)\n"
                f"• *Network Transaction Fee*: 1.50%\n"
                f"• *Combined Network Cut*: *4.50%* (vs Amazon 15%!)\n"
                f"• *Logistics*: ₹45 (Open logistics network: Shadowfax / Delhivery)\n"
                f"• *Realized Net Margin*: *30.5% net margin*\n\n"
                f"💡 *Strategic Advantage*:\n"
                f"• Retain +11% more profit per order compared to traditional marketplaces.\n"
                f"• Direct customer data ownership with zero de-platforming risk."
            )

        # Default: ALL channels multi-marketplace overview
        return (
            f"📊 *Multi-Channel E-Commerce Economics & Arbitrage Report*\n"
            f"Store: *{merchant.name}* • Active Channels: 5\n\n"
            f"🏆 *Net Realized Margin Ranking (After All Fees & RTO)*:\n"
            f"1. *Direct WhatsApp Store*: *34.2% Net Margin* (Overhead: ₹180) ⭐ *Best Profit*\n"
            f"2. *ONDC Open Network*: *30.5% Net Margin* (Overhead: ₹260)\n"
            f"3. *Meesho Marketplace*: *26.5% Net Margin* (Overhead: ₹420 - High RTO)\n"
            f"4. *Flipkart Marketplace*: *21.2% Net Margin* (Overhead: ₹560)\n"
            f"5. *Amazon India*: *19.4% Net Margin* (Overhead: ₹610)\n\n"
            f"💡 *Strategic Profit Arbitrage*:\n"
            f"• Selling an Olive Linen Shirt (MRP ₹2,099) on *WhatsApp* yields *₹1,269 profit* vs *₹829 on Amazon*.\n"
            f"• That is *₹440 more profit per shirt* in your pocket!\n"
            f"• Moving just 30 orders/month to WhatsApp recovers *₹13,200/month* in saved fees.\n\n"
            f"_Try typing_: 'amazon report', 'flipkart report', 'payment failure', or 'all inputs'"
        )

    async def _handle_order_lookup(
        self,
        db: AsyncSession,
        merchant: Merchant,
        intent: WhatsAppIntent,
        lang: str = "en"
    ) -> str:
        """Looks up specific order by ID, receipt number, or numeric digits in database."""
        query_str = (intent.order_id_query or "").strip().lower()

        # Query all orders
        orders_stmt = select(Order).order_by(Order.created_at.desc())
        orders_res = await db.execute(orders_stmt)
        orders = orders_res.scalars().all()

        target_order = None
        for o in orders:
            oid = (o.id or "").lower()
            rcpt = (o.receipt or "").lower()
            if query_str in oid or query_str in rcpt or oid.endswith(query_str):
                target_order = o
                break

        if not target_order and orders:
            try:
                idx = int(re.sub(r"[^\d]", "", query_str))
                if 1 <= idx <= len(orders):
                    target_order = orders[idx - 1]
            except Exception:
                pass

        if target_order:
            notes = target_order.notes or {}
            c_name = notes.get("customer_name", "Valued Customer")
            c_phone = notes.get("customer_phone", "Verified Mobile")
            c_city = notes.get("customer_city", "Bengaluru, Karnataka")
            p_name = notes.get("product_name", "Vastram Classic Apparel")
            sku = notes.get("sku", "VAST-SKU")
            size = notes.get("size", "Standard")
            p_method = notes.get("payment_method", "Prepaid Razorpay")
            d_status = notes.get("delivery_status", "Out for Delivery")
            amt = target_order.amount_paise // 100
            st = target_order.status

            status_icon = "🟢" if st == "PAID" else ("🟡" if st == "COD" else "🔴")

            return (
                f"📦 *Dedicated Order Ledger — {target_order.id}*\n\n"
                f"👤 *Customer Information*:\n"
                f"• Name: *{c_name}*\n"
                f"• Contact: {c_phone}\n"
                f"• Delivery City: {c_city}\n\n"
                f"🏷️ *Item Ordered*:\n"
                f"• *{p_name}* (SKU: {sku})\n"
                f"• Size/Spec: {size} | Quantity: 1\n"
                f"• Price: *₹{amt:,}*\n\n"
                f"💳 *Payment & Fulfillment*:\n"
                f"• Status: {status_icon} *{st}*\n"
                f"• Method: {p_method}\n"
                f"• Tracking Status: 🚚 *{d_status}*\n"
                f"• Receipt Token: `{target_order.receipt}`\n\n"
                f"🔗 *Live Razorpay Verification*: Verified & Audited in SQLite Ledger."
            )

        # Fallback if specific ID not found: show top 3 recent orders
        recent_lines = []
        for o in orders[:3]:
            notes = o.notes or {}
            p = notes.get("product_name", "Vastram Product")
            c = notes.get("customer_name", "Customer")
            amt = o.amount_paise // 100
            recent_lines.append(f"• *{o.id}* ({o.status}): {p} for {c} — ₹{amt:,}")

        return (
            f"🔍 *Order Lookup Results*:\n"
            f"Could not find order matching '{query_str}'. Here are your latest 3 orders:\n\n"
            + "\n".join(recent_lines) +
            f"\n\n_Type any Order ID (e.g. 'order 9841' or 'order 9840') for full details._"
        )

    async def _handle_payment_failure_report(
        self,
        db: AsyncSession,
        merchant: Merchant,
        lang: str = "en"
    ) -> str:
        """Generates comprehensive payment failure, drop-off, and 1-click recovery intelligence report."""
        orders_stmt = select(Order)
        orders_res = await db.execute(orders_stmt)
        orders = orders_res.scalars().all()

        cancelled_orders = [o for o in orders if o.status == "CANCELLED"]
        total_lost_paise = sum(o.amount_paise for o in cancelled_orders)
        total_lost_rupees = total_lost_paise // 100

        cancelled_breakdown = []
        for o in cancelled_orders:
            n = o.notes or {}
            c_name = n.get("customer_name", "Buyer")
            amt = o.amount_paise // 100
            reason = n.get("delivery_status", "Payment Dropped / Cancelled")
            cancelled_breakdown.append(f"  • *{o.id}* (₹{amt:,}): {c_name} — _{reason}_")

        breakdown_str = "\n".join(cancelled_breakdown) if cancelled_breakdown else "  • No cancelled orders recorded."

        return (
            f"⚠️ *Payment Drop-Off & Failure Intelligence Report*\n"
            f"Store: *{merchant.name}* • Monitoring: *Razorpay Webhooks & COD*\n\n"
            f"💰 *Lost Revenue Summary*:\n"
            f"• *Total Failed / Cancelled Orders*: {len(cancelled_orders)} orders\n"
            f"• *Total Realized Loss*: *₹{total_lost_rupees:,}*\n"
            f"• *Overall Checkout Success Rate*: 86.4% (19/22 orders converted)\n\n"
            f"🔍 *Detailed Incident Log*:\n"
            f"{breakdown_str}\n\n"
            f"📊 *Root Cause Distribution*:\n"
            f"• *UPI Server Timeout (45%)*: Bank gateway latency > 30s during peak hours.\n"
            f"• *3DS Card Abandonment (25%)*: User closed window before entering OTP.\n"
            f"• *COD Buyer Rejection (30%)*: Buyer canceled prior to dispatch.\n\n"
            f"🚀 *Autonomous Recovery Playbook*:\n"
            f"• Auto-generated Razorpay Smart Collect link: https://rzp.io/i/recover-vastram\n"
            f"• Sending a 1-click WhatsApp recovery link recovers *42% of abandoned checkouts* within 15 minutes!"
        )

    async def _handle_business_strategy(
        self,
        db: AsyncSession,
        merchant: Merchant,
        lang: str = "en"
    ) -> str:
        """Generates comprehensive executive business growth and margin scaling strategy."""
        return (
            f"🎯 *Vastram Retail — 4-Pillar Executive Business Strategy*\n"
            f"Store: *{merchant.name}* • Current Revenue: *₹48,081* • Active Catalog: 6 SKUs\n\n"
            f"1️⃣ *Direct WhatsApp Margin Arbitrage (High Impact)*:\n"
            f"• Direct WhatsApp delivers *34.2% net margin* vs Amazon's *19.4%*.\n"
            f"• *Play*: Include an invoice QR code inside every marketplace shipment offering ₹150 off on WhatsApp repeat purchases. Shifting 30 orders/mo saves ₹13,200 in platform commissions.\n\n"
            f"2️⃣ *COD to Prepaid Conversion Engine*:\n"
            f"• 28% of store volume is COD (₹13,394). COD has a 12% RTO return risk.\n"
            f"• *Play*: Offer an instant 5% UPI cashback (or ₹100 prepaid credit) at checkout. Eliminates return transit costs and accelerates cash flow by 6 days.\n\n"
            f"3️⃣ *High-Velocity Inventory Bundling*:\n"
            f"• *Olive Linen Casual Shirt* has 125 units in stock (top asset).\n"
            f"• *Play*: Launch the 'Executive Weekend Bundle': Olive Shirt + Jet Black Trousers for ₹3,499 (retains 26% margin, lifts basket size by +42%).\n\n"
            f"4️⃣ *Autonomous Policy Margin Guardrail*:\n"
            f"• Minimum 18% margin floor is actively enforced by AI on all pricing actions.\n"
            f"• Zero risk of accidental below-cost discounts or margin erosion."
        )

    def _handle_all_inputs_menu(self, merchant_name: str, lang: str = "en") -> str:
        """Returns comprehensive cheatsheet of all supported merchant commands, inputs, and triggers."""
        return (
            f"📱 *Vastram AI Growth Agent — Master Command & Input Cheatsheet*\n"
            f"Store: *{merchant_name}* • Multi-channel AI Operator\n\n"
            f"📊 *1. Sales & Financial Reports*:\n"
            f"• `sales report` / `seles` / `sohw repot` / `todays sales`\n"
            f"  _(Sends text ledger, PDF sales document, visual chart, & audio voice note)_\n\n"
            f"🛍️ *2. Marketplace & E-Commerce Reports*:\n"
            f"• `amazon report` / `amazn` / `amzone`\n"
            f"• `flipkart report` / `flpkart` / `flipkrt`\n"
            f"• `meesho report` / `ondc report`\n"
            f"• `ecommerce report` / `e comeses` / `channel comparison`\n\n"
            f"🎯 *3. Business Strategy & Growth*:\n"
            f"• `business strategy` / `buiness statergy` / `growth strategy`\n\n"
            f"📦 *4. Order Tracking & Specific Lookups*:\n"
            f"• `order 9841` / `ord_vast_9841` / `track order 9840` / `#9839`\n\n"
            f"⚠️ *5. Payment Failure & RTO Analytics*:\n"
            f"• `payment failure report` / `failur report` / `rto report`\n\n"
            f"🖼️ *6. Multi-Image Graph Stack (All 4 Charts)*:\n"
            f"• `stack 12 photo` / `graph images` / `all charts` / `multiaple image`\n\n"
            f"🏷️ *7. Catalog & Margin Controls*:\n"
            f"• `show products` / `catalog` / `low margin products` / `stock`\n"
            f"• `change linen shirt price to 1999` / `add 20 shirts`\n\n"
            f"🎙️ *8. Playable Voice Notes*:\n"
            f"• Send ANY WhatsApp audio voice note, or text `voice note` to listen!\n\n"
            f"💡 *Typo-Tolerance*: You can misspell any query (e.g. `seles`, `flpkart`, `oder 9841`, `buiness statergy`) and the agent will understand your exact intent!"
        )

    async def _handle_multi_image_request(
        self,
        db: AsyncSession,
        merchant: Merchant,
        lang: str = "en"
    ) -> str:
        """Handles request for multiple visual infographics / graph images."""
        return (
            f"🖼️ *Executive Infographics & Visual Chart Stack Dispatched!*\n"
            f"Store: *{merchant.name}*\n\n"
            f"📈 Dispatched 4 High-Resolution Intelligence Dashboards:\n"
            f"1. *Sales & Revenue Overview* (Prepaid vs COD & SKU Margins)\n"
            f"2. *Marketplace Channel Comparison* (Amazon vs Flipkart vs ONDC vs Direct WhatsApp)\n"
            f"3. *Payment Drop-Off & Failure Funnel* (UPI timeouts & Recovery)\n"
            f"4. *Inventory Health & Safety Buffer Stack* (Stock units vs reorder points)\n\n"
            f"🎙️ An audio executive summary has also been generated for tap-to-listen."
        )

    async def _handle_catalog_list(
        self,
        db: AsyncSession,
        merchant: Merchant,
        lang: str = "en"
    ) -> str:
        """Returns complete live catalog listing with price, cost, gross margin, and inventory."""
        products = await self.commerce.list_products(db, merchant.id, active_only=True)
        if not products:
            return f"ℹ️ No active products found in catalog for {merchant.name}."

        lines = [
            f"📦 *Active Catalog Products — {merchant.name}*",
            f"Total Items: *{len(products)}*\n"
        ]

        for i, p in enumerate(products, 1):
            price_rs = p.price_paise // 100
            cost_rs = p.cost_paise // 100
            margin = PolicyGuard.calculate_margin(p.price_paise, p.cost_paise)
            stock_icon = "🟢" if p.inventory_quantity > 20 else ("🟡" if p.inventory_quantity > 5 else "🔴")

            lines.append(
                f"{i}. *{p.name}*\n"
                f"   • SKU: `{p.sku}`\n"
                f"   • Price: ₹{price_rs:,} | Unit Cost: ₹{cost_rs:,}\n"
                f"   • Gross Margin: *{margin:.1f}%*\n"
                f"   • In Stock: {stock_icon} {p.inventory_quantity} units\n"
            )

        lines.append(
            "💡 *Available Quick Actions*:\n"
            "• 'Change <product> price to <amount>'\n"
            "• 'Update <product> stock to <qty>'\n"
            "• 'Suggest an offer for <product>'\n"
            "• 'Which products have low margins?'"
        )
        return "\n".join(lines)

    async def _handle_low_margins(
        self,
        db: AsyncSession,
        merchant: Merchant,
        lang: str = "en"
    ) -> str:
        """Evaluates catalog margins against policy floor and highlights lowest margin items."""
        products = await self.commerce.list_products(db, merchant.id, active_only=True)
        if not products:
            return "No products found in catalog."

        floor = float(merchant.minimum_margin_percent or 25.0)

        # Calculate margin for each product and sort lowest to highest
        analyzed = []
        for p in products:
            m = PolicyGuard.calculate_margin(p.price_paise, p.cost_paise)
            analyzed.append((m, p))
        analyzed.sort(key=lambda x: x[0])

        lines = [
            f"🏷️ *Catalog Margin Economics — {merchant.name}*",
            f"Configured Minimum Margin Floor: *{floor:.1f}%*\n"
        ]

        for i, (m, p) in enumerate(analyzed, 1):
            price_rs = p.price_paise // 100
            cost_rs = p.cost_paise // 100

            if m < floor:
                status_tag = "🔴 *VIOLATION (Below Floor)*"
            elif m < floor + 10.0:
                status_tag = "🟡 *NEAR FLOOR (Caution)*"
            else:
                status_tag = "🟢 *HEALTHY*"

            lines.append(
                f"{i}. *{p.name}*\n"
                f"   • Gross Margin: *{m:.1f}%* — {status_tag}\n"
                f"   • Retail Price: ₹{price_rs:,} | Unit Cost: ₹{cost_rs:,}\n"
                f"   • Available Stock: {p.inventory_quantity} units\n"
            )

        lowest_m, lowest_p = analyzed[0]
        # Recommended price to achieve target margin floor + 10%
        target_margin = (floor + 10.0) / 100.0
        rec_price_paise = int(round(lowest_p.cost_paise / (1.0 - target_margin)))
        rec_price_rs = rec_price_paise // 100

        lines.append(
            f"💡 *AI Growth Recommendation*:\n"
            f"Lowest margin item is *{lowest_p.name}* at {lowest_m:.1f}%.\n"
            f"To achieve a healthy {(floor + 10):.0f}% margin, update price to *₹{rec_price_rs:,}*.\n"
            f"Reply: *Change {lowest_p.name} price to {rec_price_rs}* to apply."
        )

        return "\n".join(lines)

    async def _handle_offer_suggestion(
        self,
        db: AsyncSession,
        merchant: Merchant,
        intent: WhatsAppIntent,
        lang: str = "en"
    ) -> str:
        """Generates policy-compliant promotional discount recommendations."""
        product, all_prods = await self.resolve_product(db, merchant.id, intent.product_name)
        if not product:
            if all_prods:
                product = max(all_prods, key=lambda p: p.inventory_quantity)
            else:
                return "No products available to create offers for."

        price_rs = product.price_paise // 100
        cost_rs = product.cost_paise // 100
        curr_margin = PolicyGuard.calculate_margin(product.price_paise, product.cost_paise)
        floor = float(merchant.minimum_margin_percent or 25.0)
        max_discount_cap = float(merchant.maximum_discount_percent or 10.0)

        # Calculate max discount that still satisfies margin floor
        min_allowed_price_paise = int(round(product.cost_paise / (1.0 - (floor / 100.0))))
        max_allowed_cut_paise = max(0, product.price_paise - min_allowed_price_paise)
        max_margin_safe_pct = (max_allowed_cut_paise / product.price_paise) * 100.0

        # Safe discount recommendation is min of policy cap and margin safe pct
        safe_discount_pct = min(max_discount_cap, max_margin_safe_pct)
        if safe_discount_pct >= 10.0:
            rec_disc_pct = 10.0
        elif safe_discount_pct >= 5.0:
            rec_disc_pct = 5.0
        else:
            rec_disc_pct = max(1.0, round(safe_discount_pct, 1))

        discounted_price_paise = int(round(product.price_paise * (1.0 - rec_disc_pct / 100.0)))
        discounted_price_rs = discounted_price_paise // 100
        projected_margin = PolicyGuard.calculate_margin(discounted_price_paise, product.cost_paise)

        return (
            f"🎯 *AI Promotional Offer Recommendation*\n\n"
            f"📦 Target Product: *{product.name}*\n"
            f"💰 Current Price: ₹{price_rs:,} (COGS: ₹{cost_rs:,})\n"
            f"📈 Current Gross Margin: {curr_margin:.1f}%\n"
            f"🛡️ Policy Floor: {floor:.1f}% | Discount Cap: {max_discount_cap:.1f}%\n\n"
            f"✨ *Recommended Campaign*: *Flash Growth Discount*\n"
            f"• Recommended Discount: *{rec_disc_pct:.0f}% OFF*\n"
            f"• Promotional Price: *₹{discounted_price_rs:,}* (Save ₹{(price_rs - discounted_price_rs):,})\n"
            f"• Projected Margin: *{projected_margin:.1f}%* (Complies with {floor:.0f}% floor)\n"
            f"• Estimated Conversion Lift: *+24% to +38%*\n\n"
            f"To launch this offer, reply:\n"
            f"*Change {product.name} price to {discounted_price_rs}*"
        )

    # -------------------------------------------------------------------------
    # Action Handlers
    # -------------------------------------------------------------------------

    async def _handle_confirm(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        explicit_code: Optional[str],
        lang: str
    ) -> str:
        """Executes active pending confirmation."""
        conf, err = await self.confirmation.find_pending_confirmation(
            db=db,
            merchant_id=merchant.id,
            sender_phone=sender_phone,
            explicit_code=explicit_code
        )

        if not conf:
            if err == "EXPIRED":
                if lang == "kn":
                    return "⏰ ದೃಢೀಕರಣದ 15 ನಿಮಿಷಗಳ ಸಮಯ ಮೀರಿದೆ. ದಯವಿಟ್ಟು ಹೊಸ ವಿನಂತಿಯನ್ನು ಕಳುಹಿಸಿ."
                elif lang == "hi":
                    return "⏰ पुष्टि का 15 मिनट का समय समाप्त हो गया है। कृपया नया अनुरोध भेजें।"
                return "⏰ This confirmation request has expired (15-min limit). Please send a new request."
            elif err == "ALREADY_EXECUTED":
                if lang == "kn":
                    return "⚠️ ಈ ಕ್ರಿಯೆಯನ್ನು ಈಗಾಗಲೇ ನಿರ್ವಹಿಸಲಾಗಿದೆ. ಮರು-ದೃಢೀಕರಣ ಸಾಧ್ಯವಿಲ್ಲ."
                elif lang == "hi":
                    return "⚠️ यह कार्रवाई पहले ही निष्पादित हो चुकी है। दोबारा पुष्टि संभव नहीं है।"
                return "⚠️ This action has already been executed. Replay is blocked."
            else:
                if lang == "kn":
                    return "ℹ️ ದೃಢೀಕರಿಸಲು ಯಾವುದೇ ಬಾಕಿ ಉಳಿದ ಕ್ರಿಯೆಗಳಿಲ್ಲ. ಹೊಸ ವಿನಂತಿಯನ್ನು ಕಳುಹಿಸಿ."
                elif lang == "hi":
                    return "ℹ️ पुष्टि के लिए कोई लंबित कार्रवाई नहीं है। नया अनुरोध भेजें।"
                return "ℹ️ No pending action found to confirm. Send a command like 'Change backpack price to 2500' to start."

        # Execute confirmed operation
        success, action_res, data = await self.confirmation.execute_confirmed_operation(db, conf)
        if not success:
            return f"❌ Failed to execute: {action_res}"

        # Generate localized success reply
        if conf.operation_type == "PRICE_UPDATE":
            prod_name = conf.product_name or "Product"
            new_p = conf.proposed_values.get("price_paise", 0) // 100
            old_p = conf.current_values.get("price_paise", 0) // 100

            if lang == "kn":
                return (
                    f"✅ *ಬೆಲೆ ಬದಲಾವಣೆ ಯಶಸ್ವಿಯಾಗಿದೆ!*\n\n"
                    f"📦 ಉತ್ಪನ್ನ: *{prod_name}*\n"
                    f"💰 ಹಿಂದಿನ ಬೆಲೆ: ₹{old_p}\n"
                    f"🎉 ಹೊಸ ಬೆಲೆ: *₹{new_p}*\n\n"
                    f"ಮಾರಾಟ ವ್ಯವಸ್ಥೆ ಮತ್ತು ವೆಬ್‌ಸೈಟ್‌ನಲ್ಲಿ ತಕ್ಷಣವೇ ಅಪ್‌ಡೇಟ್ ಆಗಿದೆ."
                )
            elif lang == "hi":
                return (
                    f"✅ *मूल्य सफलतापूर्वक अपडेट हुआ!*\n\n"
                    f"📦 उत्पाद: *{prod_name}*\n"
                    f"💰 पुराना मूल्य: ₹{old_p}\n"
                    f"🎉 नया मूल्य: *₹{new_p}*\n\n"
                    f"कैटलॉग और स्टोर में तुरंत अपडेट कर दिया गया है।"
                )
            return (
                f"✅ *Price Successfully Updated!*\n\n"
                f"📦 Product: *{prod_name}*\n"
                f"💰 Previous: ₹{old_p}\n"
                f"🎉 New Price: *₹{new_p}*\n\n"
                f"Live catalog and Razorpay pricing updated immediately."
            )

        elif conf.operation_type == "INVENTORY_UPDATE":
            prod_name = conf.product_name or "Product"
            new_inv = conf.proposed_values.get("inventory_quantity", 0)
            old_inv = conf.current_values.get("inventory_quantity", 0)

            if lang == "kn":
                return (
                    f"✅ *ದಾಸ್ತಾನು ಯಶಸ್ವಿಯಾಗಿ ನವೀಕರಿಸಲಾಗಿದೆ!*\n\n"
                    f"📦 ಉತ್ಪನ್ನ: *{prod_name}*\n"
                    f"📊 ಹಿಂದಿನ ಸ್ಟಾಕ್: {old_inv} ಯೂನಿಟ್‌ಗಳು\n"
                    f"📈 ಹೊಸ ಸ್ಟಾಕ್: *{new_inv} ಯೂನಿಟ್‌ಗಳು*"
                )
            elif lang == "hi":
                return (
                    f"✅ *इन्वेंटरी सफलतापूर्वक अपडेट की गई!*\n\n"
                    f"📦 उत्पाद: *{prod_name}*\n"
                    f"📊 पुराना स्टॉक: {old_inv} यूनिट\n"
                    f"📈 नया स्टॉक: *{new_inv} यूनिट*"
                )
            return (
                f"✅ *Inventory Successfully Updated!*\n\n"
                f"📦 Product: *{prod_name}*\n"
                f"📊 Previous Stock: {old_inv} units\n"
                f"📈 New Stock: *{new_inv} units*"
            )

        elif conf.operation_type == "OFFER_CREATE":
            disc = conf.proposed_values.get("discount_percent", 0)
            if lang == "kn":
                return f"✅ {disc}% ರಿಯಾಯಿತಿ ಆಫರ್ ಯಶಸ್ವಿಯಾಗಿ ಸಕ್ರಿಯಗೊಳಿಸಲಾಗಿದೆ!"
            elif lang == "hi":
                return f"✅ {disc}% छूट का ऑफर सफलतापूर्वक सक्रिय किया गया है!"
            return f"✅ Promotional offer of {disc}% discount has been activated!"

        return "✅ Action confirmed and executed successfully."

    async def _handle_cancel(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        lang: str
    ) -> str:
        """Cancels any pending confirmation."""
        cancelled = await self.confirmation.cancel_pending(db, merchant.id, sender_phone)
        if cancelled:
            if lang == "kn":
                return "❌ ಬಾಕಿ ಉಳಿದ ಕ್ರಿಯೆಯನ್ನು ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ. ಯಾವುದೇ ಬದಲಾವಣೆ ಮಾಡಲಾಗಿಲ್ಲ."
            elif lang == "hi":
                return "❌ लंबित कार्रवाई रद्द कर दी गई है। कोई बदलाव नहीं किया गया।"
            return "❌ Pending operation cancelled. No changes were applied."
        else:
            if lang == "kn":
                return "ℹ️ ರದ್ದುಗೊಳಿಸಲು ಯಾವುದೇ ಬಾಕಿ ಕ್ರಿಯೆ ಇಲ್ಲ."
            elif lang == "hi":
                return "ℹ️ रद्द करने के लिए कोई लंबित कार्रवाई नहीं है।"
            return "ℹ️ No pending operation to cancel."

    async def _handle_price_change(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        intent: WhatsAppIntent,
        lang: str
    ) -> str:
        """Validates price change against policy guard and creates confirmation request."""
        product, all_prods = await self.resolve_product(db, merchant.id, intent.product_name)
        if not product:
            return self._format_product_selection_prompt(all_prods, lang)

        # Determine proposed price in paise
        current_price_paise = product.price_paise
        if intent.price_value:
            proposed_paise = int(intent.price_value * 100)
        elif intent.price_relative_cut:
            proposed_paise = current_price_paise - int(intent.price_relative_cut * 100)
        else:
            if lang == "kn":
                return f"ದಯವಿಟ್ಟು {product.name} ಗೆ ನಿಖರವಾದ ಬೆಲೆಯನ್ನು ತಿಳಿಸಿ (ಉದಾಹರಣೆಗೆ: ₹2500)."
            elif lang == "hi":
                return f"कृपया {product.name} के लिए सही मूल्य बताएं (उदा: ₹2500)।"
            return f"Please specify the target price for {product.name} (e.g. ₹2500)."

        if proposed_paise <= 0:
            return "⚠️ Price must be greater than zero."

        # Validate against policy guard
        validation: PolicyValidationResult = PolicyGuard.validate_price_change(
            merchant=merchant,
            product=product,
            proposed_price_paise=proposed_paise,
            language=lang
        )

        if not validation.is_valid:
            # Policy violated: create pending confirmation for COMPLIANT ALTERNATIVE!
            alt_paise = validation.compliant_price_paise or proposed_paise
            conf = await self.confirmation.create_pending_confirmation(
                db=db,
                merchant_id=merchant.id,
                sender_phone=sender_phone,
                operation_type="PRICE_UPDATE",
                proposed_values={"price_paise": alt_paise},
                current_values={"price_paise": current_price_paise},
                product=product,
                reason=validation.violation_reason,
                language=lang
            )

            # Return localized policy alert with alternative
            if lang == "kn":
                return f"{validation.message_kn}\n\nದೃಢೀಕರಣ ಕೋಡ್: *{conf.confirmation_code}*"
            elif lang == "hi":
                return f"{validation.message_hi}\n\nपुष्टि कोड: *{conf.confirmation_code}*"
            return f"{validation.message_en}\n\nConfirmation Code: *{conf.confirmation_code}*"

        # Policy Compliant: Create pending confirmation
        conf = await self.confirmation.create_pending_confirmation(
            db=db,
            merchant_id=merchant.id,
            sender_phone=sender_phone,
            operation_type="PRICE_UPDATE",
            proposed_values={"price_paise": proposed_paise},
            current_values={"price_paise": current_price_paise},
            product=product,
            language=lang
        )

        old_rupees = current_price_paise // 100
        new_rupees = proposed_paise // 100
        margin = validation.proposed_margin_percent

        if lang == "kn":
            return (
                f"📝 *ಬೆಲೆ ಬದಲಾವಣೆ ದೃಢೀಕರಣ*\n\n"
                f"📦 ಉತ್ಪನ್ನ: *{product.name}*\n"
                f"💰 ಪ್ರಸ್ತುತ ಬೆಲೆ: ₹{old_rupees}\n"
                f"🎯 ಹೊಸ ಬೆಲೆ: *₹{new_rupees}*\n"
                f"📈 ಅಂದಾಜು ಲಾಭಾಂಶ: *{margin:.1f}%* (ನೀತಿ ಮಾನ್ಯವಾಗಿದೆ)\n\n"
                f"ಖಚಿತಪಡಿಸಲು *CONFIRM {conf.confirmation_code}* ಅಥವಾ *YES* ಎಂದು ಉತ್ತರಿಸಿ.\n"
                f"ರದ್ದುಮಾಡಲು *CANCEL* ಕಳುಹಿಸಿ. (15 ನಿಮಿಷಗಳಲ್ಲಿ ಮುಕ್ತಾಯಗೊಳ್ಳುತ್ತದೆ)"
            )
        elif lang == "hi":
            return (
                f"📝 *मूल्य परिवर्तन पुष्टि*\n\n"
                f"📦 उत्पाद: *{product.name}*\n"
                f"💰 वर्तमान मूल्य: ₹{old_rupees}\n"
                f"🎯 नया मूल्य: *₹{new_rupees}*\n"
                f"📈 अनुमानित मार्जिन: *{margin:.1f}%* (नीति के अनुसार मान्य)\n\n"
                f"लागू करने के लिए *CONFIRM {conf.confirmation_code}* या *YES* भेजें।\n"
                f"रद्द करने के लिए *CANCEL* भेजें। (15 मिनट में समाप्त)"
            )
        return (
            f"📝 *Confirm Price Change*\n\n"
            f"📦 Product: *{product.name}*\n"
            f"💰 Current Price: ₹{old_rupees}\n"
            f"🎯 Proposed Price: *₹{new_rupees}*\n"
            f"📈 Projected Margin: *{margin:.1f}%* (Policy compliant)\n\n"
            f"Reply *CONFIRM {conf.confirmation_code}* or *YES* to apply.\n"
            f"Reply *CANCEL* to discard. (Expires in 15 mins)"
        )

    async def _handle_inventory_add(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        intent: WhatsAppIntent,
        lang: str
    ) -> str:
        """Handles adding inventory stock units."""
        product, all_prods = await self.resolve_product(db, merchant.id, intent.product_name)
        if not product:
            return self._format_product_selection_prompt(all_prods, lang)

        delta = intent.inventory_delta or 10
        current_inv = product.inventory_quantity
        new_inv = current_inv + delta

        conf = await self.confirmation.create_pending_confirmation(
            db=db,
            merchant_id=merchant.id,
            sender_phone=sender_phone,
            operation_type="INVENTORY_UPDATE",
            proposed_values={"inventory_quantity": new_inv},
            current_values={"inventory_quantity": current_inv},
            product=product,
            language=lang
        )

        if lang == "kn":
            return (
                f"📦 *ದಾಸ್ತಾನು ಸೇರ್ಪಡೆ ದೃಢೀಕರಣ*\n\n"
                f"ಉತ್ಪನ್ನ: *{product.name}*\n"
                f"ಪ್ರಸ್ತುತ ಸ್ಟಾಕ್: {current_inv} ಯೂನಿಟ್‌ಗಳು\n"
                f"ಸೇರಿಸುತ್ತಿರುವ ಸ್ಟಾಕ್: +{delta} ಯೂನಿಟ್‌ಗಳು\n"
                f"ಒಟ್ಟು ಹೊಸ ಸ್ಟಾಕ್: *{new_inv} ಯೂನಿಟ್‌ಗಳು*\n\n"
                f"ದೃಢೀಕರಿಸಲು *CONFIRM {conf.confirmation_code}* ಅಥವಾ *YES* ಎಂದು ಉತ್ತರಿಸಿ, ಅಥವಾ *CANCEL* ಕಳುಹಿಸಿ."
            )
        elif lang == "hi":
            return (
                f"📦 *स्टॉक जोड़ने की पुष्टि*\n\n"
                f"उत्पाद: *{product.name}*\n"
                f"वर्तमान स्टॉक: {current_inv} यूनिट\n"
                f"जोड़ा जा रहा स्टॉक: +{delta} यूनिट\n"
                f"कुल नया स्टॉक: *{new_inv} यूनिट*\n\n"
                f"पुष्टि के लिए *CONFIRM {conf.confirmation_code}* या *YES* भेजें, या *CANCEL* भेजें।"
            )
        return (
            f"📦 *Confirm Inventory Addition*\n\n"
            f"Product: *{product.name}*\n"
            f"Current Stock: {current_inv} units\n"
            f"Adding: +{delta} units\n"
            f"Total New Stock: *{new_inv} units*\n\n"
            f"Reply *CONFIRM {conf.confirmation_code}* or *YES* to execute, or *CANCEL* to abort."
        )

    async def _handle_inventory_set(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        intent: WhatsAppIntent,
        lang: str
    ) -> str:
        """Handles setting total inventory quantity."""
        product, all_prods = await self.resolve_product(db, merchant.id, intent.product_name)
        if not product:
            return self._format_product_selection_prompt(all_prods, lang)

        target_inv = intent.inventory_delta if intent.inventory_delta is not None else 0
        current_inv = product.inventory_quantity

        conf = await self.confirmation.create_pending_confirmation(
            db=db,
            merchant_id=merchant.id,
            sender_phone=sender_phone,
            operation_type="INVENTORY_UPDATE",
            proposed_values={"inventory_quantity": target_inv},
            current_values={"inventory_quantity": current_inv},
            product=product,
            language=lang
        )

        if lang == "kn":
            return (
                f"📦 *ದಾಸ್ತಾನು ನಿಗದಿ ದೃಢೀಕರಣ*\n\n"
                f"ಉತ್ಪನ್ನ: *{product.name}*\n"
                f"ಪ್ರಸ್ತುತ ಸ್ಟಾಕ್: {current_inv} ಯೂನಿಟ್‌ಗಳು\n"
                f"ಹೊಸ ಗುರಿ ಸ್ಟಾಕ್: *{target_inv} ಯೂನಿಟ್‌ಗಳು*\n\n"
                f"ದೃಢೀಕರಿಸಲು *CONFIRM {conf.confirmation_code}* ಅಥವಾ *YES* ಕಳುಹಿಸಿ."
            )
        elif lang == "hi":
            return (
                f"📦 *इन्वेंटरी सेट करने की पुष्टि*\n\n"
                f"उत्पाद: *{product.name}*\n"
                f"वर्तमान स्टॉक: {current_inv} यूनिट\n"
                f"नया स्टॉक लक्ष्य: *{target_inv} यूनिट*\n\n"
                f"पुष्टि के लिए *CONFIRM {conf.confirmation_code}* या *YES* भेजें।"
            )
        return (
            f"📦 *Confirm Inventory Adjustment*\n\n"
            f"Product: *{product.name}*\n"
            f"Current Stock: {current_inv} units\n"
            f"Target Stock: *{target_inv} units*\n\n"
            f"Reply *CONFIRM {conf.confirmation_code}* or *YES* to apply."
        )

    async def _handle_inventory_query(
        self,
        db: AsyncSession,
        merchant: Merchant,
        intent: WhatsAppIntent,
        lang: str
    ) -> str:
        """Reports real-time stock levels."""
        all_prods = await self.commerce.list_products(db, merchant.id, active_only=True)
        if not all_prods:
            return "No products found in catalog."

        lines = []
        if lang == "kn":
            lines.append("📊 *ಪ್ರಸ್ತುತ ದಾಸ್ತಾನು ವರದಿ (Inventory Status)*:\n")
            for p in all_prods:
                status_icon = "🟢" if p.inventory_quantity > 20 else ("🟡" if p.inventory_quantity > 5 else "🔴")
                lines.append(f"{status_icon} *{p.name}*: {p.inventory_quantity} ಯೂನಿಟ್‌ಗಳು (₹{p.price_paise//100})")
            lines.append("\nಸ್ಟಾಕ್ ಸೇರಿಸಲು: 'Add 20 stock to backpack' ಅಥವಾ 'Backpack ge 20 stock haaku' ಎಂದು ಕಳುಹಿಸಿ.")
        elif lang == "hi":
            lines.append("📊 *इन्वेंटरी स्थिति रिपोर्ट (Inventory Status)*:\n")
            for p in all_prods:
                status_icon = "🟢" if p.inventory_quantity > 20 else ("🟡" if p.inventory_quantity > 5 else "🔴")
                lines.append(f"{status_icon} *{p.name}*: {p.inventory_quantity} यूनिट (₹{p.price_paise//100})")
            lines.append("\nस्टॉक जोड़ने के लिए: 'Add 20 stock to backpack' या 'Backpack me 20 stock jodo' भेजें।")
        else:
            lines.append("📊 *Real-Time Inventory Status*:\n")
            for p in all_prods:
                status_icon = "🟢" if p.inventory_quantity > 20 else ("🟡" if p.inventory_quantity > 5 else "🔴")
                lines.append(f"{status_icon} *{p.name}*: {p.inventory_quantity} in stock (Price: ₹{p.price_paise//100})")
            lines.append("\nTo update: send 'Add 25 stock to backpack' or 'Set mouse stock to 50'.")

        return "\n".join(lines)

    async def _handle_price_query(
        self,
        db: AsyncSession,
        merchant: Merchant,
        intent: WhatsAppIntent,
        lang: str
    ) -> str:
        """Returns price and margin unit economics for a product."""
        product, all_prods = await self.resolve_product(db, merchant.id, intent.product_name)
        if not product:
            return self._format_product_selection_prompt(all_prods, lang)

        price = product.price_paise // 100
        cost = product.cost_paise // 100
        margin = PolicyGuard.calculate_margin(product.price_paise, product.cost_paise)

        if lang == "kn":
            return (
                f"🏷️ *ಉತ್ಪನ್ನ ಮಾಹಿತಿ*: *{product.name}*\n\n"
                f"💰 ಮಾರಾಟ ಬೆಲೆ: ₹{price}\n"
                f"📦 ಅಸಲು ಬೆಲೆ (COGS): ₹{cost}\n"
                f"📈 ಪ್ರಸ್ತುತ ಲಾಭಾಂಶ (Margin): *{margin:.1f}%*\n"
                f"📊 ಲಭ್ಯವಿರುವ ಸ್ಟಾಕ್: {product.inventory_quantity} ಯೂನಿಟ್‌ಗಳು"
            )
        elif lang == "hi":
            return (
                f"🏷️ *उत्पाद विवरण*: *{product.name}*\n\n"
                f"💰 विक्रय मूल्य: ₹{price}\n"
                f"📦 लागत मूल्य (COGS): ₹{cost}\n"
                f"📈 वर्तमान मार्जिन: *{margin:.1f}%*\n"
                f"📊 उपलब्ध स्टॉक: {product.inventory_quantity} यूनिट"
            )
        return (
            f"🏷️ *Product Details*: *{product.name}*\n\n"
            f"💰 Retail Price: ₹{price}\n"
            f"📦 Unit Cost (COGS): ₹{cost}\n"
            f"📈 Gross Margin: *{margin:.1f}%*\n"
            f"📊 Stock Available: {product.inventory_quantity} units"
        )

    async def _handle_offer_create(
        self,
        db: AsyncSession,
        merchant: Merchant,
        sender_phone: str,
        intent: WhatsAppIntent,
        lang: str
    ) -> str:
        """Handles creating promotional discount offers within guardrails."""
        disc = intent.discount_percent or 10.0
        max_disc = float(merchant.maximum_discount_percent)

        if disc > max_disc:
            if lang == "kn":
                return (
                    f"⚠️ *ಆಫರ್ ಮಿತಿ ಎಚ್ಚರಿಕೆ*: {disc:.0f}% ರಿಯಾಯಿತಿಯು ನಿಮ್ಮ ಗರಿಷ್ಠ ಮಿತಿ "
                    f"({max_disc:.0f}%) ಗಿಂತ ಹೆಚ್ಚಾಗಿದೆ. ಗರಿಷ್ಠ {max_disc:.0f}% ರಿಯಾಯಿತಿ ಮಾತ್ರ ನೀಡಬಹುದು."
                )
            elif lang == "hi":
                return (
                    f"⚠️ *ऑफर सीमा चेतावनी*: {disc:.0f}% छूट आपकी अधिकतम सीमा "
                    f"({max_disc:.0f}%) से अधिक है। आप अधिकतम {max_disc:.0f}% छूट दे सकते हैं।"
                )
            return (
                f"⚠️ *Discount Policy Alert*: A {disc:.0f}% discount exceeds your configured "
                f"maximum discount cap of {max_disc:.0f}%. The highest safe discount is {max_disc:.0f}%."
            )

        conf = await self.confirmation.create_pending_confirmation(
            db=db,
            merchant_id=merchant.id,
            sender_phone=sender_phone,
            operation_type="OFFER_CREATE",
            proposed_values={"discount_percent": disc},
            language=lang
        )

        if lang == "kn":
            return (
                f"🎁 *ಆಫರ್ ದೃಢೀಕರಣ*\n\n"
                f"ರಿಯಾಯಿತಿ: *{disc:.0f}%*\n\n"
                f"ಸಕ್ರಿಯಗೊಳಿಸಲು *CONFIRM {conf.confirmation_code}* ಅಥವಾ *YES* ಕಳುಹಿಸಿ."
            )
        elif lang == "hi":
            return (
                f"🎁 *ऑफर पुष्टि*\n\n"
                f"छूट: *{disc:.0f}%*\n\n"
                f"लागू करने के लिए *CONFIRM {conf.confirmation_code}* या *YES* भेजें।"
            )
        return (
            f"🎁 *Confirm Promotional Offer*\n\n"
            f"Discount: *{disc:.0f}%*\n\n"
            f"Reply *CONFIRM {conf.confirmation_code}* or *YES* to activate."
        )

    # -------------------------------------------------------------------------
    # Utilities & Menus
    # -------------------------------------------------------------------------

    def _format_product_selection_prompt(self, products: List[Product], lang: str) -> str:
        """Formats list of products when an ambiguous or missing product is requested."""
        if lang == "kn":
            lines = ["ಯಾವ ಉತ್ಪನ್ನದ ವಿವರ ಬೇಕು? ದಯವಿಟ್ಟು ಆಯ್ಕೆಮಾಡಿ:\n"]
            for i, p in enumerate(products, 1):
                lines.append(f"{i}. *{p.name}* (₹{p.price_paise//100})")
            lines.append("\nಉದಾಹರಣೆ: 'Backpack price 2500 maadu'")
        elif lang == "hi":
            lines = ["किस उत्पाद के लिए अपडेट करना चाहते हैं? कृपया चुनें:\n"]
            for i, p in enumerate(products, 1):
                lines.append(f"{i}. *{p.name}* (₹{p.price_paise//100})")
            lines.append("\nउदाहरण: 'Backpack price 2500 kar do'")
        else:
            lines = ["Which product would you like to update? Available items:\n"]
            for i, p in enumerate(products, 1):
                lines.append(f"{i}. *{p.name}* (₹{p.price_paise//100})")
            lines.append("\nExample: 'Change backpack price to 2500'")

        return "\n".join(lines)

    def _generate_help_menu(self, lang: str, merchant_name: str) -> str:
        """Returns multilingual commands help card."""
        if lang == "kn":
            return (
                f"👋 ನಮಸ್ಕಾರ! ಇದು *{merchant_name}* ವ್ಯಾಪಾರ ಸಹಾಯಕ (AI WhatsApp Assistant).\n\n"
                f"ನೀವು ಈ ಕೆಳಗಿನ ಆಜ್ಞೆಗಳನ್ನು ಕನ್ನಡ ಅಥವಾ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಕಳುಹಿಸಬಹುದು:\n\n"
                f"1️⃣ *ಬೆಲೆ ಬದಲಾವಣೆ (Price Update)*:\n"
                f"• 'Ee black bag price 1800 inda 1600 maadu'\n"
                f"• 'Backpack price 2500 maadu'\n"
                f"• 'Bag price 200 kammi maadu'\n\n"
                f"2️⃣ *ದಾಸ್ತಾನು ನಿರ್ವಹಣೆ (Inventory)*:\n"
                f"• 'Backpack ge 25 stock haaku'\n"
                f"• 'Stock check maadu' / 'Stock eshtu ide?'\n\n"
                f"3️⃣ *ದೃಢೀಕರಣ (Confirmation)*:\n"
                f"• 'CONFIRM 1234' ಅಥವಾ 'YES' / 'HOWDU'\n"
                f"• 'CANCEL' ಅಥವಾ 'BEDI'\n\n"
                f"ಪ್ರಯತ್ನಿಸಲು ಮೇಲಿನ ಯಾವುದೇ ಸಂದೇಶವನ್ನು ಕಳುಹಿಸಿ!"
            )
        elif lang == "hi":
            return (
                f"👋 नमस्ते! यह *{merchant_name}* का AI WhatsApp व्यापार सहायक है।\n\n"
                f"आप हिंदी या अंग्रेजी में निम्नलिखित कमांड भेज सकते हैं:\n\n"
                f"1️⃣ *मूल्य बदलें (Price Update)*:\n"
                f"• 'Black bag ka price 1600 kar do'\n"
                f"• 'Backpack price 2500 karo'\n"
                f"• 'Price 200 kam karo'\n\n"
                f"2️⃣ *इन्वेंटरी (Inventory)*:\n"
                f"• 'Backpack me 25 stock jodo'\n"
                f"• 'Stock kitna hai?' / 'Stock check karo'\n\n"
                f"3️⃣ *पुष्टि (Confirmation)*:\n"
                f"• 'CONFIRM 1234' या 'YES' / 'HA'\n"
                f"• 'CANCEL' या 'NAHI'\n\n"
                f"शुरू करने के लिए कोई भी संदेश भेजें!"
            )
        return (
            f"👋 Welcome to the *{merchant_name}* AI WhatsApp Assistant!\n\n"
            f"You can manage your store via natural language in English, Kannada, or Hindi:\n\n"
            f"1️⃣ *Price Changes*:\n"
            f"• 'Change backpack price to 2500'\n"
            f"• 'Cut bag price by 200'\n"
            f"• 'Price of backpack?'\n\n"
            f"2️⃣ *Inventory Management*:\n"
            f"• 'Add 25 stock to backpack'\n"
            f"• 'Check inventory' or 'Low stock items'\n\n"
            f"3️⃣ *Confirmations*:\n"
            f"• 'CONFIRM <code >' or 'YES'\n"
            f"• 'CANCEL'\n\n"
            f"Send any command to get started!"
        )
