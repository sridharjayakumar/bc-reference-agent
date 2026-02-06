"""Tests for Shipping Agent logic."""

import shutil
from pathlib import Path

import pytest

from app.agents.sample_shipping_agent import ShippingAgent
from app.repositories.order_repository import OrderRepository

SOURCE_DB = Path("data/orders.db")


@pytest.fixture
def agent(tmp_path: Path) -> ShippingAgent:
    test_db = tmp_path / "test.db"
    shutil.copy(SOURCE_DB, test_db)
    agent = ShippingAgent()
    agent.order_repo = OrderRepository(db_path=test_db)
    return agent


@pytest.mark.asyncio
async def test_order_verification_with_valid_order(agent: ShippingAgent) -> None:
    """Test that providing a valid order ID and email verifies the order."""
    response = await agent.process_message(
        "Check order 3DV7KU4PK54 for cworshall0@flavors.me"
    )
    assert "order" in response.lower() or "delivery" in response.lower()


@pytest.mark.asyncio
async def test_order_verification_with_invalid_order(agent: ShippingAgent) -> None:
    """Test that an invalid order ID / email pair is rejected."""
    response = await agent.process_message(
        "Check order INVALIDORDER for nobody@example.com"
    )
    assert "couldn't find" in response.lower() or "not found" in response.lower()


@pytest.mark.asyncio
async def test_general_query(agent: ShippingAgent) -> None:
    """Test that general queries prompt for order info."""
    response = await agent.process_message("Hello!")
    assert "order" in response.lower() or "help" in response.lower()


@pytest.mark.asyncio
async def test_streaming_response(agent: ShippingAgent) -> None:
    """Test that streaming produces valid chunks."""
    chunks = []
    async for chunk in agent.process_message_stream("Hello"):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_response = "".join(chunks)
    assert len(full_response) > 0
