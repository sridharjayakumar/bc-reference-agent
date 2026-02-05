#!/usr/bin/env bash
#
# Run the Brand Concierge Reference Agent (A2A server).
#
# Usage:
#   ./run.sh              # Development mode (reload, port 8000)
#   ./run.sh dev          # Same as above
#   ./run.sh prod         # Production mode (4 workers)
#   ./run.sh --port 9000  # Custom port
#   ./run.sh --host 0.0.0.0 --port 8080  # Custom host and port

set -e

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
MODE="${1:-dev}"

# Parse optional flags
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: ./run.sh [dev|prod] [--host HOST] [--port PORT]"
      echo ""
      echo "  dev (default)  Development mode with hot-reload"
      echo "  prod           Production mode with 4 workers"
      echo "  --host HOST    Bind address (default: 127.0.0.1)"
      echo "  --port PORT    Port number (default: 8000)"
      echo ""
      echo "Examples:"
      echo "  ./run.sh                    # Dev mode on port 8000"
      echo "  ./run.sh prod               # Production with 4 workers"
      echo "  ./run.sh --port 9000        # Dev on port 9000"
      echo "  HOST=0.0.0.0 ./run.sh prod  # Prod bound to all interfaces"
      exit 0
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    dev|prod)
      MODE="$1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Change to script directory
cd "$(dirname "$0")"

# Load .env if present
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# Activate virtual environment if it exists
if [[ -d .venv ]]; then
  source .venv/bin/activate
elif [[ -d venv ]]; then
  source venv/bin/activate
fi

# Ensure uvicorn is available
if ! command -v uvicorn &>/dev/null; then
  echo "uvicorn not found. Install dependencies with: pip install -e \".[dev]\""
  exit 1
fi

echo "Starting Brand Concierge Reference Agent at http://${HOST}:${PORT}"
echo "  Mode: ${MODE}"
echo "  Test UI: http://${HOST}:${PORT}/"
echo "  API docs: http://${HOST}:${PORT}/docs"
echo "  Agent card: http://${HOST}:${PORT}/.well-known/agent.json"
echo ""

if [[ "$MODE" == "prod" ]]; then
  exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 4
else
  exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi
