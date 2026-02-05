"""Brand Concierge Reference Agent implementation."""

from collections.abc import AsyncIterator

from app.core.config import settings


class BrandConciergeAgent:
    """
    Reference implementation of a Brand Concierge agent.

    This agent handles conversational interactions for brand experiences,
    including product recommendations, site navigation, and brand information.
    """

    def __init__(self) -> None:
        self.brand_name = settings.brand_name
        self.brand_tone = settings.brand_tone

    async def process_message(self, message: str, context_id: str | None = None) -> str:
        """
        Process an incoming message and generate a response.

        Args:
            message: The user's message text
            context_id: Optional context ID for conversation continuity

        Returns:
            The agent's response text
        """
        # Determine intent and route to appropriate skill
        intent = self._classify_intent(message)

        if intent == "product":
            return await self._handle_product_query(message)
        elif intent == "navigation":
            return await self._handle_navigation_query(message)
        else:
            return await self._handle_general_query(message)

    async def process_message_stream(
        self, message: str, context_id: str | None = None
    ) -> AsyncIterator[str]:
        """
        Process a message and stream the response.

        Args:
            message: The user's message text
            context_id: Optional context ID for conversation continuity

        Yields:
            Response text chunks
        """
        response = await self.process_message(message, context_id)
        # Simulate streaming by yielding words
        for word in response.split():
            yield word + " "

    def _classify_intent(self, message: str) -> str:
        """Classify the user's intent from their message."""
        message_lower = message.lower()

        product_keywords = ["product", "recommend", "buy", "price", "compare", "looking for"]
        navigation_keywords = ["find", "where", "navigate", "page", "link", "help me find"]

        if any(kw in message_lower for kw in product_keywords):
            return "product"
        elif any(kw in message_lower for kw in navigation_keywords):
            return "navigation"
        return "general"

    async def _handle_product_query(self, message: str) -> str:
        """Handle product-related queries."""
        return (
            f"I'd be happy to help you find the right product. "
            f"As your {self.brand_name} concierge, I can provide personalized recommendations. "
            f"Could you tell me more about what you're looking for?"
        )

    async def _handle_navigation_query(self, message: str) -> str:
        """Handle site navigation queries."""
        return (
            "I can help you navigate our site. "
            "Let me guide you to the right place. "
            "What specific information are you looking for?"
        )

    async def _handle_general_query(self, message: str) -> str:
        """Handle general brand-related queries."""
        return (
            f"Welcome to {self.brand_name}! "
            f"I'm here to assist you with any questions about our brand, "
            f"products, or services. How can I help you today?"
        )
