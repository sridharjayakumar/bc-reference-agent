# Brand Concierge Reference Agent

A reference [A2A (Agent-to-Agent)](https://a2a-protocol.org/latest/specification/) agent implementation that integrates with [Adobe Brand Concierge](https://business.adobe.com/products/brand-concierge.html). This project demonstrates how to build custom A2A-compliant agents that can be orchestrated by Adobe Experience Platform Agent Orchestrator within the Brand Concierge ecosystem.

## What is Adobe Brand Concierge?

[Adobe Brand Concierge](https://business.adobe.com/products/brand-concierge.html) is Adobe's AI-powered application that transforms customer websites into conversational experiences. It enables website visitors to have natural conversations instead of navigating menus, personalizes interactions using Adobe Experience Platform data, and maintains brand safety with guardrails.

## What is This Project?

This is a **reference implementation** showing developers how to build **custom agents** that integrate with Brand Concierge. When you build agents using this pattern, they can be:

- Discovered by Adobe Experience Platform Agent Orchestrator via Agent Cards
- Invoked by Brand Concierge to handle specific customer queries
- Specialized for your domain (product catalogs, order tracking, custom knowledge bases)
- Integrated with your backend systems (CRMs, databases, APIs)

Think of this as a template/blueprint for building agents that plug into the Brand Concierge ecosystem.

## Table of Contents

- [Architecture](#architecture)
- [Implementation Details](#implementation-details)
- [Authentication](#authentication)
- [Development](#development)
- [Production](#production)
- [Testing](#testing)
- [References](#references)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│               Brand Concierge Reference Agent (A2A Server)                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  GET /                           Test chat UI (no auth)                      │
│  GET /.well-known/agent.json     Agent Card (discovery, no auth)             │
│  POST /a2a                       JSON-RPC 2.0 endpoint (IMS auth required)   │
│  GET /health                     Health check (no auth)                      │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  Authentication Layer                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  require_ims_auth → Bearer token → IMS userinfo → IMSSession         │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────────────────┤
│  A2A Protocol Handler                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  message/send | tasks/get | tasks/list | tasks/cancel                │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────────────────┤
│  Agent Implementation (Example Skills)                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  Intent Classification → product | navigation | general              │    │
│  │  Skill Handlers → product-advisor | site-navigator | brand-assistant │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘

           ↕ A2A Protocol (JSON-RPC 2.0 over HTTPS)

┌──────────────────────────────────────────────────────────────────────────────┐
│           Adobe Experience Platform Agent Orchestrator                       │
│         (Routes customer queries to appropriate A2A agents)                  │
└──────────────────────────────────────────────────────────────────────────────┘

           ↕

┌──────────────────────────────────────────────────────────────────────────────┐
│                      Adobe Brand Concierge                                   │
│        (Transforms websites into conversational experiences)                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
app/
├── main.py                 # FastAPI app, JSON-RPC routing, exception handlers
├── agent_card.json         # A2A Agent Card (skills, capabilities, security)
├── agents/
│   ├── handler.py          # A2A protocol, task lifecycle, message routing
│   └── concierge.py        # Intent classification and skill handlers
├── auth/
│   └── dependencies.py     # IMS auth dependency, surface detection
├── api/routes/
│   └── health.py           # Health check endpoint
├── core/
│   └── config.py           # Pydantic settings (brand, IMS, etc.)
├── services/
│   ├── ims_validator.py    # Adobe IMS token validation and caching
│   └── session.py          # IMSSession and SessionManager
├── templates/
│   └── chat.html           # Test chat UI template
└── static/
    ├── css/                # UI stylesheets
    └── js/                 # UI JavaScript
```

---

## Implementation Details

### A2A Protocol

The server implements the A2A specification and exposes a single JSON-RPC 2.0 endpoint at `POST /a2a`:

| Method | Description |
|--------|-------------|
| `message/send` | Send a message and receive a task. Creates/updates tasks in `working` → `completed`/`failed`. |
| `tasks/get` | Retrieve a task by `taskId`. |
| `tasks/list` | List tasks, optionally filtered by `contextId`. |
| `tasks/cancel` | Cancel a task if it is in a cancellable state. |

Task states follow the [A2A Life of a Task](https://a2a-protocol.org/latest/topics/life-of-a-task/#example-follow-up-scenario) spec: `working`, `completed`, `failed`, `canceled`, `rejected`, `input_required`, `auth_required`.

### Agent Card

The Agent Card is served at `GET /.well-known/agent.json` and declares:

- **Protocol versions:** 0.2, 0.3
- **Skills:**
  - `product-advisor` — Product recommendations and comparisons
  - `site-navigator` — Content discovery and site navigation
  - `brand-assistant` — Brand information and FAQs
- **Capabilities:** Streaming enabled, push notifications disabled
- **Security:** `imsBearer` (Adobe IMS access token)

See [Agent Cards in the spec](https://a2a-protocol.org/latest/specification/#441-agentcard).

### Agent Logic (Example Implementation)

The `BrandConciergeAgent` provides a simple reference implementation using keyword matching. In production, you would replace this with your actual business logic:

- **Product intent:** Keywords like `product`, `recommend`, `buy`, `price`, `compare` → integrate with your product catalog
- **Navigation intent:** Keywords like `find`, `where`, `navigate`, `page`, `link` → integrate with your content management system
- **General intent:** Default fallback for brand queries → integrate with your knowledge base or FAQ system

This simple pattern demonstrates the architecture. Real implementations typically use LLMs, RAG, database queries, or API integrations.

### State Management

- **Tasks:** In-memory store keyed by `taskId`
- **Contexts:** `contextId` → list of `taskId`s for conversation continuity
- **Sessions:** IMS-validated sessions with user context, surface, and context ID

---

## Authentication

### IMS Bearer Authentication

The `/a2a` endpoint requires Adobe IMS (Identity Management System) authentication.

- **Header:** `Authorization: Bearer <ims_access_token>`
- **Agent Card:** Declares `imsBearer` in `securitySchemes` and `security`

See the [Adobe A2A Extensions](https://github.com/OneAdobe/adobe-a2a/tree/main/extensions/adobe) for Adobe-specific auth requirements.

### Authentication Flow

1. Client sends request with `Authorization: Bearer <token>`.
2. `require_ims_auth` extracts the token and validates it via IMS `userinfo/v2`.
3. On success, an `IMSSession` is created with `user_id`, `surface`, and `context_id`.
4. The session is passed to handlers; `user_id` and `surface` are stored in task metadata.

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `IMS_CLIENT_ID` | Adobe API client ID (sent as `X-Api-Key` to IMS) | `""` |
| `IMS_VALIDATION_CACHE_TTL` | Token validation cache TTL in seconds | `86400` (24h) |
| `IMS_BASE_URL` | Adobe IMS base URL | `https://ims-na1.adobelogin.com` |

### Endpoints and Auth

| Endpoint | Authentication |
|----------|----------------|
| `GET /` | None (test UI) |
| `GET /.well-known/agent.json` | None (public) |
| `GET /health` | None |
| `POST /a2a` | Required (IMS Bearer token) |

### Error Responses

- **401 Unauthorized:** Missing `Authorization` header or invalid/expired token.
- Response includes `WWW-Authenticate: Bearer realm="Adobe IMS"` header.

---

## Development

### Prerequisites

- Python 3.11+

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd brand-concierge

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env
# Edit .env to set BRAND_NAME, BRAND_TONE, and IMS_CLIENT_ID
```

### Run the Server

Using the `run.sh` script (recommended):

```bash
./run.sh              # Development mode (auto-reload, port 8000)
./run.sh dev          # Same as above
./run.sh --port 9000  # Custom port
./run.sh prod         # Production mode (4 workers)
```

Or run uvicorn directly:

```bash
uvicorn app.main:app --reload
```

- Test UI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Agent Card: http://localhost:8000/.well-known/agent.json

### Test Chat UI

The server includes a web-based test UI at `GET /` for manual testing. You'll need to provide a valid IMS Bearer token in the authentication panel to interact with the agent. The UI allows you to see the A2A JSON-RPC messages being exchanged.

### Example Request

```bash
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_IMS_ACCESS_TOKEN" \
  -H "X-Adobe-Surface: web" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Where can I find your return policy?"}]
      }
    }
  }'
```

### Linting and Formatting

```bash
ruff check .
ruff check . --fix
ruff format .
```

### Type Checking

```bash
mypy app
```

---

## Production

### Environment Variables

Set all required variables in production:

```env
APP_NAME=Brand Concierge
DEBUG=false

BRAND_NAME=Your Brand Name
BRAND_TONE=friendly and professional

# IMS Authentication
IMS_CLIENT_ID=your_adobe_client_id
IMS_VALIDATION_CACHE_TTL=86400
IMS_BASE_URL=https://ims-na1.adobelogin.com
```

### Run with run.sh

```bash
./run.sh prod
```

With custom host/port (or via environment variables):

```bash
HOST=0.0.0.0 PORT=8000 ./run.sh prod
# or
./run.sh prod --host 0.0.0.0 --port 8000
```

Or run uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### run.sh Reference

| Command | Description |
|---------|-------------|
| `./run.sh` or `./run.sh dev` | Development mode with hot-reload (port 8000) |
| `./run.sh prod` | Production mode with 4 workers |
| `./run.sh --port 9000` | Custom port (works with dev or prod) |
| `./run.sh --host 0.0.0.0` | Bind to all interfaces |
| `HOST=0.0.0.0 PORT=8080 ./run.sh prod` | Use env vars for host/port |
| `./run.sh --help` | Show usage and examples |

The script activates `.venv` or `venv` if present and loads `.env` before starting.

### Deployment Considerations

1. **State:** Tasks and sessions are stored in memory. For multi-worker or multi-instance deployments, use a shared store (e.g., Redis).
2. **HTTPS:** Use a reverse proxy (nginx, Caddy) or load balancer with TLS.
3. **Agent Card URL:** Update the `url` field in `agent_card.json` to your production base URL, or serve it dynamically from config.
4. **IMS:** Ensure `IMS_CLIENT_ID` is set for Adobe integrations. Obtain client credentials from [Adobe Developer Console](https://developer.adobe.com/).

---

## Testing

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
pytest tests/test_a2a.py
pytest tests/test_agent.py
pytest tests/test_health.py
pytest tests/test_auth.py
```

### Run a Single Test

```bash
pytest tests/test_a2a.py::test_send_message -v
```

### Test Coverage

```bash
pytest --cov=app --cov-report=term-missing
```

### Testing Without Real IMS Tokens

The pytest test suite uses mocked IMS authentication so you can run tests without real tokens:

- **Authenticated tests** (`test_a2a`, `test_agent`): Use the `client` fixture which mocks `ims_validator.validate_token` to return a test user.
- **Auth tests** (`test_auth`): Test authentication flow with both successful and failed validation scenarios.
- **Unauthenticated tests**: Use the `unauthenticated_client` fixture to test auth error handling.

See `tests/conftest.py` for implementation details. Note that running the actual server always requires real IMS authentication - there is no "development mode" that bypasses auth.

---

## References

| Resource | Link |
|----------|------|
| A2A Protocol Specification | https://a2a-protocol.org/latest/specification/ |
| A2A Python SDK | https://github.com/a2aproject/a2a-python |
| A2A Sample Agents (Python) | https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents |
| Agent Cards (Spec) | https://a2a-protocol.org/latest/specification/#441-agentcard |
| Life of a Task | https://a2a-protocol.org/latest/topics/life-of-a-task/ |
| A2A Extensions | https://a2a-protocol.org/latest/topics/extensions/ |
| Adobe A2A Extensions | https://github.com/OneAdobe/adobe-a2a/tree/main/extensions/adobe |
| Adobe Agent Orchestrator – Agent Development | https://devhome.corp.adobe.com/docs/default/component/agent-orchestrator/developer-guides/pages/agent-development |
| Agent Discovery (Curated Registries) | https://a2a-protocol.org/latest/topics/agent-discovery/#2-curated-registries-catalog-based-discovery |
