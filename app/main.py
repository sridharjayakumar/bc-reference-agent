"""Brand Concierge Reference Agent - A2A Server."""

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agents.handler import A2AHandler
from app.api.routes import health
from app.auth.dependencies import AuthenticationError, require_ims_auth
from app.core.config import settings
from app.repositories.order_repository import OrderRepository
from app.services.session import IMSSession

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Reference A2A agent for integration with Adobe Brand Concierge",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize A2A handler
handler = A2AHandler()

# Load agent card
AGENT_CARD_PATH = Path(__file__).parent / "agent_card.json"
with open(AGENT_CARD_PATH) as f:
    AGENT_CARD = json.load(f)

# Setup templates and static files for test UI
TEMPLATES_PATH = Path(__file__).parent / "templates"
STATIC_PATH = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_PATH))
app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")

# Include health router
app.include_router(health.router, tags=["health"])


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    """Handle authentication errors with proper WWW-Authenticate header."""
    return JSONResponse(
        status_code=401,
        content={"error": exc.message},
        headers={"WWW-Authenticate": 'Bearer realm="Adobe IMS"'},
    )


@app.get("/", response_class=HTMLResponse)
async def test_ui(request: Request) -> HTMLResponse:
    """
    Serve the test chat UI.

    Provides a simple interface for testing the A2A agent
    without requiring a separate frontend application.
    """
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "agent_name": AGENT_CARD.get("name", "Brand Concierge Reference Agent"),
            "agent_description": AGENT_CARD.get("description", ""),
            "skills": AGENT_CARD.get("skills", []),
            "ims_token": settings.ims_client_id,
        },
    )


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request) -> HTMLResponse:
    """Serve the orders list page."""
    repo = handler.agent.order_repo
    orders = await repo.get_all_orders()
    latest_order_id = await repo.get_latest_updated_id()
    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "orders": orders, "latest_order_id": latest_order_id},
    )


@app.get("/.well-known/agent.json")
async def get_agent_card() -> dict[str, Any]:
    """
    Return the Agent Card for discovery.

    Per A2A spec, agents publish their card at /.well-known/agent.json
    to enable client discovery of capabilities and skills.
    """
    return AGENT_CARD


@app.post("/a2a")
async def handle_jsonrpc(
    request: Request,
    session: IMSSession = Depends(require_ims_auth),  # noqa: B008
) -> JSONResponse:
    """
    Handle A2A JSON-RPC 2.0 requests.

    Requires IMS authentication via Authorization: Bearer <token> header.

    Supports methods:
    - message/send: Send a message and receive a task
    - tasks/get: Retrieve a task by ID
    - tasks/list: List tasks (optionally by context)
    - tasks/cancel: Cancel a task
    """
    try:
        body = await request.json()
    except Exception:
        return _jsonrpc_error(-32700, "Parse error", None)

    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    if body.get("jsonrpc") != "2.0":
        return _jsonrpc_error(-32600, "Invalid Request: must be JSON-RPC 2.0", request_id)

    if not method:
        return _jsonrpc_error(-32600, "Invalid Request: method required", request_id)

    # Route to appropriate handler
    try:
        if method == "message/send":
            result = await _handle_send_message(params, session)
        elif method == "tasks/get":
            result = await _handle_get_task(params)
        elif method == "tasks/list":
            result = await _handle_list_tasks(params)
        elif method == "tasks/cancel":
            result = await _handle_cancel_task(params)
        else:
            return _jsonrpc_error(-32601, f"Method not found: {method}", request_id)

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        )

    except HTTPException as e:
        return _jsonrpc_error(-32000, e.detail, request_id)
    except Exception as e:
        return _jsonrpc_error(-32603, f"Internal error: {str(e)}", request_id)


async def _handle_send_message(params: dict[str, Any], session: IMSSession) -> dict[str, Any]:
    """Handle message/send method."""
    message = params.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    config = params.get("configuration", {})
    # Use session's context_id if not explicitly provided (per A2A spec)
    context_id = config.get("contextId") or session.context_id
    task_id = config.get("taskId")

    return await handler.send_message(
        message=message,
        context_id=context_id,
        task_id=task_id,
        user_id=session.user_id,
        surface=session.surface,
    )


async def _handle_get_task(params: dict[str, Any]) -> dict[str, Any]:
    """Handle tasks/get method."""
    task_id = params.get("taskId")
    if not task_id:
        raise HTTPException(status_code=400, detail="taskId is required")

    task = await handler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def _handle_list_tasks(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle tasks/list method."""
    context_id = params.get("contextId")
    return await handler.list_tasks(context_id)


async def _handle_cancel_task(params: dict[str, Any]) -> dict[str, Any]:
    """Handle tasks/cancel method."""
    task_id = params.get("taskId")
    if not task_id:
        raise HTTPException(status_code=400, detail="taskId is required")

    task = await handler.cancel_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _jsonrpc_error(code: int, message: str, request_id: Any) -> JSONResponse:
    """Create a JSON-RPC error response."""
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
    )
