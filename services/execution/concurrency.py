"""Concurrency & Atomic Inventory Reservation Manager for Phase 5."""

from typing import Dict, List, Tuple
from sqlalchemy import update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from domain.models import Product

logger = structlog.get_logger()


class InventoryReservationManager:
    """Manages atomic reservation, release, and deduction of physical SKU inventory."""

    async def reserve_inventory(
        self,
        db: AsyncSession,
        product_quantities: Dict[str, int]
    ) -> bool:
        """Atomically reserve inventory for a batch of products within current transaction.

        Uses atomic conditional updates:
        UPDATE products SET reserved_quantity = reserved_quantity + :qty
        WHERE id = :pid AND (inventory_quantity - reserved_quantity) >= :qty

        If ANY product in the batch has insufficient stock, rolls back all reservations
        in the batch and returns False.
        """
        reserved_so_far: List[Tuple[str, int]] = []

        for pid, qty in product_quantities.items():
            if qty <= 0:
                continue

            stmt = (
                update(Product)
                .where(
                    and_(
                        Product.id == pid,
                        Product.is_active.is_(True),
                        (Product.inventory_quantity - Product.reserved_quantity) >= qty
                    )
                )
                .values(reserved_quantity=Product.reserved_quantity + qty)
            )
            res = await db.execute(stmt)

            if res.rowcount == 0:
                logger.warn(
                    "atomic_inventory_reservation_failed",
                    product_id=pid,
                    requested_qty=qty,
                    message="Insufficient available-to-sell stock"
                )
                # Roll back already applied reservations in this batch
                for prev_pid, prev_qty in reserved_so_far:
                    rollback_stmt = (
                        update(Product)
                        .where(Product.id == prev_pid)
                        .values(reserved_quantity=func.max(0, Product.reserved_quantity - prev_qty))
                    )
                    await db.execute(rollback_stmt)

                return False

            reserved_so_far.append((pid, qty))

        logger.info("inventory_batch_reserved_atomically", items=reserved_so_far)
        return True

    async def release_inventory(
        self,
        db: AsyncSession,
        product_quantities: Dict[str, int]
    ) -> None:
        """Release reserved inventory on execution failure, cancellation, or rejection."""
        for pid, qty in product_quantities.items():
            if qty <= 0:
                continue

            stmt = (
                update(Product)
                .where(Product.id == pid)
                .values(reserved_quantity=func.max(0, Product.reserved_quantity - qty))
            )
            await db.execute(stmt)

        logger.info("inventory_batch_released", items=product_quantities)

    async def commit_inventory_deduction(
        self,
        db: AsyncSession,
        product_quantities: Dict[str, int]
    ) -> None:
        """Permanently deduct inventory when a transaction is finalized as PAID."""
        for pid, qty in product_quantities.items():
            if qty <= 0:
                continue

            stmt = (
                update(Product)
                .where(Product.id == pid)
                .values(
                    inventory_quantity=func.max(0, Product.inventory_quantity - qty),
                    reserved_quantity=func.max(0, Product.reserved_quantity - qty)
                )
            )
            await db.execute(stmt)

        logger.info("inventory_deducted_on_payment", items=product_quantities)
