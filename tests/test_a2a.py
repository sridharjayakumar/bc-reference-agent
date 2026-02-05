"""Tests for A2A protocol endpoints."""

from fastapi.testclient import TestClient


def test_agent_card_discovery(client: TestClient) -> None:
    """Test that agent card is available at well-known endpoint."""
    response = client.get("/.well-known/agent.json")
    assert response.status_code == 200

    card = response.json()
    assert card["name"] == "Brand Concierge Reference Agent"
    assert "skills" in card
    assert "capabilities" in card
    assert card["capabilities"]["streaming"] is True


def test_send_message(client: TestClient) -> None:
    """Test sending a message via JSON-RPC."""
    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Hello, I'm looking for a product"}],
                }
            },
        },
    )
    assert response.status_code == 200

    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "1"
    assert "result" in result

    task = result["result"]
    assert "id" in task
    assert "contextId" in task
    assert task["status"]["state"] == "completed"
    assert len(task["messages"]) == 2  # user message + agent response


def test_get_task(client: TestClient) -> None:
    """Test retrieving a task by ID."""
    # First create a task
    send_response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Test message"}],
                }
            },
        },
    )
    task_id = send_response.json()["result"]["id"]

    # Then retrieve it
    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tasks/get",
            "params": {"taskId": task_id},
        },
    )
    assert response.status_code == 200

    result = response.json()["result"]
    assert result["id"] == task_id


def test_list_tasks(client: TestClient) -> None:
    """Test listing all tasks."""
    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tasks/list",
            "params": {},
        },
    )
    assert response.status_code == 200
    assert isinstance(response.json()["result"], list)


def test_invalid_method(client: TestClient) -> None:
    """Test that invalid methods return proper error."""
    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "invalid/method",
            "params": {},
        },
    )
    assert response.status_code == 200  # JSON-RPC returns 200 with error in body

    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32601


def test_missing_jsonrpc_version(client: TestClient) -> None:
    """Test that missing jsonrpc version returns error."""
    response = client.post(
        "/a2a",
        json={
            "id": "1",
            "method": "tasks/list",
            "params": {},
        },
    )
    assert response.status_code == 200

    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32600
