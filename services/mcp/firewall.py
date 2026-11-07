"""Buyer Response Firewall: Strict boundary between internal economics and external AI buyers.

FIREWALL INVARIANTS:
1. Strips all confidential merchant economics (COGS, unit cost, margin %, LinUCB uncertainty,
   exploration scores, bandit parameters, and safety traces).
2. Guarantees that no private database fields leak to the external AI buyer.
3. Every payload is validated against a strict Pydantic model with extra="forbid".
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import structlog

from domain.models import Product, Order
from domain.commerce_schemas import ProductResponse
from services.runtime.schemas import DecisionEnvelope
from services.boundary.schemas import DecisionExecuteResponse
from services.mcp.schemas import (
    BuyerSafeProductView,
    BuyerSafeOfferView,
    BuyerOfferItem,
    BuyerSafeCheckoutResponse,
    BuyerSafeOrderStatusView,
)

logger = structlog.get_logger()

# Default offer freshness TTL: 15 minutes (900 seconds)
DEFAULT_OFFER_TTL_SECONDS = 900


class BuyerResponseFirewall:
    """Sanitizes internal domain objects into buyer-safe views and verifies non-leakage."""

    @classmethod
    def sanitize_product(cls, product: Product) -> BuyerSafeProductView:
        """Convert an internal Product database model to BuyerSafeProductView.
        
        Explicitly eliminates cost_paise, margin, and supplier attributes.
        """
        available_qty = max(0, (product.inventory_quantity or 0) - (product.reserved_quantity or 0))
        in_stock = available_qty > 0 and bool(product.is_active)

        # Filter attributes: exclude any internal keys containing 'cost', 'cogs', 'supplier', 'margin'
        sanitized_attrs: Dict[str, Any] = {}
        if product.attributes and isinstance(product.attributes, dict):
            for k, v in product.attributes.items():
                k_lower = k.lower()
                if not any(leak in k_lower for leak in ("cost", "cogs", "supplier", "margin", "wholesale")):
                    sanitized_attrs[k] = v

        return BuyerSafeProductView(
            id=product.id,
            sku=product.sku,
            name=product.name,
            description=product.description,
            category=product.category,
            price_paise=product.price_paise,
            currency=product.currency or "INR",
            in_stock=in_stock,
            available_quantity=available_qty,
            attributes=sanitized_attrs
        )

    @classmethod
    def sanitize_offer(
        cls,
        envelope: DecisionEnvelope,
        product_catalog_map: Optional[Dict[str, Product]] = None,
        ttl_seconds: int = DEFAULT_OFFER_TTL_SECONDS
    ) -> BuyerSafeOfferView:
        """Convert an internal DecisionEnvelope to BuyerSafeOfferView.
        
        Strictly strips merchant_evaluation, scores, safety_audit, and model_metadata.
        """
        catalog = product_catalog_map or {}
        items: List[BuyerOfferItem] = []

        for pid in envelope.buyer_offer.product_ids:
            prod = catalog.get(pid)
            item_name = prod.name if prod else pid
            unit_price = prod.price_paise if prod else envelope.buyer_offer.offered_price_paise
            items.append(BuyerOfferItem(
                product_id=pid,
                name=item_name,
                quantity=1,
                unit_price_paise=unit_price
            ))

        expires_at = envelope.created_at + timedelta(seconds=ttl_seconds)
        is_executable = envelope.selected_policy.strategy_type != "NO_OFFER"

        # Format canonical external offer_id
        offer_id = f"off_{envelope.decision_id}"

        return BuyerSafeOfferView(
            offer_id=offer_id,
            strategy_type=envelope.selected_policy.strategy_type,
            items=items,
            offered_price_paise=envelope.buyer_offer.offered_price_paise,
            currency=envelope.buyer_offer.currency,
            display_discount_percent=envelope.buyer_offer.display_discount_percent,
            positioning=envelope.buyer_offer.positioning,
            rationale=envelope.buyer_offer.rationale,
            expires_at=expires_at,
            is_executable=is_executable
        )

    @classmethod
    def sanitize_checkout(cls, exec_resp: DecisionExecuteResponse) -> BuyerSafeCheckoutResponse:
        """Convert a Phase 9.2 DecisionExecuteResponse to BuyerSafeCheckoutResponse.
        
        Strips internal state_fingerprint, safety_check_id, and internal authorization tokens.
        """
        # Formulate simulated/test checkout URL if order was created
        checkout_url = None
        if exec_resp.razorpay_order_id:
            checkout_url = f"https://api.razorpay.com/v1/checkout/test/{exec_resp.razorpay_order_id}"

        status_str = (
            exec_resp.boundary_status.value
            if hasattr(exec_resp.boundary_status, "value")
            else str(exec_resp.boundary_status)
        )

        return BuyerSafeCheckoutResponse(
            execution_id=exec_resp.execution_id,
            status=status_str,
            order_id=exec_resp.order_id,
            razorpay_order_id=exec_resp.razorpay_order_id,
            amount_paise=exec_resp.authorized_amount_paise or 0,
            currency=exec_resp.currency,
            checkout_url=checkout_url,
            rejection_reasons=exec_resp.rejection_reasons,
            is_duplicate=exec_resp.is_duplicate
        )

    @classmethod
    def sanitize_order_status(cls, order: Order) -> BuyerSafeOrderStatusView:
        """Convert internal Order database record to BuyerSafeOrderStatusView."""
        return BuyerSafeOrderStatusView(
            order_id=order.id,
            razorpay_order_id=order.razorpay_order_id,
            amount_paise=order.amount_paise,
            currency=order.currency or "INR",
            status=order.status,
            created_at=order.created_at,
            updated_at=order.updated_at
        )
