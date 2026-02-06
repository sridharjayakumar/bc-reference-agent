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

**Features:**
- **Self-contained AI** - Includes Ollama for local LLM inference
- **Multiple skills** - Product advisor, site navigator, brand assistant
- **Conversation memory** - Maintains context across messages
- **Fallback mode** - Works with or without AI enabled
- **Production-ready** - Docker-based, health checks, IMS auth

## Table of Contents

- [Architecture](#architecture)
- [LLM Integration](#llm-integration)
- [Implementation Details](#implementation-details)
- [Authentication](#authentication)
- [Development](#development)
- [Docker Deployment](#docker-deployment)
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

## LLM Integration

The agent uses **Ollama** for self-contained, local AI inference

### Quick Start with AI

```bash
# Start the agent (automatically pulls qwen2.5:3b on first run)
./run.sh dev

# Test it at http://localhost:8003
```

**Note:** The first time you start the agent, it will automatically download the qwen2.5:3b model (~1.9GB, takes 2-5 minutes). After the first download, it's cached and starts immediately!

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

**See [LLM-SETUP.md](LLM-SETUP.md) for complete LLM guide:** how automatic model pulling works, troubleshooting, and configuration options.

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

### Agent Logic

The `BrandConciergeAgent` uses AI (Ollama) to generate natural, context-aware responses:

1. **Intent Classification**: Keywords determine which skill to invoke
   - **Product intent:** `product`, `recommend`, `buy`, `price`, `compare`
   - **Navigation intent:** `find`, `where`, `navigate`, `page`, `link`
   - **General intent:** Default fallback for brand queries

2. **System Prompt Selection**: Each intent gets a specialized system prompt
   - Product Advisor: "You are a Product Advisor specializing in..."
   - Site Navigator: "You are a Site Navigator helping..."
   - Brand Assistant: "You are a Brand Assistant providing..."

3. **LLM Generation**: Ollama generates contextual response
   - Uses conversation history for follow-ups
   - Maintains brand tone and guidelines
   - Falls back to keyword-based if AI fails

4. **Fallback Mode**: If `LLM_ENABLED=false`, uses simple hardcoded responses

**Customization**: Edit system prompts in `app/agents/concierge.py` to match your brand, add RAG for knowledge base integration, or connect to your product APIs.

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

### Native Python Setup (Optional)

If you need to run without Docker for development:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run directly with uvicorn
uvicorn app.main:app --reload
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
        "parts": [{"kind": "text", "text": "Where can I find your return policy?"}]
      }
    }
  }'
```

### Code Quality (Optional - Native Python)

If running native Python setup:

```bash
# Linting and formatting
ruff check .
ruff check . --fix
ruff format .

# Type checking
mypy app
```

---

## Docker Deployment

**Note:** Docker is the default and recommended way to run this agent. The `./run.sh` script uses Docker by default.

### Quick Start

```bash
# Using run.sh (recommended)
./run.sh              # Development mode
./run.sh prod         # Production mode
./run.sh logs         # View logs
./run.sh down         # Stop

# Or using docker-compose directly
docker-compose up -d
docker-compose logs -f
docker-compose down
```

### Advanced Docker Usage

```bash
# Build production image
docker build -t brand-concierge-agent:latest .

# Run container
docker run -d \
  --name brand-concierge-agent \
  -p 8000:8000 \
  -e IMS_CLIENT_ID=your_client_id \
  -e BRAND_NAME="Your Brand" \
  --env-file .env \
  brand-concierge-agent:latest
```

### Development with Hot Reload

```bash
# Using run.sh (recommended)
./run.sh dev

# Or using docker-compose directly
docker-compose -f docker-compose.dev.yml up

# Code changes in ./app will auto-reload
```

### Docker Image Features

- **Multi-stage build** - Smaller final image (~200MB)
- **Non-root user** - Runs as user `appuser` for security
- **Health checks** - Automatic container health monitoring
- **Resource limits** - CPU and memory constraints configured
- **Logging** - JSON logs with rotation (max 10MB × 3 files)

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

### Docker Commands Reference

| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start in background |
| `docker-compose up --build` | Rebuild and start |
| `docker-compose logs -f` | Follow logs |
| `docker-compose ps` | Show running containers |
| `docker-compose exec agent sh` | Shell into container |
| `docker-compose down` | Stop and remove containers |
| `docker-compose down -v` | Stop and remove volumes |

### Production Deployment Options

**Single Container:**
```bash
docker run -d \
  --name brand-concierge-agent \
  -p 8000:8000 \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 30s \
  --env-file .env \
  brand-concierge-agent:latest
```

**With HTTPS (behind nginx reverse proxy):**
See docker-compose.yml and configure nginx separately for TLS termination.

**Kubernetes:**
Use the Docker image with Kubernetes Deployment and Service manifests. Set environment variables via ConfigMap and Secrets.

---

## Production

### Environment Variables

Set all required variables in `.env` file:

```env
APP_NAME=Brand Concierge Reference Agent
DEBUG=false

BRAND_NAME=Your Brand Name
BRAND_TONE=friendly and professional

# LLM Configuration
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen2.5:3b

# IMS Authentication (required)
IMS_CLIENT_ID=your_adobe_client_id
IMS_VALIDATION_CACHE_TTL=86400
IMS_BASE_URL=https://ims-na1.adobelogin.com
```

### Run Production Server

```bash
# Start production mode
./run.sh prod

# Check status
./run.sh status

# View logs
./run.sh logs

# Stop
./run.sh down
```

### Command Reference

Use `./run.sh` on macOS/Linux or `.\run.ps1` on Windows PowerShell:

| Command | Description |
|---------|-------------|
| `./run.sh` or `./run.sh dev` | Development mode with hot-reload |
| `./run.sh prod` | Production mode (background) |
| `./run.sh logs` | Follow container logs |
| `./run.sh status` | Show container status |
| `./run.sh restart` | Restart containers |
| `./run.sh down` | Stop and remove containers |
| `./run.sh --help` | Show all commands |

All commands use Docker by default. The qwen2.5:3b model is automatically downloaded on first startup.

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
