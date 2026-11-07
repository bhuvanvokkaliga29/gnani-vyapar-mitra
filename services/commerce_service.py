"""Deterministic Merchant Commerce Service Subsystem.

Manages tenant catalog, inventory stock, product affinity relationships,
business constraints, and builds the unified MerchantCommerceContext.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from domain.models import Merchant, Product, ProductRelationship, MerchantPriority, AuditEvent
from domain.economics import (
    calculate_gross_profit,
    calculate_gross_margin_percent,
    calculate_available_to_sell,
    is_product_eligible
)
from domain.commerce_schemas import (
    MerchantCreateRequest,
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductResponse,
    RelationshipCreateRequest,
    RelationshipResponse,
    ConstraintsUpdateRequest,
    PrioritiesUpdateRequest,
    MerchantCommerceContext
)

logger = structlog.get_logger()


class CommerceServiceError(Exception):
    """Base exception for commerce service domain errors."""
    pass


class MerchantNotFoundError(CommerceServiceError):
    pass


class ProductNotFoundError(CommerceServiceError):
    pass


class DuplicateSkuError(CommerceServiceError):
    pass


class InvalidRelationshipError(CommerceServiceError):
    pass


class CommerceService:
    """Service handling catalog, economics, relationships, and context generation."""

    async def create_merchant(self, db: AsyncSession, req: MerchantCreateRequest) -> Merchant:
        """Register a new merchant tenant with business objectives and constraints."""
        existing = await self.get_merchant(db, req.id)
        if existing:
            raise CommerceServiceError(f"Merchant with ID '{req.id}' already exists")

        merchant = Merchant(
            id=req.id,
            name=req.name,
            currency=req.currency.upper(),
            status="ACTIVE",
            business_objective=req.business_objective,
            minimum_margin_percent=req.minimum_margin_percent,
            maximum_discount_percent=req.maximum_discount_percent,
            target_aov_paise=req.target_aov_paise
        )
        db.add(merchant)

        # Initialize empty priorities container
        priority = MerchantPriority(merchant_id=req.id)
        db.add(priority)

        # Audit event
        audit = AuditEvent(
            entity_type="MERCHANT",
            entity_id=req.id,
            actor="COMMERCE_SERVICE",
            action="merchant_created",
            payload={"name": req.name, "currency": req.currency}
        )
        db.add(audit)

        await db.commit()
        await db.refresh(merchant)
        logger.info("merchant_created", merchant_id=req.id, name=req.name)
        return merchant

    async def get_merchant(self, db: AsyncSession, merchant_id: str) -> Optional[Merchant]:
        """Fetch merchant tenant by primary ID."""
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_merchant_constraints(
        self,
        db: AsyncSession,
        merchant_id: str,
        req: ConstraintsUpdateRequest
    ) -> Merchant:
        """Update merchant financial guardrails and business objectives."""
        merchant = await self.get_merchant(db, merchant_id)
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{merchant_id}' not found")

        if req.minimum_margin_percent is not None:
            merchant.minimum_margin_percent = req.minimum_margin_percent
        if req.maximum_discount_percent is not None:
            merchant.maximum_discount_percent = req.maximum_discount_percent
        if req.target_aov_paise is not None:
            merchant.target_aov_paise = req.target_aov_paise
        if req.business_objective is not None:
            merchant.business_objective = req.business_objective

        audit = AuditEvent(
            entity_type="MERCHANT",
            entity_id=merchant_id,
            actor="COMMERCE_SERVICE",
            action="constraints_updated",
            payload={
                "min_margin": float(merchant.minimum_margin_percent),
                "max_discount": float(merchant.maximum_discount_percent),
                "target_aov": merchant.target_aov_paise,
                "objective": merchant.business_objective
            }
        )
        db.add(audit)
        await db.commit()
        await db.refresh(merchant)
        logger.info("merchant_constraints_updated", merchant_id=merchant_id)
        return merchant

    async def set_merchant_priorities(
        self,
        db: AsyncSession,
        merchant_id: str,
        req: PrioritiesUpdateRequest
    ) -> MerchantPriority:
        """Update merchant product and category priorities."""
        merchant = await self.get_merchant(db, merchant_id)
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{merchant_id}' not found")

        stmt = select(MerchantPriority).where(MerchantPriority.merchant_id == merchant_id)
        result = await db.execute(stmt)
        priorities = result.scalar_one_or_none()

        if not priorities:
            priorities = MerchantPriority(merchant_id=merchant_id)
            db.add(priorities)

        priorities.priority_product_ids = req.priority_product_ids
        priorities.priority_categories = req.priority_categories
        priorities.clearance_product_ids = req.clearance_product_ids

        await db.commit()
        await db.refresh(priorities)
        logger.info("merchant_priorities_updated", merchant_id=merchant_id)
        return priorities

    async def create_product(
        self,
        db: AsyncSession,
        merchant_id: str,
        req: ProductCreateRequest
    ) -> Product:
        """Create a new product in the merchant catalog with validation."""
        merchant = await self.get_merchant(db, merchant_id)
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{merchant_id}' not found")

        # Currency consistency enforcement
        if req.currency.upper() != merchant.currency.upper():
            raise CommerceServiceError(
                f"Product currency '{req.currency.upper()}' does not match merchant base currency '{merchant.currency.upper()}'"
            )

        # Inventory reservation invariant
        if req.reserved_quantity > req.inventory_quantity:
            raise CommerceServiceError("Reserved quantity cannot exceed total inventory quantity")

        # Enforce unique SKU within merchant scope
        sku_stmt = select(Product).where(
            and_(Product.merchant_id == merchant_id, Product.sku == req.sku)
        )
        if (await db.execute(sku_stmt)).scalar_one_or_none():
            raise DuplicateSkuError(f"SKU '{req.sku}' already exists for merchant '{merchant_id}'")

        # Enforce unique product ID
        id_stmt = select(Product).where(Product.id == req.id)
        if (await db.execute(id_stmt)).scalar_one_or_none():
            raise CommerceServiceError(f"Product ID '{req.id}' already exists")

        product = Product(
            id=req.id,
            merchant_id=merchant_id,
            sku=req.sku,
            name=req.name,
            description=req.description,
            category=req.category,
            price_paise=req.price_paise,
            cost_paise=req.cost_paise,
            currency=req.currency.upper(),
            inventory_quantity=req.inventory_quantity,
            reserved_quantity=req.reserved_quantity,
            is_active=req.is_active,
            attributes=req.attributes
        )
        db.add(product)

        audit = AuditEvent(
            entity_type="PRODUCT",
            entity_id=product.id,
            actor="COMMERCE_SERVICE",
            action="product_created",
            payload={"sku": product.sku, "price_paise": product.price_paise, "category": product.category}
        )
        db.add(audit)

        await db.commit()
        await db.refresh(product)
        logger.info("product_created", merchant_id=merchant_id, product_id=product.id, sku=product.sku)
        return product

    async def update_product(
        self,
        db: AsyncSession,
        merchant_id: str,
        product_id: str,
        req: ProductUpdateRequest
    ) -> Product:
        """Update an existing product's pricing, cost, or inventory with validation."""
        product = await self.get_product(db, product_id)
        if not product or product.merchant_id != merchant_id:
            raise ProductNotFoundError(f"Product '{product_id}' not found for merchant '{merchant_id}'")

        new_inv = req.inventory_quantity if req.inventory_quantity is not None else product.inventory_quantity
        new_res = req.reserved_quantity if req.reserved_quantity is not None else product.reserved_quantity

        if new_res > new_inv:
            raise CommerceServiceError("Reserved quantity cannot exceed total inventory quantity")

        if req.name is not None:
            product.name = req.name
        if req.description is not None:
            product.description = req.description
        if req.category is not None:
            product.category = req.category
        if req.price_paise is not None:
            product.price_paise = req.price_paise
        if req.cost_paise is not None:
            product.cost_paise = req.cost_paise
        if req.inventory_quantity is not None:
            product.inventory_quantity = req.inventory_quantity
        if req.reserved_quantity is not None:
            product.reserved_quantity = req.reserved_quantity
        if req.is_active is not None:
            product.is_active = req.is_active
        if req.attributes is not None:
            product.attributes = req.attributes

        audit = AuditEvent(
            entity_type="PRODUCT",
            entity_id=product.id,
            actor="COMMERCE_SERVICE",
            action="product_updated",
            payload={"price_paise": product.price_paise, "inventory": product.inventory_quantity}
        )
        db.add(audit)

        await db.commit()
        await db.refresh(product)
        logger.info("product_updated", merchant_id=merchant_id, product_id=product.id)
        return product

    async def get_product(self, db: AsyncSession, product_id: str) -> Optional[Product]:
        """Fetch product by ID."""
        stmt = select(Product).where(Product.id == product_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_products(
        self,
        db: AsyncSession,
        merchant_id: str,
        active_only: bool = False
    ) -> List[Product]:
        """List products for a given merchant with deterministic ID ordering."""
        conditions = [Product.merchant_id == merchant_id]
        if active_only:
            conditions.append(Product.is_active.is_(True))

        stmt = select(Product).where(and_(*conditions)).order_by(Product.id.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_product_relationship(
        self,
        db: AsyncSession,
        merchant_id: str,
        req: RelationshipCreateRequest
    ) -> ProductRelationship:
        """Create a validated product relationship."""
        # 1. Reject self-referencing relationships
        if req.primary_product_id == req.related_product_id:
            raise InvalidRelationshipError("Product cannot have a relationship with itself")

        # 2. Verify both products exist and belong to the same merchant tenant
        p1 = await self.get_product(db, req.primary_product_id)
        p2 = await self.get_product(db, req.related_product_id)

        if not p1:
            raise ProductNotFoundError(f"Primary product '{req.primary_product_id}' not found")
        if not p2:
            raise ProductNotFoundError(f"Related product '{req.related_product_id}' not found")

        if p1.merchant_id != merchant_id or p2.merchant_id != merchant_id:
            raise InvalidRelationshipError("Cross-merchant product relationships are prohibited")

        # 3. Check for existing duplicate relationship
        dup_stmt = select(ProductRelationship).where(
            and_(
                ProductRelationship.primary_product_id == req.primary_product_id,
                ProductRelationship.related_product_id == req.related_product_id,
                ProductRelationship.relationship_type == req.relationship_type
            )
        )
        if (await db.execute(dup_stmt)).scalar_one_or_none():
            raise InvalidRelationshipError("Relationship between these products of this type already exists")

        rel = ProductRelationship(
            merchant_id=merchant_id,
            primary_product_id=req.primary_product_id,
            related_product_id=req.related_product_id,
            relationship_type=req.relationship_type.upper(),
            affinity_score=req.affinity_score,
            source=req.source,
            confidence=req.confidence
        )
        db.add(rel)

        audit = AuditEvent(
            entity_type="PRODUCT_RELATIONSHIP",
            entity_id=f"{req.primary_product_id}_{req.related_product_id}",
            actor="COMMERCE_SERVICE",
            action="relationship_created",
            payload={"type": rel.relationship_type, "affinity": float(rel.affinity_score)}
        )
        db.add(audit)

        await db.commit()
        await db.refresh(rel)
        logger.info(
            "relationship_created",
            primary=req.primary_product_id,
            related=req.related_product_id,
            type=rel.relationship_type
        )
        return rel

    async def list_relationships(
        self,
        db: AsyncSession,
        merchant_id: str
    ) -> List[ProductRelationship]:
        """List all product relationships for a merchant with deterministic ordering."""
        stmt = (
            select(ProductRelationship)
            .where(ProductRelationship.merchant_id == merchant_id)
            .order_by(
                ProductRelationship.primary_product_id.asc(),
                ProductRelationship.related_product_id.asc(),
                ProductRelationship.relationship_type.asc()
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_merchant_commerce_context(
        self,
        db: AsyncSession,
        merchant_id: str
    ) -> MerchantCommerceContext:
        """Generate the unified, strongly-typed merchant commercial knowledge object.

        This single context object provides the future Policy Agent with all
        inviolable commercial ground truth:
        - Merchant objectives
        - Constraints
        - Catalog items with unit economics and eligibility
        - Known product affinity relationships
        - Catalog priorities
        """
        merchant = await self.get_merchant(db, merchant_id)
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{merchant_id}' not found")

        products = await self.list_products(db, merchant_id)
        relationships = await self.list_relationships(db, merchant_id)

        # Retrieve priorities
        priorities_stmt = select(MerchantPriority).where(MerchantPriority.merchant_id == merchant_id)
        priorities_res = await db.execute(priorities_stmt)
        priorities_obj = priorities_res.scalar_one_or_none()

        priorities_dict = {
            "priority_product_ids": sorted(priorities_obj.priority_product_ids) if priorities_obj else [],
            "priority_categories": sorted(priorities_obj.priority_categories) if priorities_obj else [],
            "clearance_product_ids": sorted(priorities_obj.clearance_product_ids) if priorities_obj else []
        }

        # Build product responses with deterministic economics
        product_dtos: List[ProductResponse] = []
        for p in products:
            profit = calculate_gross_profit(p.price_paise, p.cost_paise)
            margin_pct = calculate_gross_margin_percent(p.price_paise, p.cost_paise)
            available = calculate_available_to_sell(p.inventory_quantity, p.reserved_quantity)
            is_elig, inelig_reason = is_product_eligible(
                price_paise=p.price_paise,
                cost_paise=p.cost_paise,
                inventory_quantity=p.inventory_quantity,
                reserved_quantity=p.reserved_quantity,
                is_active=p.is_active,
                minimum_margin_percent=merchant.minimum_margin_percent
            )

            product_dtos.append(
                ProductResponse(
                    id=p.id,
                    merchant_id=p.merchant_id,
                    sku=p.sku,
                    name=p.name,
                    description=p.description,
                    category=p.category,
                    price_paise=p.price_paise,
                    cost_paise=p.cost_paise,
                    currency=p.currency,
                    inventory_quantity=p.inventory_quantity,
                    reserved_quantity=p.reserved_quantity,
                    available_to_sell=available,
                    gross_profit_paise=profit,
                    gross_margin_percent=margin_pct,
                    is_active=p.is_active,
                    is_eligible=is_elig,
                    ineligibility_reason=inelig_reason,
                    attributes=p.attributes or {},
                    created_at=p.created_at,
                    updated_at=p.updated_at
                )
            )

        relationship_dtos = [
            RelationshipResponse(
                id=r.id,
                merchant_id=r.merchant_id,
                primary_product_id=r.primary_product_id,
                related_product_id=r.related_product_id,
                relationship_type=r.relationship_type,
                affinity_score=r.affinity_score,
                source=r.source,
                confidence=r.confidence,
                created_at=r.created_at
            )
            for r in relationships
        ]

        context = MerchantCommerceContext(
            merchant_id=merchant.id,
            merchant_name=merchant.name,
            currency=merchant.currency,
            status=merchant.status,
            business_objective=merchant.business_objective,
            constraints={
                "minimum_margin_percent": merchant.minimum_margin_percent,
                "maximum_discount_percent": merchant.maximum_discount_percent,
                "target_aov_paise": merchant.target_aov_paise
            },
            priorities=priorities_dict,
            products=product_dtos,
            relationships=relationship_dtos
        )

        audit = AuditEvent(
            entity_type="MERCHANT",
            entity_id=merchant_id,
            actor="COMMERCE_SERVICE",
            action="commerce_context_requested",
            payload={"product_count": len(product_dtos), "relationship_count": len(relationship_dtos)}
        )
        db.add(audit)
        await db.commit()

        logger.info(
            "commerce_context_generated",
            merchant_id=merchant_id,
            product_count=len(product_dtos),
            relationship_count=len(relationship_dtos)
        )
        return context
