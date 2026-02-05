"""Session management for authenticated users."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.ims_validator import IMSUserInfo


@dataclass
class IMSSession:
    """Represents an authenticated user session."""

    context_id: str
    user_info: IMSUserInfo
    surface: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        """Get the user ID from the session."""
        return self.user_info.user_id

    @property
    def expires_at(self) -> datetime:
        """Get the session expiry time (from IMS token)."""
        return self.user_info.expires_at

    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.now(UTC) > self.expires_at


class SessionManager:
    """
    Manages user sessions associated with IMS tokens.

    Sessions are keyed by context_id and contain user information
    derived from validated IMS tokens.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, IMSSession] = {}
        # Maps user_id -> list of context_ids for session lookup
        self._user_sessions: dict[str, list[str]] = {}

    def create_session(
        self,
        user_info: IMSUserInfo,
        surface: str,
        context_id: str | None = None,
    ) -> IMSSession:
        """
        Create a new session or return existing one for the context.

        Args:
            user_info: Validated IMS user information
            surface: Detected surface (web, mobile, etc.)
            context_id: Optional existing context ID

        Returns:
            IMSSession for the user
        """
        # If context_id provided, check for existing session
        if context_id and context_id in self._sessions:
            existing = self._sessions[context_id]
            # Verify the session belongs to the same user
            if existing.user_id == user_info.user_id and not existing.is_expired():
                # Update user_info in case token was refreshed
                existing.user_info = user_info
                return existing

        # Generate new context_id if not provided or invalid
        if not context_id:
            context_id = str(uuid.uuid4())

        session = IMSSession(
            context_id=context_id,
            user_info=user_info,
            surface=surface,
        )

        self._sessions[context_id] = session

        # Track sessions by user
        if user_info.user_id not in self._user_sessions:
            self._user_sessions[user_info.user_id] = []
        if context_id not in self._user_sessions[user_info.user_id]:
            self._user_sessions[user_info.user_id].append(context_id)

        return session

    def get_session(self, context_id: str) -> IMSSession | None:
        """
        Retrieve a session by context ID.

        Args:
            context_id: The context ID to look up

        Returns:
            IMSSession if found and not expired, None otherwise
        """
        session = self._sessions.get(context_id)
        if session and session.is_expired():
            self._remove_session(context_id)
            return None
        return session

    def get_user_sessions(self, user_id: str) -> list[IMSSession]:
        """Get all active sessions for a user."""
        context_ids = self._user_sessions.get(user_id, [])
        sessions = []
        for context_id in context_ids:
            session = self.get_session(context_id)
            if session:
                sessions.append(session)
        return sessions

    def _remove_session(self, context_id: str) -> None:
        """Remove a session and clean up references."""
        session = self._sessions.pop(context_id, None)
        if session:
            user_contexts = self._user_sessions.get(session.user_id, [])
            if context_id in user_contexts:
                user_contexts.remove(context_id)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count of removed sessions."""
        expired = [ctx_id for ctx_id, session in self._sessions.items() if session.is_expired()]
        for ctx_id in expired:
            self._remove_session(ctx_id)
        return len(expired)


# Global session manager instance
session_manager = SessionManager()
