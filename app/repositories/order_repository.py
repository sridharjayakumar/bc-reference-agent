"""Order repository backed by SQLite."""

from pathlib import Path
from typing import Optional

import aiosqlite

from app.models.order import Order, OrderUpdate


class OrderRepository:
    """Repository for order data operations using SQLite."""

    def __init__(self, db_path: str | Path = "data/orders.db"):
        self.db_path = Path(db_path)

    async def find_by_order_id_and_email(
        self, order_id: str, email: str
    ) -> Optional[Order]:
        """Find order by order ID and email (case-insensitive)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders WHERE UPPER(order_id) = ? AND LOWER(email) = ?",
                (order_id.upper().strip(), email.lower().strip()),
            )
            row = await cursor.fetchone()

        if row:
            order = Order.from_row(dict(row))
            print(f"[OrderRepository] Found order {order_id} for {order.full_name()}")
            return order

        print(f"[OrderRepository] Order {order_id} not found for email {email}")
        return None

    async def update_order(
        self, order_id: str, email: str, updates: OrderUpdate
    ) -> tuple[bool, str]:
        """
        Update order with validation.

        Returns:
            tuple[bool, str]: (success, message)
        """
        update_dict = updates.to_dict()
        if not update_dict:
            return False, "No fields to update"

        set_clause = ", ".join(f"{k} = ?" for k in update_dict)
        values = list(update_dict.values())
        values.extend([order_id.upper().strip(), email.lower().strip()])

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"UPDATE orders SET {set_clause} "
                "WHERE UPPER(order_id) = ? AND LOWER(email) = ?",
                values,
            )
            await db.commit()

            if cursor.rowcount > 0:
                print(f"[OrderRepository] Updated order {order_id}: {update_dict}")
                return True, f"Successfully updated order {order_id}"

        return False, f"Order {order_id} not found for email {email}"

    async def get_all_orders(self) -> list[Order]:
        """Get all orders."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM orders ORDER BY id")
            rows = await cursor.fetchall()

        return [Order.from_row(dict(row)) for row in rows]

    async def get_order_count(self) -> int:
        """Get total number of orders."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM orders")
            (count,) = await cursor.fetchone()  # type: ignore[misc]

        return count
