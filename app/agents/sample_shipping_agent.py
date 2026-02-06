"""Sample Shipping Agent - demonstrates order tracking and shipping management."""

from collections.abc import AsyncIterator
import random
import re
from datetime import datetime, timedelta

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import settings
from app.models.order import OrderUpdate
from app.repositories.order_repository import OrderRepository


class ShippingAgent:
    """
    AI-powered shipping agent for order tracking and delivery management.

    Features:
    - Check delivery dates by order ID
    - Update delivery dates
    - Update shipping addresses
    - Email verification for security
    """

    def __init__(self) -> None:
        self.brand_name = settings.brand_name
        self.brand_tone = settings.brand_tone
        self.llm_model = settings.llm_model
        self.llm_enabled = settings.llm_enabled

        # Initialize Order Repository
        self.order_repo = OrderRepository(db_path=settings.db_path)

        # Initialize LLM client if enabled
        if self.llm_enabled:
            self.client = AsyncOpenAI(
                base_url=settings.llm_base_url,
                api_key="ollama",
            )
        else:
            self.client = None

        # Conversation history per context
        self._conversation_history: dict[str, list[ChatCompletionMessageParam]] = {}

        # Session state for tracking verification
        self._session_state: dict[str, dict] = {}

    async def _find_order(self, order_id: str, email: str) -> dict | None:
        """Find order by ID and verify with email."""
        order = await self.order_repo.find_by_order_id_and_email(order_id, email)
        if order:
            # Convert Order model to dict for backwards compatibility
            return {
                "order_id": order.order_id,
                "first_name": order.first_name,
                "last_name": order.last_name,
                "email": order.email,
                "street": order.street,
                "city": order.city,
                "state": order.state,
                "zipcode": order.zipcode,
                "delivery_date": order.delivery_date,
            }
        return None

    async def _update_order(self, order_id: str, email: str, updates: dict) -> bool:
        """Update order information after verification."""
        print(f"[_update_order] Called with order_id={order_id}, email={email}, updates={updates}")

        # Create OrderUpdate model from updates dict
        try:
            order_update = OrderUpdate(**updates)
        except Exception as e:
            print(f"[_update_order] Invalid update data: {e}")
            return False

        # Use repository to update
        success, message = await self.order_repo.update_order(order_id, email, order_update)
        print(f"[_update_order] Result: {message}")

        return success

    def _extract_order_info(self, message: str) -> dict:
        """Extract order ID and email from message using simple pattern matching."""

        # Look for order ID pattern (alphanumeric, typically with numbers and letters)
        order_pattern = r'\b([A-Z0-9]{10,15})\b'
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        order_match = re.search(order_pattern, message.upper())
        email_match = re.search(email_pattern, message)

        return {
            "order_id": order_match.group(1) if order_match else None,
            "email": email_match.group(0) if email_match else None
        }

    # Month name/abbreviation to number mapping
    _MONTH_MAP: dict[str, int] = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
        'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
        'may': 5, 'june': 6, 'jun': 6,
        'july': 7, 'jul': 7, 'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
        'december': 12, 'dec': 12,
    }

    @staticmethod
    def _next_future_date(month: int, day: int) -> datetime:
        """Return the next future occurrence of month/day, rolling the year forward if needed."""
        today = datetime.now()
        try:
            candidate = datetime(today.year, month, day)
        except ValueError:
            # Invalid day for the month (e.g. Feb 30) - fall back to last day
            # Try decreasing day until valid
            for d in range(day, 0, -1):
                try:
                    candidate = datetime(today.year, month, d)
                    break
                except ValueError:
                    continue
            else:
                return today + timedelta(days=1)
        if candidate.date() <= today.date():
            # Date has passed this year, roll to next year
            try:
                candidate = datetime(today.year + 1, month, day)
            except ValueError:
                for d in range(day, 0, -1):
                    try:
                        candidate = datetime(today.year + 1, month, d)
                        break
                    except ValueError:
                        continue
        return candidate

    def _extract_new_date(self, message: str, current_delivery_date: str | None = None) -> str | None:
        """Extract new delivery date from message, including relative expressions.

        Supports:
        - Explicit full dates: MM/DD/YYYY, MM-DD-YYYY, Month DD YYYY
        - Partial dates (smart year/month inference):
          - Month + day without year: "March 3rd", "Jan 15", "3/15"
          - Day only: "the 3rd", "the 15th"
        - Relative: tomorrow, next <weekday>, next week, this weekend,
          next weekend, sooner/earlier
        """
        # 1. Try explicit full-date patterns first
        explicit_patterns = [
            r'\b(\d{1,2}/\d{1,2}/\d{4})\b',       # 8/8/2028, 08/08/2028
            r'\b(\d{1,2}-\d{1,2}-\d{4})\b',        # 8-8-2028
            r'\b([A-Za-z]+ \d{1,2},? \d{4})\b',    # August 8, 2028
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)

        today = datetime.now()
        msg = message.lower()

        # 2. Try partial dates (month + day, no year)
        month_names = '|'.join(self._MONTH_MAP.keys())

        # "March 3rd", "Jan 15", "January 15th", "feb 2nd"
        match = re.search(
            rf'\b({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b', msg
        )
        if match:
            month = self._MONTH_MAP[match.group(1)]
            day = int(match.group(2))
            target = self._next_future_date(month, day)
            return f"{target.month}/{target.day}/{target.year}"

        # "3/15" or "03/15" (M/D without year - must NOT have a trailing /digit for YYYY)
        match = re.search(r'\b(\d{1,2})/(\d{1,2})\b(?!/\d)', msg)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                target = self._next_future_date(month, day)
                return f"{target.month}/{target.day}/{target.year}"

        # 3. Try day-only: "the 3rd", "the 15th", "on the 3rd", "3rd"
        match = re.search(r'(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b', msg)
        if match:
            day = int(match.group(1))
            if 1 <= day <= 31:
                # If day has passed in current month, assume next month
                month = today.month
                year = today.year
                if day <= today.day:
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
                try:
                    target = datetime(year, month, day)
                except ValueError:
                    # Invalid day for that month, skip to month after
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
                    try:
                        target = datetime(year, month, day)
                    except ValueError:
                        target = None
                if target:
                    return f"{target.month}/{target.day}/{target.year}"

        # 4. Try relative date expressions
        target = None

        if 'tomorrow' in msg:
            target = today + timedelta(days=1)

        elif 'next weekend' in msg:
            # Saturday of the week after the upcoming weekend
            days_to_saturday = (5 - today.weekday()) % 7
            if days_to_saturday == 0:
                days_to_saturday = 7
            target = today + timedelta(days=days_to_saturday + 7)

        elif re.search(r'(?:this\s+)?weekend', msg):
            # The coming Saturday (or today if already Saturday)
            days_to_saturday = (5 - today.weekday()) % 7
            if days_to_saturday == 0 and today.weekday() != 5:
                # It's Sunday, roll to next Saturday
                days_to_saturday = 6
            target = today + timedelta(days=days_to_saturday)

        elif 'next week' in msg:
            # Random weekday (Mon-Fri) of next calendar week
            days_to_next_monday = (7 - today.weekday()) % 7
            if days_to_next_monday == 0:
                days_to_next_monday = 7
            next_monday = today + timedelta(days=days_to_next_monday)
            target = next_monday + timedelta(days=random.randint(0, 4))

        elif match := re.search(
            r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', msg
        ):
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday',
                         'friday', 'saturday', 'sunday']
            target_weekday = day_names.index(match.group(1))
            days_ahead = (target_weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target = today + timedelta(days=days_ahead)

        elif 'sooner' in msg or 'earlier' in msg:
            # Random date between tomorrow and current delivery date
            if current_delivery_date:
                try:
                    parts = current_delivery_date.split('/')
                    delivery_dt = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
                    tomorrow = today + timedelta(days=1)
                    if delivery_dt > tomorrow:
                        delta = (delivery_dt - tomorrow).days
                        target = tomorrow + timedelta(days=random.randint(0, delta - 1) if delta > 1 else 0)
                    else:
                        target = tomorrow
                except (ValueError, IndexError):
                    target = today + timedelta(days=1)
            else:
                target = today + timedelta(days=1)

        if target:
            return f"{target.month}/{target.day}/{target.year}"

        return None

    def _extract_new_address(self, message: str) -> dict | None:
        """Extract new address components from message."""

        # Look for address patterns in the message
        # Common format: "Street Address, City, State ZIP"
        # Example: "123 Main Street, Los Angeles, California 90210"

        # Pattern for addresses with number at start: "123 Main Street, City, State ZIP"
        # Supports both "City, State ZIP" and "City State ZIP" (comma between city/state is optional)
        pattern_numeric = r'(\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd|Way|Place|Pl)?)\s*,\s*([A-Za-z\s]+?)(?:\s*,\s*|\s+)([A-Za-z]{2,})\s+(\d{5})'

        # Try numeric address pattern first
        match = re.search(pattern_numeric, message, re.IGNORECASE)
        if match:
            return {
                "street": match.group(1).strip().title(),
                "city": match.group(2).strip().title(),
                "state": match.group(3).strip().title(),
                "zipcode": match.group(4).strip()
            }

        return None

    def _is_confirmation(self, message: str) -> bool:
        """Check if message contains confirmation keywords."""
        message_lower = message.lower().strip()

        # Explicit confirmation keywords (short and clear)
        confirmation_keywords = [
            'yes', 'confirm', 'proceed', 'go ahead', 'correct'
        ]

        return any(keyword == message_lower or keyword in message_lower for keyword in confirmation_keywords)

    def _is_cancellation(self, message: str) -> bool:
        """Check if message contains cancellation keywords."""
        message_lower = message.lower().strip()

        cancellation_keywords = [
            'no', 'cancel', 'nevermind', 'never mind', 'don\'t', 'dont'
        ]

        return any(keyword == message_lower or keyword in message_lower for keyword in cancellation_keywords)

    def _build_context(self, context_id: str) -> str:
        """Build context about verified orders in this session."""
        state = self._session_state.get(context_id, {})
        if state.get("verified_order"):
            order = state["verified_order"]
            return f"\n\nVerified Order Context:\n- Order ID: {order['order_id']}\n- Customer: {order['first_name']} {order['last_name']}\n- Email: {order['email']}\n- Delivery Date: {order['delivery_date']}\n- Address: {order['street']}, {order['city']}, {order['state']} {order['zipcode']}"
        return ""

    async def process_message(self, message: str, context_id: str | None = None) -> str:
        """
        Process an incoming message and generate a response.

        Args:
            message: The user's message text
            context_id: Optional context ID for conversation continuity

        Returns:
            The agent's response text
        """
        if not self.llm_enabled:
            return await self._fallback_response(message, context_id)

        # Extract order info from message
        extracted = self._extract_order_info(message)

        # Check if user is trying to verify an order
        if extracted["order_id"] and extracted["email"]:
            order = await self._find_order(extracted["order_id"], extracted["email"])
            if order:
                # Store verified order in session
                if context_id:
                    self._session_state[context_id] = {"verified_order": order}

                # Return a programmatic greeting with real data — don't rely
                # on the LLM to copy values from context (small models hallucinate).
                return (
                    f"Hi {order['first_name']}! Your order {order['order_id']} "
                    f"is scheduled for delivery on {order['delivery_date']}. "
                    f"How can I help you today?"
                )
            else:
                context_info = "\n\nOrder not found or email doesn't match."
        else:
            context_info = self._build_context(context_id) if context_id else ""

        # Check if user has a verified order and wants to make updates
        update_result = None
        if context_id and context_id in self._session_state:
            state = self._session_state[context_id]
            verified_order = state.get("verified_order")

            if verified_order:
                # Check for date update request
                new_date = self._extract_new_date(message, verified_order.get("delivery_date"))
                is_confirming = self._is_confirmation(message)
                is_cancelling = self._is_cancellation(message)

                # Debug logging
                print(f"\n[UPDATE DEBUG] ===== NEW MESSAGE =====")
                print(f"[UPDATE DEBUG] Full message: {message}")
                print(f"[UPDATE DEBUG] new_date extracted: {new_date}")
                print(f"[UPDATE DEBUG] is_confirming: {is_confirming}")
                print(f"[UPDATE DEBUG] is_cancelling: {is_cancelling}")
                print(f"[UPDATE DEBUG] pending_date_update in state: {'pending_date_update' in state}")
                if "pending_date_update" in state:
                    print(f"[UPDATE DEBUG] pending_date_update value: {state['pending_date_update']}")
                print(f"[UPDATE DEBUG] context_id: {context_id}")

                # Handle cancellation
                if is_cancelling and ("pending_date_update" in state or "pending_address_update" in state):
                    state.pop("pending_date_update", None)
                    state.pop("pending_address_update", None)
                    context_info += "\n\nCANCELLED: User cancelled the pending change."

                # Determine the date to use (current message or pending)
                date_to_update = None
                if new_date:
                    # User provided new date - store as pending, don't auto-update
                    state["pending_date_update"] = new_date
                    print(f"[UPDATE DEBUG] Storing pending date: {new_date}")
                    # Add marker for LLM to show confirmation
                    context_info += f"\n\nPENDING_DATE_CHANGE: {new_date}"
                elif is_confirming and "pending_date_update" in state:
                    # User explicitly confirmed the pending change
                    date_to_update = state["pending_date_update"]
                    print(f"[UPDATE DEBUG] User confirmed pending date: {date_to_update}")

                print(f"[UPDATE DEBUG] date_to_update: {date_to_update}")

                # Perform the update if we have a date to update
                if date_to_update:
                    print(f"[UPDATE DEBUG] Calling _update_order for {verified_order['order_id']}")
                    success = await self._update_order(
                        verified_order["order_id"],
                        verified_order["email"],
                        {"delivery_date": date_to_update}
                    )
                    print(f"[UPDATE DEBUG] Update success: {success}")
                    if success:
                        # Update session with new date
                        verified_order["delivery_date"] = date_to_update
                        state["verified_order"] = verified_order
                        # Clear pending update
                        state.pop("pending_date_update", None)
                        update_result = f"\n\nSYSTEM: Delivery date successfully updated to {date_to_update} in database."
                    else:
                        update_result = "\n\nSYSTEM: Failed to update delivery date in database."

                # Check for address update request
                new_address = self._extract_new_address(message)

                print(f"[ADDRESS DEBUG] new_address extracted: {new_address}")

                # Determine the address to use (current message or pending)
                address_to_update = None
                if new_address:
                    # User provided new address - store as pending, don't auto-update
                    state["pending_address_update"] = new_address
                    print(f"[ADDRESS DEBUG] Storing pending address: {new_address}")
                    # Add marker for LLM to show confirmation
                    addr_str = f"{new_address['street']}, {new_address['city']}, {new_address['state']} {new_address['zipcode']}"
                    context_info += f"\n\nPENDING_ADDRESS_CHANGE: {addr_str}"
                elif is_confirming and "pending_address_update" in state:
                    # User explicitly confirmed the pending change
                    address_to_update = state["pending_address_update"]
                    print(f"[ADDRESS DEBUG] User confirmed pending address: {address_to_update}")

                print(f"[ADDRESS DEBUG] address_to_update: {address_to_update}")

                # Perform the update if we have an address to update
                if address_to_update:
                    print(f"[ADDRESS DEBUG] Calling _update_order for address change")
                    success = await self._update_order(
                        verified_order["order_id"],
                        verified_order["email"],
                        address_to_update
                    )
                    print(f"[ADDRESS DEBUG] Update success: {success}")
                    if success:
                        # Update session with new address
                        verified_order.update(address_to_update)
                        state["verified_order"] = verified_order
                        # Clear pending update
                        state.pop("pending_address_update", None)
                        addr_summary = f"{address_to_update['street']}, {address_to_update['city']}, {address_to_update['state']} {address_to_update['zipcode']}"
                        update_result = f"\n\nSYSTEM: Address successfully updated to {addr_summary} in database."
                    else:
                        update_result = "\n\nSYSTEM: Failed to update address in database."

        # Add update result to context if any
        if update_result:
            context_info += update_result

        # Build system prompt
        system_prompt = self._get_system_prompt() + context_info

        # Build conversation messages
        messages = self._build_conversation_messages(system_prompt, message, context_id)

        # Generate AI response
        try:
            response = await self._generate_llm_response(messages)

            # Store in conversation history
            if context_id:
                self._add_to_history(context_id, "user", message)
                self._add_to_history(context_id, "assistant", response)

            return response

        except Exception as e:
            error_msg = str(e)
            print(f"\n{'='*60}")
            print(f"LLM Error: {error_msg}")

            if "not found" in error_msg.lower() and "model" in error_msg.lower():
                print(f"\nAI Model Not Found!")
                print(f"   The model '{self.llm_model}' hasn't been downloaded yet.")
                print(f"\n   To fix this, restart the containers:")
                print(f"   ./run.sh down && ./run.sh dev")
                print(f"\n   The model will be automatically downloaded on startup (~1.9GB).")
                print(f"   This is a one-time download that takes 2-5 minutes.")

            print(f"\n   Using fallback keyword-based responses for now...")
            print(f"{'='*60}\n")

            return await self._fallback_response(message, context_id)

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
        if not self.llm_enabled or not self.client:
            response = await self._fallback_response(message, context_id)
            for word in response.split():
                yield word + " "
            return

        # Extract and verify order info
        extracted = self._extract_order_info(message)
        if extracted["order_id"] and extracted["email"]:
            order = await self._find_order(extracted["order_id"], extracted["email"])
            if order and context_id:
                self._session_state[context_id] = {"verified_order": order}

        context_info = self._build_context(context_id) if context_id else ""
        system_prompt = self._get_system_prompt() + context_info
        messages = self._build_conversation_messages(system_prompt, message, context_id)

        try:
            stream = await self.client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                stream=True,
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

            # Store complete response in history
            if context_id:
                self._add_to_history(context_id, "user", message)
                self._add_to_history(context_id, "assistant", full_response)

        except Exception as e:
            print(f"LLM streaming error: {e}")
            response = await self._fallback_response(message, context_id)
            for word in response.split():
                yield word + " "

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the shipping agent."""
        return f"""You are a helpful shipping assistant for {self.brand_name}.
Your tone should be {self.brand_tone}.
Keep responses concise (2-3 sentences) and actionable.
Do not use emojis in your responses.

You help customers with:
- Checking delivery dates for their orders
- Updating delivery dates
- Updating shipping addresses
- Answering questions about their shipments

IMPORTANT SECURITY:
- Always require both Order ID AND email address for verification
- If the user hasn't provided both, politely ask for the missing information
- Never share full details until verification is complete

CRITICAL - Responding to Order Verification:
- If you see a "Verified Order Context" section, the order is ALREADY VERIFIED
- DO NOT say "I'm verifying", "Please wait", "I'm checking", or "Let me look that up"
- Read the Verified Order Context and use the real values directly in your response
- Your response MUST include the actual Customer name, Order ID, and Delivery Date from the context
- Do NOT use any placeholder text in brackets - only use real data from the context
- If verified order info is not in the context, ask for Order ID and email

CRITICAL - Handling Update Requests:
- If user asks to change/update something but DOES NOT provide the new date/address:
  * Ask them: "What date would you like to change it to?" or "What is your new address?"
  * DO NOT invent or suggest dates
  * WAIT for them to provide the specific information
- When you see "PENDING_DATE_CHANGE:" followed by a date in the context:
  * Use the exact date shown after "PENDING_DATE_CHANGE:" in your response
  * Respond ONLY: "Your delivery date will be changed to <the date> for order <order_id>."
  * DO NOT mention confirmation, buttons, or next steps
  * Just state what will change, nothing more
- When you see "PENDING_ADDRESS_CHANGE:" followed by an address in the context:
  * Use the exact address shown after "PENDING_ADDRESS_CHANGE:" in your response
  * Respond ONLY: "Your shipping address will be changed to <the address> for order <order_id>."
  * DO NOT mention confirmation, buttons, or next steps
- When you see "SYSTEM:" followed by "successfully updated in database":
  * Respond ONLY: "Your delivery date has been updated successfully." or "Your shipping address has been updated successfully." depending on what was updated
  * Do NOT repeat the date or address unless it appears in the SYSTEM message
- When you see "CANCELLED: User cancelled the pending change":
  * Respond: "Okay, I've cancelled that change."
- NEVER invent dates or addresses - only use what the user provides
- NEVER claim an update is complete unless you see the SYSTEM confirmation message
- NEVER mention "Confirm" or "Cancel" buttons - they appear automatically

When you don't have specific order information yet, guide the user to provide their Order ID and email address for verification."""

    def _build_conversation_messages(
        self, system_prompt: str, user_message: str, context_id: str | None
    ) -> list[ChatCompletionMessageParam]:
        """Build the conversation messages for the LLM."""
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation history if available (keep last 10 messages for context)
        if context_id and context_id in self._conversation_history:
            history = self._conversation_history[context_id][-10:]
            messages.extend(history)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    async def _generate_llm_response(
        self, messages: list[ChatCompletionMessageParam]
    ) -> str:
        """Generate response using the LLM."""
        if not self.client:
            return await self._fallback_response(messages[-1]["content"])  # type: ignore

        response = await self.client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )

        return response.choices[0].message.content or "I'm having trouble responding right now."

    def _add_to_history(self, context_id: str, role: str, content: str) -> None:
        """Add a message to conversation history."""
        if context_id not in self._conversation_history:
            self._conversation_history[context_id] = []

        self._conversation_history[context_id].append(
            {"role": role, "content": content}  # type: ignore
        )

    async def _fallback_response(self, message: str, context_id: str | None = None) -> str:
        """
        Fallback response when LLM is disabled or errors occur.
        """
        message_lower = message.lower()
        extracted = self._extract_order_info(message)

        # Check if they're providing order info
        if extracted["order_id"] and extracted["email"]:
            order = await self._find_order(extracted["order_id"], extracted["email"])
            if order:
                if context_id:
                    self._session_state[context_id] = {"verified_order": order}
                return (
                    f"Order {order['order_id']} verified! "
                    f"Your delivery to {order['city']}, {order['state']} is scheduled for {order['delivery_date']}. "
                    f"How can I help you with this order?"
                )
            else:
                return (
                    "I couldn't find that order with the provided email address. "
                    "Please double-check your Order ID and email, then try again."
                )

        # Check if they have a verified order
        if context_id and context_id in self._session_state:
            state = self._session_state[context_id]
            if "verified_order" in state:
                order = state["verified_order"]
                if "date" in message_lower or "when" in message_lower or "delivery" in message_lower:
                    return f"Your order {order['order_id']} is scheduled for delivery on {order['delivery_date']}."
                elif "address" in message_lower or "where" in message_lower:
                    return f"Your order will be delivered to {order['street']}, {order['city']}, {order['state']} {order['zipcode']}."

        # Default response - ask for order info
        return (
            f"I'm here to help with your {self.brand_name} shipping questions! "
            "To check your order status or make changes, please provide your Order ID and email address."
        )
