"""Unit tests for Phase 5 atomic inventory reservation & concurrency manager."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import Product, Merchant
from services.execution.concurrency import InventoryReservationManager


@pytest.fixture
def reservation_mgr():
    return InventoryReservationManager()


@pytest.fixture
async def seed_product_with_stock_one(db_session: AsyncSession):
    """Seed a product with exactly 1 available stock unit."""
    merchant = Merchant(
        id="merch_test_race",
        name="Race Test Merchant",
        currency="INR"
    )
    db_session.add(merchant)

    product = Product(
        id="prod_scarce_01",
        merchant_id="merch_test_race",
        sku="SKU-SCARCE-01",
        name="Scarce Item",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        inventory_quantity=1,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add(product)
    await db_session.commit()
    return product


@pytest.mark.asyncio
async def test_atomic_reservation_race_stock_one(db_session: AsyncSession, reservation_mgr, seed_product_with_stock_one):
    """When two executions race for stock = 1, exactly one succeeds and the second fails."""
    pid = seed_product_with_stock_one.id

    # Request A attempts to reserve 1 unit
    res_a = await reservation_mgr.reserve_inventory(db_session, {pid: 1})
    assert res_a is True

    # Request B immediately attempts to reserve 1 unit on the same product
    res_b = await reservation_mgr.reserve_inventory(db_session, {pid: 1})
    assert res_b is False  # Must fail atomically!


@pytest.mark.asyncio
async def test_release_inventory_restores_availability(db_session: AsyncSession, reservation_mgr, seed_product_with_stock_one):
    """Releasing reserved inventory restores availability for subsequent requests."""
    pid = seed_product_with_stock_one.id

    # Reserve 1 unit
    res_a = await reservation_mgr.reserve_inventory(db_session, {pid: 1})
    assert res_a is True

    # Release 1 unit
    await reservation_mgr.release_inventory(db_session, {pid: 1})

    # Now request B can successfully reserve
    res_b = await reservation_mgr.reserve_inventory(db_session, {pid: 1})
    assert res_b is True


@pytest.mark.asyncio
async def test_commit_inventory_deduction_on_payment(db_session: AsyncSession, reservation_mgr, seed_product_with_stock_one):
    """Finalizing payment deducts both physical inventory and reserved quantity."""
    pid = seed_product_with_stock_one.id

    # Reserve 1 unit
    await reservation_mgr.reserve_inventory(db_session, {pid: 1})

    # Finalize / deduct
    await reservation_mgr.commit_inventory_deduction(db_session, {pid: 1})

    await db_session.refresh(seed_product_with_stock_one)
    assert seed_product_with_stock_one.inventory_quantity == 0
    assert seed_product_with_stock_one.reserved_quantity == 0
