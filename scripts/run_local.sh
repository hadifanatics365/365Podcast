#!/bin/bash
# Run the podcast generation service locally

set -e

# Change to project root
cd "$(dirname "$0")/.."

# Check for .env file
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please update .env with your API keys before running."
    exit 1
fi

# Export environment variables
export $(grep -v '^#' .env | xargs)

# Check required API keys
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your-anthropic-api-key-here" ]; then
    echo "Error: ANTHROPIC_API_KEY not set in .env"
    exit 1
fi

if [ -z "$ELEVENLABS_API_KEY" ] || [ "$ELEVENLABS_API_KEY" = "your-elevenlabs-api-key-here" ]; then
    echo "Error: ELEVENLABS_API_KEY not set in .env"
    exit 1
fi

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -q poetry
poetry install

# Create storage directory
mkdir -p /tmp/podcasts

echo "Starting Podcast Generation Service..."
echo "API docs: http://localhost:8000/docs"
echo ""

# Run the service
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
