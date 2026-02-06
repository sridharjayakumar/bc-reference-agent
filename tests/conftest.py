import shutil
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.handler import A2AHandler
from app.main import app
from app.repositories.order_repository import OrderRepository
from app.services.ims_validator import IMSUserInfo

SOURCE_DB = Path("data/orders.db")


@pytest.fixture
def mock_ims_user() -> IMSUserInfo:
    """Create a mock IMS user for testing."""
    return IMSUserInfo(
        user_id="test-user-123",
        email="test@example.com",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        org_id="test-org",
    )


@pytest.fixture
def client(mock_ims_user: IMSUserInfo) -> Generator[TestClient, None, None]:
    """Create test client with mocked IMS authentication."""
    with patch(
        "app.auth.dependencies.ims_validator.validate_token",
        new_callable=AsyncMock,
    ) as mock_validate:
        mock_validate.return_value = mock_ims_user
        test_client = TestClient(app)
        # Add default auth header for convenience
        test_client.headers["Authorization"] = "Bearer test-token"
        yield test_client


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """Create test client without authentication (for testing auth failures)."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path: Path) -> Generator[None, None, None]:
    """Redirect the handler's agent repo to a temp copy of the DB for every test."""
    from app.agents import handler as handler_module

    original_handler = handler_module.A2AHandler
    test_db = tmp_path / "test.db"
    shutil.copy(SOURCE_DB, test_db)

    class PatchedHandler(A2AHandler):
        def __init__(self) -> None:
            super().__init__()
            self.agent.order_repo = OrderRepository(db_path=test_db)

    handler_module.A2AHandler = PatchedHandler  # type: ignore[misc]
    yield
    handler_module.A2AHandler = original_handler  # type: ignore[misc]
