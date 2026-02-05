"""Tests for Brand Concierge agent logic."""

import pytest

from app.agents.concierge import BrandConciergeAgent


@pytest.fixture
def agent() -> BrandConciergeAgent:
    return BrandConciergeAgent()


@pytest.mark.asyncio
async def test_product_intent_classification(agent: BrandConciergeAgent) -> None:
    """Test that product-related queries are classified correctly."""
    response = await agent.process_message("I'm looking for a laptop to buy")
    assert "product" in response.lower() or "recommend" in response.lower()


@pytest.mark.asyncio
async def test_navigation_intent_classification(agent: BrandConciergeAgent) -> None:
    """Test that navigation queries are handled appropriately."""
    response = await agent.process_message("Where can I find the return policy?")
    assert "navigate" in response.lower() or "guide" in response.lower()


@pytest.mark.asyncio
async def test_general_query(agent: BrandConciergeAgent) -> None:
    """Test that general queries receive a brand welcome."""
    response = await agent.process_message("Hello!")
    assert "welcome" in response.lower() or "help" in response.lower()


@pytest.mark.asyncio
async def test_streaming_response(agent: BrandConciergeAgent) -> None:
    """Test that streaming produces valid chunks."""
    chunks = []
    async for chunk in agent.process_message_stream("Hello"):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_response = "".join(chunks)
    assert len(full_response) > 0
