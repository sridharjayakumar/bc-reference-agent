#
# Run the Brand Concierge Reference Agent (A2A server) using Docker.
#
# Usage:
#   .\run.ps1              # Development mode with hot-reload
#   .\run.ps1 dev          # Same as above
#   .\run.ps1 prod         # Production mode
#   .\run.ps1 down         # Stop and remove containers
#   .\run.ps1 logs         # View logs
#   .\run.ps1 restart      # Restart containers
#   .\run.ps1 --help       # Show this help
#

param(
    [Parameter(Position=0)]
    [string]$Mode = "dev",

    [switch]$Build
)

$ErrorActionPreference = "Stop"

# ── Helper: find running compose stack ──────────────────────────────────────

function Get-RunningComposeFile {
    foreach ($file in @("docker-compose.dev.yml", "docker-compose.yml")) {
        $ids = docker compose -f $file ps -q 2>$null
        if ($ids) { return $file }
    }
    return $null
}

# ── Command dispatch ────────────────────────────────────────────────────────

switch ($Mode) {
    { $_ -in "-h", "--help", "help" } {
        Write-Host "Usage: .\run.ps1 [command]"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  dev (default)   Start in development mode with hot-reload"
        Write-Host "  prod            Start in production mode"
        Write-Host "  down            Stop and remove containers"
        Write-Host "  logs            Follow container logs"
        Write-Host "  restart         Restart containers"
        Write-Host "  status          Show container status"
        Write-Host ""
        Write-Host "Examples:"
        Write-Host "  .\run.ps1        # Start dev mode (automatically pulls qwen2.5:3b model)"
        Write-Host "  .\run.ps1 prod   # Start production mode"
        Write-Host "  .\run.ps1 logs   # View logs"
        Write-Host "  .\run.ps1 down   # Stop everything"
        exit 0
    }

    "down" {
        Write-Host "Stopping all containers..."
        docker compose -f docker-compose.yml down 2>$null
        docker compose -f docker-compose.dev.yml down 2>$null
        Write-Host "Containers stopped and removed"
        exit 0
    }

    "logs" {
        Write-Host "Following logs... (Ctrl+C to exit)"
        $file = Get-RunningComposeFile
        if ($file) {
            docker compose -f $file logs -f
        } else {
            Write-Host "No running containers found"
            Write-Host "Start with: .\run.ps1 dev"
        }
        exit 0
    }

    "restart" {
        Write-Host "Restarting containers..."
        $file = Get-RunningComposeFile
        if ($file) {
            docker compose -f $file restart
        } else {
            Write-Host "No running containers found"
            Write-Host "Start with: .\run.ps1 dev"
        }
        exit 0
    }

    "status" {
        Write-Host "Container status:"
        $file = Get-RunningComposeFile
        if ($file) {
            docker compose -f $file ps
        } else {
            Write-Host "No containers running"
            Write-Host "Start with: .\run.ps1 dev"
        }
        exit 0
    }

    "dev"  { $ComposeFile = "docker-compose.dev.yml" }
    "prod" { $ComposeFile = "docker-compose.yml" }

    default {
        Write-Host "Unknown command: $Mode"
        Write-Host "Run '.\run.ps1 --help' for usage information"
        exit 1
    }
}

# ── Pre-flight checks ──────────────────────────────────────────────────────

# Change to script directory
Set-Location $PSScriptRoot

# Check Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed"
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check docker compose is available
$composeOk = $false
try { docker compose version 2>$null | Out-Null; $composeOk = $true } catch {}
if (-not $composeOk) {
    try { docker-compose version 2>$null | Out-Null; $composeOk = $true } catch {}
}
if (-not $composeOk) {
    Write-Host "Error: docker compose is not available"
    Write-Host "Please install Docker Compose or upgrade Docker Desktop"
    exit 1
}

# Check .env file
if (-not (Test-Path .env)) {
    Write-Host "Warning: .env file not found"
    Write-Host "Creating from .env.example..."
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "Created .env file"
        Write-Host "Please edit .env and set your IMS_CLIENT_ID before continuing"
        Write-Host ""
        Read-Host "Press Enter to continue or Ctrl+C to exit"
    } else {
        Write-Host "Error: .env.example not found"
        exit 1
    }
}

# ── Build flag ──────────────────────────────────────────────────────────────

$BuildFlag = if ($Build) { "--build" } else { "" }

# ── Read PORT from .env or use default ──────────────────────────────────────

$Port = $env:PORT
if (-not $Port) {
    # Try to read PORT from .env file
    if (Test-Path .env) {
        $envLine = Select-String -Path .env -Pattern "^PORT=" -ErrorAction SilentlyContinue
        if ($envLine) { $Port = ($envLine.Line -split "=", 2)[1].Trim() }
    }
}
if (-not $Port) { $Port = "8003" }

# ── Start containers ────────────────────────────────────────────────────────

Write-Host "Starting Brand Concierge Reference Agent..."
Write-Host "  Mode: $Mode"
Write-Host "  Compose file: $ComposeFile"
Write-Host ""

if ($Mode -eq "dev") {
    Write-Host "Starting development mode with hot-reload..."
    Write-Host "  Test UI: http://localhost:$Port/"
    Write-Host "  API docs: http://localhost:$Port/docs"
    Write-Host "  Agent card: http://localhost:$Port/.well-known/agent.json"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop"
    Write-Host ""
    docker compose -f $ComposeFile up $BuildFlag
} else {
    Write-Host "Starting production mode..."
    Write-Host "  Test UI: http://localhost:$Port/"
    Write-Host "  API docs: http://localhost:$Port/docs"
    Write-Host "  Agent card: http://localhost:$Port/.well-known/agent.json"
    Write-Host ""
    docker compose -f $ComposeFile up -d $BuildFlag
    Write-Host ""
    Write-Host "Agent started in background"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  .\run.ps1 logs    # View logs"
    Write-Host "  .\run.ps1 status  # Check status"
    Write-Host "  .\run.ps1 down    # Stop containers"
}
