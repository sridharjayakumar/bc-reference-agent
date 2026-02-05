"""FastAPI dependencies for IMS authentication."""

import re
from typing import Any

from fastapi import Request

from app.services.ims_validator import IMSValidationError, ims_validator
from app.services.session import IMSSession, session_manager


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message)
        self.message = message


def detect_surface(request: Request) -> str:
    """
    Detect the surface (client type) from request headers.

    Priority:
    1. X-Adobe-Surface header (explicit)
    2. User-Agent parsing
    3. Referer header analysis
    4. Default to "unknown"
    """
    # Check explicit surface header
    surface_header = request.headers.get("X-Adobe-Surface")
    if surface_header:
        return surface_header.lower()

    # Parse User-Agent
    user_agent = request.headers.get("User-Agent", "").lower()
    if user_agent:
        if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent:
            return "mobile"
        if "tablet" in user_agent or "ipad" in user_agent:
            return "tablet"
        if any(browser in user_agent for browser in ["chrome", "firefox", "safari", "edge"]):
            return "web"

    # Check Referer for web surfaces
    referer = request.headers.get("Referer", "")
    if referer:
        if "mobile" in referer.lower():
            return "mobile"
        return "web"

    return "unknown"


def _extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    # Match "Bearer <token>" pattern
    match = re.match(r"Bearer\s+(.+)", auth_header, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_context_id(request: Request, body: dict[str, Any] | None = None) -> str | None:
    """Extract context ID from request body if available."""
    if body is None:
        return None

    params = body.get("params", {})
    config = params.get("configuration", {})
    return config.get("contextId")


async def require_ims_auth(request: Request) -> IMSSession:
    """
    FastAPI dependency that requires IMS authentication.

    Validates the Bearer token and returns an IMSSession with user context.

    Usage:
        @app.post("/a2a")
        async def handle_request(session: IMSSession = Depends(require_ims_auth)):
            ...

    Raises:
        AuthenticationError: If authentication fails
    """
    # Extract Bearer token
    token = _extract_bearer_token(request)
    if not token:
        raise AuthenticationError("Missing Authorization header")

    # Validate token with IMS
    try:
        user_info = await ims_validator.validate_token(token)
    except IMSValidationError as e:
        raise AuthenticationError(e.message) from e

    # Detect surface
    surface = detect_surface(request)

    # Create/get session for this user
    session = session_manager.create_session(user_info, surface)

    return session
