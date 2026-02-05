"""A2A request handler for Brand Concierge."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.concierge import BrandConciergeAgent


class A2AHandler:
    """
    Handles A2A protocol requests and manages task lifecycle.

    This handler processes JSON-RPC requests according to the A2A specification,
    managing tasks through their lifecycle states: working, completed, failed,
    canceled, rejected, input_required, auth_required.
    """

    def __init__(self) -> None:
        self.agent = BrandConciergeAgent()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._contexts: dict[str, list[str]] = {}  # context_id -> list of task_ids

    async def send_message(
        self,
        message: dict[str, Any],
        context_id: str | None = None,
        task_id: str | None = None,
        user_id: str | None = None,
        surface: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a SendMessage request.

        Args:
            message: The A2A Message object containing parts
            context_id: Optional context ID for conversation continuity
            task_id: Optional task ID (if continuing existing task)
            user_id: Optional authenticated user ID
            surface: Optional surface/client type (web, mobile, etc.)

        Returns:
            A2A Task object with response
        """
        # Generate IDs if not provided
        context_id = context_id or str(uuid.uuid4())
        task_id = task_id or str(uuid.uuid4())

        # Extract text from message parts
        user_text = self._extract_text_from_message(message)

        # Create task in working state
        now = datetime.now(UTC).isoformat()
        task: dict[str, Any] = {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "working"},
            "createdAt": now,
            "updatedAt": now,
            "messages": [message],
            "artifacts": [],
        }

        # Add metadata with user context if available
        if user_id or surface:
            task["metadata"] = {}
            if user_id:
                task["metadata"]["userId"] = user_id
            if surface:
                task["metadata"]["surface"] = surface

        # Store task
        self._tasks[task_id] = task
        if context_id not in self._contexts:
            self._contexts[context_id] = []
        self._contexts[context_id].append(task_id)

        # Process with agent
        try:
            response_text = await self.agent.process_message(user_text, context_id)

            # Create response message
            response_message = {
                "role": "agent",
                "parts": [{"kind": "text", "text": response_text}],
            }

            # Update task to completed
            task["messages"].append(response_message)
            task["status"] = {"state": "completed"}
            task["updatedAt"] = datetime.now(UTC).isoformat()

        except Exception as e:
            task["status"] = {
                "state": "failed",
                "error": {"code": "PROCESSING_ERROR", "message": str(e)},
            }
            task["updatedAt"] = datetime.now(UTC).isoformat()

        return task

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    async def list_tasks(self, context_id: str | None = None) -> list[dict[str, Any]]:
        """List tasks, optionally filtered by context."""
        if context_id:
            task_ids = self._contexts.get(context_id, [])
            return [self._tasks[tid] for tid in task_ids if tid in self._tasks]
        return list(self._tasks.values())

    async def cancel_task(self, task_id: str) -> dict[str, Any] | None:
        """Cancel a task if it's in a cancellable state."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        state = task["status"]["state"]
        if state in ("completed", "failed", "canceled", "rejected"):
            return task  # Already in terminal state

        task["status"] = {"state": "canceled"}
        task["updatedAt"] = datetime.now(UTC).isoformat()
        return task

    def _extract_text_from_message(self, message: dict[str, Any]) -> str:
        """Extract text content from an A2A message."""
        parts = message.get("parts", [])
        text_parts = []
        for part in parts:
            if part.get("kind") == "text":
                text_parts.append(part.get("text", ""))
        return " ".join(text_parts)
