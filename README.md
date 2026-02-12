# Brand Concierge Reference Agent

A reference [A2A (Agent-to-Agent)](https://a2a-protocol.org/latest/specification/) agent implementation that integrates with [Adobe Brand Concierge](https://business.adobe.com/products/brand-concierge.html). This project demonstrates how to build custom A2A-compliant agents that can be orchestrated by Adobe Experience Platform Agent Orchestrator within the Brand Concierge ecosystem. The included sample agent handles order tracking and shipping management — look up orders, check delivery dates, update delivery dates, and change shipping addresses.

## What is Adobe Brand Concierge?

[Adobe Brand Concierge](https://business.adobe.com/products/brand-concierge.html) is Adobe's AI-powered application that transforms customer websites into conversational experiences. It enables website visitors to have natural conversations instead of navigating menus, personalizes interactions using Adobe Experience Platform data, and maintains brand safety with guardrails.

## What is This Project?

This is a **reference implementation** showing developers how to build **custom agents** that integrate with Brand Concierge. When you build agents using this pattern, they can be:

- Discovered by Adobe Experience Platform Agent Orchestrator via Agent Cards
- Invoked by Brand Concierge to handle specific customer queries
- Specialized for your domain (product catalogs, order tracking, custom knowledge bases)
- Integrated with your backend systems (CRMs, databases, APIs)

Think of this as a template/blueprint for building agents that plug into the Brand Concierge ecosystem.

**Features:**
- **Self-contained AI** - Includes Ollama for local LLM inference
- **Shipping assistant** - Order tracking, delivery date updates, address changes
- **Conversation memory** - Maintains context across messages
- **Fallback mode** - Works with or without AI enabled
- **Production-ready** - Docker-based, health checks, IMS auth

## Table of Contents

- [Architecture](#architecture)
- [LLM Integration](#llm-integration)
- [Implementation Details](#implementation-details)
- [Authentication](#authentication)
- [Development](#development)
- [References](#references)

---

## Architecture

![Architecture Diagram](docs/architecture.png)

### Directory Structure

```
app/
├── main.py                     # FastAPI app, JSON-RPC routing, exception handlers
├── agent_card.json             # A2A Agent Card (skills, capabilities, security)
├── agents/
│   ├── handler.py              # A2A protocol, task lifecycle, message routing
│   └── sample_shipping_agent.py # Shipping agent: order tracking, date/address updates
├── auth/
│   └── dependencies.py         # IMS auth dependency, surface detection
├── api/routes/
│   └── health.py               # Health check endpoint
├── core/
│   └── config.py               # Pydantic settings (brand, IMS, DB, LLM)
├── models/
│   └── order.py                # Order and OrderUpdate Pydantic models
├── repositories/
│   └── order_repository.py     # SQLite-backed order data access
├── services/
│   ├── ims_validator.py        # Adobe IMS token validation and caching
│   └── session.py              # IMSSession and SessionManager
├── templates/
│   ├── chat.html               # Test chat UI template
│   └── orders.html             # Orders list page
└── static/
    ├── css/                    # UI stylesheets
    └── js/                     # UI JavaScript
```

---

## LLM Integration

The agent uses **Ollama** for self-contained, local AI inference

### Quick Start with AI

```bash
# Start the agent (automatically pulls qwen2.5:3b on first run)
./run.sh dev

# Test it at http://localhost:8003
```

**Note:** The first time you start the agent, it will automatically download the qwen2.5:3b model (~1.9GB, takes 2-5 minutes). After the first download, it's cached and starts immediately! I'm using qwen since it is lightweight and performs better than gemma2 models in data look-up.
Feel free to change it to the LLM of your choice.

### How It Works

- **Local LLM**: Runs Ollama container with Qwen2.5 3B
- **Automatic setup**: Model downloads automatically on first start
- **OpenAI-compatible**: Uses OpenAI SDK with custom base URL
- **Fallback mode**: Works without AI if disabled

### Default Model

This project uses **qwen2.5:3b** (Alibaba's Qwen2.5 3B) as the default model:
- **Size**: 1.9GB
- **RAM**: 3GB minimum
- **Performance**: Strong instruction following, excellent at structured data extraction
- **Auto-download**: Automatically pulled on first startup

### Configuration

To customize the model or LLM settings, edit `.env`:

```env
# LLM Configuration
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen2.5:3b
```

### Disable AI (Optional)

To use keyword-based responses instead of AI:

```env
# In .env
LLM_ENABLED=false
```

Then restart: `./run.sh down && ./run.sh dev`

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
  - `shipping-assistant` — Order tracking, delivery date updates, and shipping address changes with email verification
- **Capabilities:** Streaming enabled, push notifications disabled
- **Security:** `imsBearer` (Adobe IMS access token)

See [Agent Cards in the spec](https://a2a-protocol.org/latest/specification/#441-agentcard).

### Agent Logic

The `ShippingAgent` (`app/agents/sample_shipping_agent.py`) uses AI (Ollama) to generate natural, context-aware responses:

1. **Order Verification**: Customer provides Order ID and email address
   - Regex extraction of order ID (10-15 char alphanumeric) and email from message
   - SQLite lookup via `OrderRepository` to verify the order
   - Verified order stored in session state for the conversation context

2. **Delivery Date Updates**: Two-step confirmation flow
   - Extracts dates from messages (explicit dates, relative expressions like "tomorrow", "next Monday")
   - Stores as pending change, asks for confirmation
   - On confirmation, updates the SQLite database

3. **Address Updates**: Two-step confirmation flow
   - Extracts address components (street, city, state, ZIP) via regex
   - Stores as pending change, asks for confirmation
   - On confirmation, updates the SQLite database

4. **LLM Generation**: Ollama generates contextual responses
   - Uses conversation history for follow-ups (last 10 messages)
   - System prompt includes verified order context and pending changes
   - Falls back to keyword-based responses if AI fails

5. **Fallback Mode**: If `LLM_ENABLED=false`, uses simple keyword-based responses

**Customization**: Replace `ShippingAgent` in `app/agents/sample_shipping_agent.py` with your own agent logic, add RAG for knowledge base integration, or connect to your product APIs.

### State Management

- **Tasks:** In-memory store keyed by `taskId`
- **Contexts:** `contextId` → list of `taskId`s for conversation continuity
- **Sessions:** IMS-validated sessions with user context, surface, and context ID
- **Orders:** SQLite database (`data/orders.db`) for order data and updates

---

## Authentication

### IMS Bearer Authentication

The `/a2a` endpoint requires Adobe IMS (Identity Management System) authentication.

- **Header:** `Authorization: Bearer <ims_access_token>`
- **Agent Card:** Declares `imsBearer` in `securitySchemes` and `security`

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

- Docker Desktop (recommended) or Docker Engine 20.10+
- Docker Compose V2

**Note:** Docker is the default deployment method.

### Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd brand-concierge

# Copy and configure environment
cp .env.example .env
# Edit .env to set IMS_CLIENT_ID and other settings

# Start the agent (Docker)
./run.sh              # macOS/Linux
.\run.ps1             # Windows (PowerShell)
```

### Run the Server

Using the `run.sh` script (macOS/Linux) or `run.ps1` (Windows PowerShell):

```bash
./run.sh              # Development mode with hot-reload
./run.sh dev          # Same as above
./run.sh prod         # Production mode
./run.sh logs         # View logs
./run.sh status       # Check container status
./run.sh restart      # Restart containers
./run.sh down         # Stop containers
./run.sh --help       # Show all commands
```

**Windows (PowerShell):** Replace `./run.sh` with `.\run.ps1` for all commands above.

The agent will be available at:
- Test UI: http://localhost:8003
- API Docs: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc
- Agent Card: http://localhost:8003/.well-known/agent.json

**Note:** Default port is 8003. Change it with `PORT=8000 ./run.sh` if port 8000 is available.

### Test Chat UI

The server includes a web-based test UI at `GET /` for manual testing. You'll need to provide a valid IMS Bearer token in the authentication panel to interact with the agent. The UI allows you to see the A2A JSON-RPC messages being exchanged.

### Development Commands

```bash
# View logs
./run.sh logs

# Check status
./run.sh status

# Restart containers
./run.sh restart

# Stop all containers
./run.sh down
```

### Example Request

```bash
curl -X POST http://localhost:8003/a2a \
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
        "parts": [{"kind": "text", "text": "When will my order 3DV7KU4PK54 arrive? My email is customer@example.com"}]
      }
    }
  }'
```
### Environment Variables

All configuration via environment variables or `.env` file:

```env
APP_NAME=Brand Concierge Reference Agent
DEBUG=false
BRAND_NAME=Your Brand
LLM_ENABLED=true
LLM_MODEL=qwen2.5:3b
IMS_CLIENT_ID=your_client_id
IMS_VALIDATION_CACHE_TTL=86400
IMS_BASE_URL=https://ims-na1.adobelogin.com
```

## References

| Resource | Link |
|----------|------|
| A2A Protocol Specification | https://a2a-protocol.org/latest/specification/ |
| A2A Python SDK | https://github.com/a2aproject/a2a-python |
| A2A Sample Agents (Python) | https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents |
| Agent Cards (Spec) | https://a2a-protocol.org/latest/specification/#441-agentcard |
| Life of a Task | https://a2a-protocol.org/latest/topics/life-of-a-task/ |
| A2A Extensions | https://a2a-protocol.org/latest/topics/extensions/ |
| Agent Discovery (Curated Registries) | https://a2a-protocol.org/latest/topics/agent-discovery/#2-curated-registries-catalog-based-discovery |
