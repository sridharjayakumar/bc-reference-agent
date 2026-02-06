#!/usr/bin/env bash
#
# Run the Brand Concierge Reference Agent (A2A server) using Docker.
#
# Usage:
#   ./run.sh              # Development mode with hot-reload
#   ./run.sh dev          # Same as above
#   ./run.sh prod         # Production mode
#   ./run.sh down         # Stop and remove containers
#   ./run.sh logs         # View logs
#   ./run.sh build        # Rebuild images
#   ./run.sh --help       # Show this help

set -e

MODE="${1:-dev}"
COMPOSE_FILE=""

# Parse command
case $MODE in
  -h|--help)
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  dev (default)   Start in development mode with hot-reload"
    echo "  prod            Start in production mode"
    echo "  down            Stop and remove containers"
    echo "  logs            Follow container logs"
    echo "  restart         Restart containers"
    echo "  status          Show container status"
    echo ""
    echo "Examples:"
    echo "  ./run.sh        # Start dev mode (automatically pulls qwen2.5:3b model)"
    echo "  ./run.sh prod   # Start production mode"
    echo "  ./run.sh logs   # View logs"
    echo "  ./run.sh down   # Stop everything"
    exit 0
    ;;
  dev)
    COMPOSE_FILE="docker-compose.dev.yml"
    ;;
  prod)
    COMPOSE_FILE="docker-compose.yml"
    ;;
  down)
    echo "Stopping all containers..."
    docker-compose -f docker-compose.yml down 2>/dev/null || true
    docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
    echo "Containers stopped and removed"
    exit 0
    ;;
  logs)
    echo "Following logs... (Ctrl+C to exit)"
    # Try both compose files with proper error handling
    if docker compose -f docker-compose.dev.yml ps -q 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.dev.yml logs -f
    elif docker compose -f docker-compose.yml ps -q 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.yml logs -f
    else
      echo "No running containers found"
      echo "Start with: ./run.sh dev"
    fi
    exit 0
    ;;
  restart)
    echo "Restarting containers..."
    if docker compose -f docker-compose.dev.yml ps -q 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.dev.yml restart
    elif docker compose -f docker-compose.yml ps -q 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.yml restart
    else
      echo "No running containers found"
      echo "Start with: ./run.sh dev"
    fi
    exit 0
    ;;
  status)
    echo "Container status:"
    if docker compose -f docker-compose.dev.yml ps -q 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.dev.yml ps
    elif docker compose -f docker-compose.yml ps -q 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.yml ps
    else
      echo "No containers running"
      echo "Start with: ./run.sh dev"
    fi
    exit 0
    ;;
  *)
    echo "Unknown command: $MODE"
    echo "Run './run.sh --help' for usage information"
    exit 1
    ;;
esac

# Change to script directory
cd "$(dirname "$0")"

# Check if Docker is installed
if ! command -v docker &>/dev/null; then
  echo "Error: Docker is not installed"
  echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
  exit 1
fi

# Check if docker-compose is available
if ! docker compose version &>/dev/null && ! command -v docker-compose &>/dev/null; then
  echo "Error: docker-compose is not available"
  echo "Please install Docker Compose or upgrade Docker Desktop"
  exit 1
fi

# Use 'docker compose' (V2) if available, otherwise 'docker-compose' (V1)
DOCKER_COMPOSE="docker compose"
if ! docker compose version &>/dev/null; then
  DOCKER_COMPOSE="docker-compose"
fi

# Check if .env file exists
if [[ ! -f .env ]]; then
  echo "Warning: .env file not found"
  echo "Creating from .env.example..."
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "Created .env file"
    echo "Please edit .env and set your IMS_CLIENT_ID before continuing"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to exit..."
  else
    echo "Error: .env.example not found"
    exit 1
  fi
fi

# Initialize orders database from template if it doesn't exist
if [[ ! -f data/orders.db ]]; then
  echo "Initializing orders database from sample-orders.db..."
  mkdir -p data
  cp sample-orders.db data/orders.db
  echo "Created data/orders.db"
fi

# Check for --build flag
BUILD_FLAG=""
if [[ "$2" == "--build" ]]; then
  BUILD_FLAG="--build"
fi

echo "Starting Brand Concierge Reference Agent..."
echo "  Mode: $MODE"
echo "  Compose file: $COMPOSE_FILE"
echo ""

# Start the containers
if [[ "$MODE" == "dev" ]]; then
  echo "Starting development mode with hot-reload..."
  echo "  Test UI: http://localhost:${PORT:-8003}/"
  echo "  API docs: http://localhost:${PORT:-8003}/docs"
  echo "  Agent card: http://localhost:${PORT:-8003}/.well-known/agent.json"
  echo ""
  echo "Press Ctrl+C to stop"
  echo ""
  $DOCKER_COMPOSE -f $COMPOSE_FILE up $BUILD_FLAG
else
  echo "Starting production mode..."
  echo "  Test UI: http://localhost:${PORT:-8003}/"
  echo "  API docs: http://localhost:${PORT:-8003}/docs"
  echo "  Agent card: http://localhost:${PORT:-8003}/.well-known/agent.json"
  echo ""
  $DOCKER_COMPOSE -f $COMPOSE_FILE up -d $BUILD_FLAG
  echo ""
  echo "Agent started in background"
  echo ""
  echo "Useful commands:"
  echo "  ./run.sh logs    # View logs"
  echo "  ./run.sh status  # Check status"
  echo "  ./run.sh down    # Stop containers"
fi
