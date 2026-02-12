# Brand Concierge Integration Blueprint

A partner guide to building and integrating A2A agents with Adobe Brand Concierge.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Integration Checklist](#integration-checklist)
- [Step 1: Build Your A2A Agent](#step-1-build-your-a2a-agent)
  - [1.1 A2A Protocol Requirements](#11-a2a-protocol-requirements)
  - [1.2 Agent Card](#12-agent-card)
  - [1.3 JSON-RPC Endpoint](#13-json-rpc-endpoint)
  - [1.4 Authentication](#14-authentication)
  - [1.5 Agent Logic](#15-agent-logic)
- [Step 2: Register Your Agent in the AO Manifest](#step-2-register-your-agent-in-the-ao-manifest)
- [Step 3: Bind the Manifest to a Brand Concierge Instance](#step-3-bind-the-manifest-to-a-brand-concierge-instance)
- [Step 4 (Optional): Surface the Agent in Agent Composer](#step-4-optional-surface-the-agent-in-agent-composer)
- [Step 5: Compliance — Mutations and Headers](#step-5-compliance--mutations-and-headers)
- [Getting Started with the Reference Agent](#getting-started-with-the-reference-agent)
- [Customization Guide](#customization-guide)
- [Testing Your Agent](#testing-your-agent)
- [Production Considerations](#production-considerations)

---

## Overview

Adobe Brand Concierge enables brands to deploy AI-powered conversational agents on their digital properties. Partners can extend Brand Concierge by building custom agents using the **A2A (Agent-to-Agent) protocol** — an open standard for agent interoperability.

Your agent does not communicate with Brand Concierge directly. Instead, it is orchestrated by the **Adobe Experience Platform Agent Orchestrator (AO)**, which routes conversations between the end user and your agent.

**The flow:**

```
End User (Web/Mobile)
        |
        v
Brand Concierge Conversation Service
        |
        v
Agent Orchestrator (AO)  ──  v1_directagent mode
        |
        v
Your A2A Agent
```

AO discovers your agent via its **Agent Card**, routes messages to your **JSON-RPC endpoint**, and returns your responses to the end user through Brand Concierge.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Brand Concierge                         │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Web SDK /   │───>│ Conversation │───>│    Agent     │   │
│  │  Mobile SDK  │    │   Service    │    │ Orchestrator │   │
│  └──────────────┘    └──────────────┘    └───────┬──────┘   │
│                                                  │          │
└──────────────────────────────────────────────────│──────────┘
                                                   │
                              ┌────────────────────┤
                              │                    │
                              v                    v
                     ┌────────────────┐    ┌────────────────┐
                     │  Your Custom   │    │  Other A2A     │
                     │  A2A Agent     │    │  Agents        │
                     │                │    │                │
                     │ /.well-known/  │    │ /.well-known/  │
                     │  agent.json    │    │  agent.json    │
                     │ /a2a (JSON-RPC)│    │ /a2a (JSON-RPC)│
                     └────────────────┘    └────────────────┘
```

---

## Integration Checklist

| Step | Owner | Action |
|------|-------|--------|
| **1. Build A2A agent** | Partner | Implement JSON-RPC endpoint, publish Agent Card, handle IMS auth |
| **2. AO manifest** | Adobe Engineering | Add your agent entry to the Brand Concierge AO manifest |
| **3. Concierge binding** | Adobe Engineering | Point a concierge instance at the manifest and bind to a datastream |
| **4. UI exposure** (optional) | Adobe Product + Partner | Add as a selectable skill in Agent Composer |
| **5. Compliance** | Partner | Support mutation extension, IMS user tokens, and header passthrough |

---

## Step 1: Build Your A2A Agent

The [Brand Concierge Reference Agent](https://github.com/anthropics/bc-reference-agent) provides a fully working implementation you can use as a starting point. It demonstrates all the patterns described below.

### 1.1 A2A Protocol Requirements

Your agent must implement the [A2A specification](https://a2a-protocol.org/):

- **Transport**: JSON-RPC 2.0 over HTTP(S)
- **Discovery**: Publish an Agent Card at `/.well-known/agent.json`
- **Protocol versions**: Support A2A 0.2 and/or 0.3
- **Authentication**: Accept and validate Adobe IMS Bearer tokens

### 1.2 Agent Card

The Agent Card is a JSON document that declares your agent's identity, capabilities, and security requirements. AO uses this card to discover your agent and understand what it can do.

Publish it at: `https://<your-agent-host>/.well-known/agent.json`

**Required fields:**

| Field | Description |
|-------|-------------|
| `name` | Human-readable agent name |
| `description` | What your agent does (used by AO for routing decisions) |
| `url` | Base URL where your agent is reachable |
| `protocolVersions` | A2A versions supported (e.g., `["0.2", "0.3"]`) |
| `capabilities` | Feature flags: `streaming`, `pushNotifications`, etc. |
| `skills` | Array of skills your agent provides |
| `securitySchemes` | Authentication methods accepted |
| `security` | Which security schemes are required |

**Example Agent Card** (from the Reference Agent):

```json
{
  "name": "Sample Shipping Agent",
  "description": "A reference A2A agent implementation demonstrating order tracking and shipping management. Shows how to build agents that handle order lookups, delivery date updates, and address changes with email verification. Orchestrated by Adobe Experience Platform Agent Orchestrator.",
  "url": "http://localhost:8000",
  "protocolVersions": ["0.2", "0.3"],
  "provider": {
    "organization": "Your Organization",
    "url": "https://your-org.com"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "extendedAgentCard": false
  },
  "skills": [
    {
      "id": "shipping-assistant",
      "name": "Shipping Assistant",
      "description": "Helps customers track orders, check delivery dates, update delivery dates, and change shipping addresses. Verifies identity using Order ID and email address before providing order details or making changes.",
      "tags": ["shipping", "delivery", "tracking", "orders"],
      "examples": [
        "When will my order 3DV7KU4PK54 arrive? My email is customer@example.com",
        "Can I change my delivery date? Order ID 2K97AT2CK39, email mpedden2@cnet.com",
        "I want to update my address to 456 Oak Avenue, Boston, Massachusetts 02101"
      ]
    }
  ],
  "securitySchemes": {
    "imsBearer": {
      "type": "http",
      "scheme": "bearer",
      "bearerFormat": "IMS",
      "description": "Adobe IMS access token"
    }
  },
  "security": [{ "imsBearer": [] }]
}
```

**Skill design guidelines:**

- Write clear, specific `description` text — AO uses this to decide when to route to your agent
- Include realistic `examples` that show the kind of user messages your agent handles
- Use descriptive `tags` for categorization
- Each skill should have a unique `id`

### 1.3 JSON-RPC Endpoint

Your agent must expose a single JSON-RPC 2.0 endpoint (typically at `/a2a`) that handles the following methods:

| Method | Purpose | Required |
|--------|---------|----------|
| `message/send` | Receive a user message and return a Task with the agent's response | Yes |
| `tasks/get` | Retrieve a task by its ID | Yes |
| `tasks/list` | List tasks, optionally filtered by context ID | Recommended |
| `tasks/cancel` | Cancel a running task | Recommended |

**Request format:**

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        { "kind": "text", "text": "When will my order arrive?" }
      ]
    },
    "configuration": {
      "contextId": "conversation-123",
      "taskId": "task-456"
    }
  }
}
```

**Response format (Task object):**

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "result": {
    "id": "task-456",
    "contextId": "conversation-123",
    "status": { "state": "completed" },
    "createdAt": "2025-01-15T10:30:00Z",
    "updatedAt": "2025-01-15T10:30:01Z",
    "messages": [
      {
        "role": "user",
        "parts": [{ "kind": "text", "text": "When will my order arrive?" }]
      },
      {
        "role": "agent",
        "parts": [{ "kind": "text", "text": "Your order is scheduled for delivery on 2/15/2025." }]
      }
    ],
    "artifacts": []
  }
}
```

**Task lifecycle states:**

```
working  ──>  completed
         ──>  failed
         ──>  canceled
         ──>  input_required
         ──>  auth_required
```

**Error responses** must follow JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "error": {
    "code": -32601,
    "message": "Method not found: invalid/method"
  }
}
```

Standard error codes:

| Code | Meaning |
|------|---------|
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32603` | Internal error |

The Reference Agent implements the full JSON-RPC routing in `app/main.py`.

### 1.4 Authentication

Brand Concierge uses **Adobe IMS (Identity Management Service)** tokens. Your agent must validate these tokens on every request.

**Flow:**

1. AO forwards the end user's IMS Bearer token to your agent via the `Authorization` header
2. Your agent extracts the token and validates it against the IMS userinfo endpoint
3. On success, you have the authenticated user's identity for the session

**Implementation requirements:**

- Extract the `Bearer` token from the `Authorization` header
- Validate against: `https://ims-na1.adobelogin.com/ims/userinfo/v2`
- Cache validated tokens (recommended TTL: 24 hours) to reduce latency
- Return HTTP 401 with `WWW-Authenticate: Bearer realm="Adobe IMS"` on failure
- Use **IMS user tokens** (not service tokens) for user-facing agents

**Reference implementation** — the Reference Agent handles this in `app/auth/dependencies.py` and `app/services/ims_validator.py`:

```python
# FastAPI dependency — validates IMS token on every /a2a request
@app.post("/a2a")
async def handle_jsonrpc(
    request: Request,
    session: IMSSession = Depends(require_ims_auth),
):
    # session contains: user_id, surface, context_id
    ...
```

**Surface detection:** The Reference Agent also detects the client surface type (web, mobile, tablet) from request headers, which can be used to tailor responses. This is optional but recommended.

**Configuration (from `.env`):**

```env
IMS_CLIENT_ID=your_client_id_from_adobe_developer_console
IMS_VALIDATION_CACHE_TTL=86400
IMS_BASE_URL=https://ims-na1.adobelogin.com
```

Obtain your `IMS_CLIENT_ID` from the [Adobe Developer Console](https://developer.adobe.com/console).

### 1.5 Agent Logic

Your agent logic processes user messages and generates responses. This is where your business domain expertise lives.

**Interface contract** — your agent must implement:

```python
async def process_message(self, message: str, context_id: str | None = None) -> str:
    """
    Process a user message and return a text response.

    Args:
        message: The user's message text
        context_id: Conversation context ID for multi-turn continuity

    Returns:
        The agent's response text
    """
    ...
```

For streaming support:

```python
async def process_message_stream(
    self, message: str, context_id: str | None = None
) -> AsyncIterator[str]:
    """Process a message and yield response chunks."""
    ...
```

**The Reference Agent's shipping assistant** (`app/agents/sample_shipping_agent.py`) demonstrates:

- **Identity verification**: Extracts Order ID and email via regex, verifies against a database
- **Session state management**: Tracks verified orders and pending updates per conversation context
- **Two-step confirmation flow**: Proposes changes, waits for user confirmation, then applies
- **LLM integration**: Uses an LLM for natural language responses with keyword-based fallback
- **Conversation history**: Maintains per-context message history for multi-turn conversations

Replace this with your own agent logic while keeping the same interface.

---

## Step 2: Register Your Agent in the AO Manifest

Once your A2A agent is deployed and reachable, it must be registered in the Brand Concierge AO manifest. This is the configuration that tells Agent Orchestrator about your agent.

**Manifest structure:**

```yaml
manifest_id: my_brand_concierge_manifest
streaming: true

agent_orchestrator:
  url: <AO cluster endpoint>
  enabled: true
  config:
    runtime_mode: v1_directagent
    llm_config:
      coordinator_model: gpt-4.1-mini
      agent_executor_model: gpt-4o

agents:
  - agent: product_advisor_agent
    ref: agent_cards/product_advisor_agent
    allow_direct_responses: true
    config:
      is_agent_name_enabled: true
      is_chat_history_enabled: true

  - agent: my_new_a2a_agent              # Your A2A agent
    ref: agent_cards/my_new_a2a_agent    # Points to your Agent Card URL
    allow_direct_responses: true
    config:
      is_agent_name_enabled: true
      is_chat_history_enabled: false
```

**Key fields for your agent entry:**

| Field | Description |
|-------|-------------|
| `agent` | Unique identifier for your agent in the manifest |
| `ref` | Reference to your Agent Card (URL or path) |
| `allow_direct_responses` | Whether your agent can respond directly to users |
| `config.is_agent_name_enabled` | Include your agent's name in responses |
| `config.is_chat_history_enabled` | Whether AO forwards conversation history |

**Who edits the manifest?**

> [!CAUTION]
> **TODO — Pending internal confirmation**
>
> Waiting for answers on how the AO manifest is managed. How can partners have their agent added? They will need to provide:

1. Your Agent Card URL (e.g., `https://your-agent.example.com/.well-known/agent.json`)
2. Your preferred agent identifier
3. Configuration preferences (chat history, direct responses, etc.)

---

## Step 3: Bind the Manifest to a Brand Concierge Instance

After your agent is in the manifest, the manifest must be bound to a Brand Concierge **concierge** instance. This is handled by Adobe Engineering using internal configuration APIs.

> [!CAUTION]
> **TODO — Pending internal confirmation**
>
> Diana/Cecily to confirm if this level of detail needs to be shared with partners.

**What happens:**

1. A concierge is created (or updated) to reference the manifest containing your agent:

```json
{
  "id": "my-concierge-id",
  "name": "My Concierge with A2A Agent",
  "type": "b2c",
  "manifestId": "my_brand_concierge_manifest"
}
```

2. The concierge is bound to a **datastream** so the Web SDK knows which concierge handles conversations:

```json
{
  "id": "<datastreamId>",
  "imsOrgId": "<ims-org>@AdobeOrg",
  "sandboxName": "<sandbox>",
  "sandboxId": "<sandboxId>",
  "name": "BC DataStream",
  "conciergeId": "my-concierge-id",
  "datacollectionConfigs": {
    "configId": "<edge-config-id>"
  }
}
```

Once this binding is in place, any Brand Concierge conversation routed to that concierge will have AO selecting among the registered agents — including yours — based on the user's message and each agent's skill descriptions.

Work with your Adobe partner contact to complete this step.

---

## Step 4 (Optional): Surface the Agent in Agent Composer

By default, your agent operates behind the scenes, selected by AO based on routing logic. To make your agent visible and configurable by brand marketers in the Brand Concierge UI:

1. **Define it as a skill** in Agent Composer's catalog
2. **Wire Composer to the Conversation Service** so enabling/disabling the skill updates the concierge configuration
3. **Coordinate with Adobe Product** to surface your skill as a selectable capability in the Agent Composer interface

This step involves UX and product coordination beyond the technical integration. It makes your agent a "first-class" capability that Brand Concierge customers can turn on and off per concierge.

---

## Step 5: Compliance — Mutations and Headers

If your agent can **modify customer state** (e.g., update orders, change preferences, book appointments), you must follow the DX mutation protocol:

### Mutation Extension

- Declare the mutation extension in your Agent Card
- Implement mutation handling in your agent's request handler
- Accept mutation calls without adding extra LLM reasoning in between — if your agent chains to other agents (business-agent to technical-agent), forward mutation calls unchanged

### Header Passthrough

If your agent calls other downstream agents or services:

- Pass through IMS headers unmodified
- Preserve organization and sandbox context headers

---

## Getting Started with the Reference Agent

The fastest way to start is to clone and run the Reference Agent.

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for LLM support)
- An Adobe Developer Console project (for `IMS_CLIENT_ID`)

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd bc-reference-agent

# Docker (recommended — includes local LLM)
cp .env.example .env
# Edit .env to set IMS_CLIENT_ID, BRAND_NAME, BRAND_TONE
./run.sh dev
```

### Verify It Works

Once running, visit:

- `http://localhost:8003` — Interactive chat test UI
- `http://localhost:8003/.well-known/agent.json` — Agent Card
- `http://localhost:8003/docs` — OpenAPI documentation
- `http://localhost:8003/orders` — Sample order database viewer

### Environment Configuration

```env
# App
APP_NAME=Brand Concierge Reference Agent
DEBUG=false
PORT=8003

# Brand (customize these)
BRAND_NAME=Your Brand
BRAND_TONE=friendly and professional

# Database
DB_PATH=data/orders.db

# LLM (Ollama runs locally via Docker)
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen2.5:3b

# Adobe IMS Authentication
IMS_CLIENT_ID=your_client_id_from_developer_console
IMS_VALIDATION_CACHE_TTL=86400
IMS_BASE_URL=https://ims-na1.adobelogin.com
```

---

## Customization Guide

The Reference Agent is designed to be replaced with your own business logic. Here is what to modify:

### 1. Replace the Agent Logic

The core file to replace is `app/agents/sample_shipping_agent.py`. This contains the shipping assistant implementation.

**Create your own agent class** that implements:

```python
class YourCustomAgent:
    async def process_message(self, message: str, context_id: str | None = None) -> str:
        """Your agent logic here."""
        ...

    async def process_message_stream(
        self, message: str, context_id: str | None = None
    ) -> AsyncIterator[str]:
        """Optional: streaming support."""
        ...
```

Then update `app/agents/handler.py` to use your agent:

```python
from app.agents.your_custom_agent import YourCustomAgent

class A2AHandler:
    def __init__(self) -> None:
        self.agent = YourCustomAgent()
        ...
```

**What you can integrate:**

- Your own backend APIs and databases
- RAG (Retrieval-Augmented Generation) systems
- Third-party LLM providers (OpenAI, Anthropic, Azure, etc.)
- CRM systems, product catalogs, knowledge bases
- Appointment booking, order management, support ticketing

### 2. Update the Agent Card

Edit `app/agent_card.json` to describe your agent's capabilities:

```json
{
  "name": "Your Agent Name",
  "description": "Clear description of what your agent does — AO uses this for routing",
  "url": "https://your-production-url.com",
  "skills": [
    {
      "id": "your-skill-id",
      "name": "Your Skill Name",
      "description": "Detailed description of this skill's capabilities",
      "tags": ["relevant", "tags"],
      "examples": [
        "Example user message that triggers this skill",
        "Another example showing a different capability"
      ]
    }
  ]
}
```

### 3. Configure Brand Identity

Set `BRAND_NAME` and `BRAND_TONE` in your `.env` file. These are used by the agent's LLM system prompt to shape response personality:

```env
BRAND_NAME=Acme Electronics
BRAND_TONE=warm, helpful, and knowledgeable about consumer electronics
```

### 4. Add Your Data Layer

The Reference Agent uses SQLite for order data. Replace with your own data source:

- Modify or replace `app/models/order.py` with your domain models
- Modify or replace `app/repositories/order_repository.py` with your data access layer
- Connect to your production database, API, or service

---

## Testing Your Agent

The Reference Agent includes a test suite that demonstrates how to test A2A agents with mocked authentication.

### Run Tests

```bash
pytest                                          # All tests
pytest tests/test_a2a.py -v                     # A2A protocol tests
pytest tests/test_agent.py -v                   # Agent logic tests
pytest tests/test_auth.py -v                    # Authentication tests
pytest --cov=app --cov-report=term-missing      # With coverage
```

### Test with Mocked Authentication

Tests use mocked IMS validation so you don't need real tokens. See `tests/conftest.py`:

```python
@pytest.fixture
def client(mock_ims_user):
    """Test client with mocked IMS authentication."""
    with patch.object(ims_validator, "validate_token", return_value=mock_ims_user):
        client = TestClient(app)
        client.headers["Authorization"] = "Bearer test-token"
        yield client
```

### Test the A2A Endpoint Manually

```bash
curl -X POST http://localhost:8003/a2a \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-ims-token>" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello, I need help with my order"}]
      }
    }
  }'
```

### Code Quality

```bash
ruff check .          # Lint
ruff check . --fix    # Auto-fix lint issues
ruff format .         # Format code
mypy app              # Type checking
```

---

## Production Considerations

### Replace In-Memory Storage

The Reference Agent uses in-memory dictionaries for tasks, contexts, and sessions. For production multi-worker deployments:

- Replace task storage in `A2AHandler` with Redis or a database
- Replace session storage in `SessionManager` with a shared store
- Ensure all workers can access the same state

### Deployment

The Reference Agent includes Docker support:

```bash
./run.sh prod         # Production mode with 4 Uvicorn workers
./run.sh logs         # Follow container logs
./run.sh status       # Check container status
./run.sh down         # Stop all containers
```

For production:

- Deploy behind a reverse proxy (NGINX, Cloudflare, etc.)
- Enable HTTPS — AO will communicate with your agent over HTTPS
- Set the `url` field in your Agent Card to your production URL
- Configure health checks (the Reference Agent exposes `/health`)
- Set up logging and monitoring

### Routing

For agents deployed within the Adobe DX ecosystem, A2A clients will typically reach your agent through:

> [!CAUTION]
> **TODO — Pending internal confirmation**
>
> Need updates from Diana on the routing URLs:
> - Agent endpoint: `https://...../a2a/<agent-name>`
> - Agent Card: `https://...../a2a/<agent-name>/agent-card.json`

Coordinate with Adobe Engineering for routing configuration.

---

## Reference Agent Project Structure

```
bc-reference-agent/
├── app/
│   ├── main.py                          # FastAPI app, JSON-RPC routing
│   ├── agent_card.json                  # A2A Agent Card
│   ├── agents/
│   │   ├── handler.py                   # A2A task lifecycle management
│   │   └── sample_shipping_agent.py     # Sample agent (replace this)
│   ├── auth/
│   │   └── dependencies.py              # IMS authentication dependency
│   ├── core/
│   │   └── config.py                    # Environment configuration
│   ├── models/
│   │   └── order.py                     # Data models
│   ├── repositories/
│   │   └── order_repository.py          # Database access layer
│   ├── services/
│   │   ├── ims_validator.py             # IMS token validation with caching
│   │   └── session.py                   # Session management
│   ├── templates/                       # Test UI (chat + orders)
│   └── static/                          # CSS/JS for test UI
├── tests/                               # Test suite
├── data/
│   └── orders.db                        # Sample SQLite database
├── run.sh                               # Docker deployment script
├── docker-compose.yml                   # Production Docker config
├── docker-compose.dev.yml               # Development Docker config
├── .env.example                         # Environment template
└── pyproject.toml                       # Python project config
```

---

## Key Resources

| Resource | Description |
|----------|-------------|
| [A2A Protocol Specification](https://a2a-protocol.org/) | The open protocol your agent implements |
| [Adobe Developer Console](https://developer.adobe.com/console) | Obtain your IMS Client ID |
| Brand Concierge Reference Agent | This repository — working reference implementation |
