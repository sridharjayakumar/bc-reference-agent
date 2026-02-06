#!/bin/sh
#
# Initialize Ollama with qwen2.5:3b model on first start
#

set -e

MODEL="qwen2.5:3b"

echo "Initializing Ollama..."

# Wait for Ollama to be ready (max 60 seconds)
for i in $(seq 1 60); do
    if ollama list > /dev/null 2>&1; then
        echo "Ollama is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "Ollama did not start in time"
        exit 1
    fi
    sleep 1
done

# Check if model exists
if ollama list | grep -q "qwen2.5"; then
    echo "Model $MODEL is already available"
    exit 0
fi

# Pull the model
echo "Pulling model $MODEL (~1.9GB, may take 2-5 minutes)..."
if ollama pull "$MODEL"; then
    echo "Model $MODEL is ready!"
else
    echo "Failed to pull model $MODEL"
    exit 1
fi
