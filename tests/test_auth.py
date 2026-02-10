"""Tests for IMS authentication."""

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.ims_validator import IMSUserInfo


class TestAuthRequired:
    """Tests for authentication requirement."""

    def test_a2a_requires_auth_header(self, unauthenticated_client: TestClient) -> None:
        """Test that /a2a endpoint returns 401 without Authorization header."""
        response = unauthenticated_client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tasks/list",
                "params": {},
            },
        )
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="Adobe IMS"'

    def test_a2a_invalid_token_returns_401(self, unauthenticated_client: TestClient) -> None:
        """Test that /a2a endpoint returns 401 with invalid token."""
        with patch(
            "app.auth.dependencies.ims_validator.validate_token",
            new_callable=AsyncMock,
        ) as mock_validate:
            from app.services.ims_validator import IMSValidationError

            mock_validate.side_effect = IMSValidationError("Invalid token")

            response = unauthenticated_client.post(
                "/a2a",
                headers={"Authorization": "Bearer invalid_token"},
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "tasks/list",
                    "params": {},
                },
            )
            assert response.status_code == 401

    def test_agent_card_no_auth_required(self, unauthenticated_client: TestClient) -> None:
        """Test that /.well-known/agent.json works without authentication."""
        response = unauthenticated_client.get("/.well-known/agent.json")
        assert response.status_code == 200

        card = response.json()
        assert card["name"] == "Sample Shipping Agent"
        assert "securitySchemes" in card
        assert "imsBearer" in card["securitySchemes"]


class TestAuthenticatedRequests:
    """Tests for authenticated requests."""

    def test_message_send_with_valid_auth(
        self, client: TestClient, mock_ims_user: IMSUserInfo
    ) -> None:
        """Test message/send with valid authentication."""
        response = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": "Hello"}],
                    }
                },
            },
        )
        assert response.status_code == 200

        result = response.json()
        assert "result" in result
        task = result["result"]

        # Verify task has context and metadata
        assert "contextId" in task
        assert "metadata" in task
        assert task["metadata"]["userId"] == mock_ims_user.user_id

    def test_message_send_includes_surface(self, unauthenticated_client: TestClient) -> None:
        """Test that surface is detected and included in task metadata."""
        from datetime import datetime, timedelta

        mock_user = IMSUserInfo(
            user_id="test-user",
            email="test@example.com",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        with patch(
            "app.auth.dependencies.ims_validator.validate_token",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_user

            # Test with explicit surface header
            response = unauthenticated_client.post(
                "/a2a",
                headers={
                    "Authorization": "Bearer valid_token",
                    "X-Adobe-Surface": "mobile-app",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "parts": [{"kind": "text", "text": "Hello"}],
                        }
                    },
                },
            )
            assert response.status_code == 200

            task = response.json()["result"]
            assert task["metadata"]["surface"] == "mobile-app"


class TestSurfaceDetection:
    """Tests for surface detection from headers."""

    def test_detect_surface_from_explicit_header(self) -> None:
        """Test surface detection from X-Adobe-Surface header."""
        from app.auth.dependencies import detect_surface

        request = MagicMock()
        request.headers = {"X-Adobe-Surface": "web-app"}

        surface = detect_surface(request)
        assert surface == "web-app"

    def test_detect_surface_from_user_agent_mobile(self) -> None:
        """Test surface detection from mobile User-Agent."""
        from app.auth.dependencies import detect_surface

        request = MagicMock()
        request.headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"}

        surface = detect_surface(request)
        assert surface == "mobile"

    def test_detect_surface_from_user_agent_web(self) -> None:
        """Test surface detection from web browser User-Agent."""
        from app.auth.dependencies import detect_surface

        request = MagicMock()
        request.headers = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/91.0"}

        surface = detect_surface(request)
        assert surface == "web"

    def test_detect_surface_unknown(self) -> None:
        """Test surface detection returns unknown when no indicators."""
        from app.auth.dependencies import detect_surface

        request = MagicMock()
        # Use MagicMock for headers to allow .get method mocking
        headers = MagicMock()
        headers.get = MagicMock(return_value="")
        request.headers = headers

        surface = detect_surface(request)
        assert surface == "unknown"


class TestIMSValidator:
    """Tests for IMS token validation."""

    @pytest.mark.asyncio
    async def test_validator_caches_results(self) -> None:
        """Test that validator caches successful validations."""
        from app.services.ims_validator import IMSTokenValidator

        validator = IMSTokenValidator()

        mock_response = {
            "sub": "user-123",
            "email": "test@example.com",
            "expires_in": 3600,
        }

        with patch("app.services.ims_validator.httpx.AsyncClient") as mock_client_class:
            # Create a mock response
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response

            # Create mock client with async context manager
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # First call
            result1 = await validator.validate_token("test-token")
            assert result1.user_id == "user-123"
            assert mock_client.get.call_count == 1

            # Second call should use cache
            result2 = await validator.validate_token("test-token")
            assert result2.user_id == "user-123"
            assert mock_client.get.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_validator_rejects_invalid_token(self) -> None:
        """Test that validator raises error for invalid tokens."""
        from app.services.ims_validator import IMSTokenValidator, IMSValidationError

        validator = IMSTokenValidator()

        with patch("app.services.ims_validator.httpx.AsyncClient") as mock_client_class:
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 401

            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(IMSValidationError) as exc_info:
                await validator.validate_token("invalid-token")

            assert "Invalid or expired token" in str(exc_info.value)


class TestSessionManager:
    """Tests for session management."""

    def test_session_creation(self) -> None:
        """Test session creation with user info."""
        from datetime import datetime, timedelta

        from app.services.session import SessionManager

        manager = SessionManager()
        user_info = IMSUserInfo(
            user_id="user-123",
            email="test@example.com",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        session = manager.create_session(user_info, "web")

        assert session.user_id == "user-123"
        assert session.surface == "web"
        assert session.context_id is not None

    def test_session_reuse_with_same_context(self) -> None:
        """Test that same context_id returns existing session."""
        from datetime import datetime, timedelta

        from app.services.session import SessionManager

        manager = SessionManager()
        user_info = IMSUserInfo(
            user_id="user-123",
            email="test@example.com",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        session1 = manager.create_session(user_info, "web")
        session2 = manager.create_session(user_info, "web", context_id=session1.context_id)

        assert session1.context_id == session2.context_id

    def test_expired_session_removed(self) -> None:
        """Test that expired sessions are not returned."""
        from datetime import datetime, timedelta

        from app.services.session import SessionManager

        manager = SessionManager()
        # Create session that's already expired
        user_info = IMSUserInfo(
            user_id="user-123",
            email="test@example.com",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )

        session = manager.create_session(user_info, "web")

        # Session should not be retrievable since it's expired
        retrieved = manager.get_session(session.context_id)
        assert retrieved is None
