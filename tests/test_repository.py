"""Tests for OrderRepository with SQLite backend."""

import shutil
from pathlib import Path

import aiosqlite
import pytest

from app.models.order import OrderUpdate
from app.repositories.order_repository import OrderRepository

SOURCE_DB = Path("data/orders.db")


@pytest.fixture
def repo(tmp_path: Path) -> OrderRepository:
    """Create a repository backed by a copy of the real DB."""
    test_db = tmp_path / "test.db"
    shutil.copy(SOURCE_DB, test_db)
    return OrderRepository(db_path=test_db)


@pytest.fixture
async def empty_repo(tmp_path: Path) -> OrderRepository:
    """Create a repository with an empty orders table."""
    db_path = tmp_path / "empty.db"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE orders ("
            "id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, "
            "email TEXT, order_id TEXT, street TEXT, city TEXT, "
            "state TEXT, zipcode TEXT, delivery_date TEXT)"
        )
        await db.commit()
    return OrderRepository(db_path=db_path)


# --- find_by_order_id_and_email ---


@pytest.mark.asyncio
async def test_find_order_found(repo: OrderRepository) -> None:
    order = await repo.find_by_order_id_and_email("3DV7KU4PK54", "cworshall0@flavors.me")
    assert order is not None
    assert order.order_id == "3DV7KU4PK54"
    assert order.first_name == "Cassandry"


@pytest.mark.asyncio
async def test_find_order_not_found(repo: OrderRepository) -> None:
    order = await repo.find_by_order_id_and_email("DOESNOTEXIST", "nobody@example.com")
    assert order is None


@pytest.mark.asyncio
async def test_find_order_case_insensitive(repo: OrderRepository) -> None:
    order = await repo.find_by_order_id_and_email("3dv7ku4pk54", "CWORSHALL0@FLAVORS.ME")
    assert order is not None
    assert order.order_id == "3DV7KU4PK54"


# --- update_order ---


@pytest.mark.asyncio
async def test_update_order_success(repo: OrderRepository) -> None:
    updates = OrderUpdate(delivery_date="1/1/2030")
    success, msg = await repo.update_order("3DV7KU4PK54", "cworshall0@flavors.me", updates)
    assert success is True
    assert "Successfully" in msg

    # Verify the update persisted
    order = await repo.find_by_order_id_and_email("3DV7KU4PK54", "cworshall0@flavors.me")
    assert order is not None
    assert order.delivery_date == "1/1/2030"


@pytest.mark.asyncio
async def test_update_order_not_found(repo: OrderRepository) -> None:
    updates = OrderUpdate(delivery_date="1/1/2030")
    success, msg = await repo.update_order("DOESNOTEXIST", "nobody@example.com", updates)
    assert success is False
    assert "not found" in msg


# --- get_all_orders ---


@pytest.mark.asyncio
async def test_get_all_orders(repo: OrderRepository) -> None:
    orders = await repo.get_all_orders()
    assert len(orders) == 20


@pytest.mark.asyncio
async def test_get_all_orders_empty(empty_repo: OrderRepository) -> None:
    orders = await empty_repo.get_all_orders()
    assert orders == []


# --- get_order_count ---


@pytest.mark.asyncio
async def test_get_order_count(repo: OrderRepository) -> None:
    count = await repo.get_order_count()
    assert count == 20


@pytest.mark.asyncio
async def test_get_order_count_empty(empty_repo: OrderRepository) -> None:
    count = await empty_repo.get_order_count()
    assert count == 0
