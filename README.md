# 365Scores Podcast Generation Service

A Python backend service that converts sports game data into professional podcast audio using AI.

## Features

- **Daily Recap Mode**: Cohesive summary of multiple matches with smooth transitions
- **Game Spotlight Mode**: Deep dive into a single game (pre-game preview or post-game recap)
- **Dynamic Routing**: Automatically determines the best mode based on input
- **Betting Integration**: Includes odds, trends, and betting insights
- **SSML Support**: Natural pacing with pause markers for professional audio

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                          │
│                    POST /api/v1/podcast/generate                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PodcastOrchestrator                        │
│  Coordinates: Fetch → Route → Enrich → Script → Audio → Store  │
└─────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  GameFetcher │ │ContentRouter │ │ScriptGenerator│ │AudioSynthesizer│
│  365Scores   │ │ Mode Logic   │ │ Claude API   │ │ ElevenLabs   │
│     API      │ │              │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (or pip)
- API Keys:
  - Anthropic (Claude) API key
  - ElevenLabs API key

### Installation

```bash
# Clone and navigate to service
cd podcast-generation-service

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# ANTHROPIC_API_KEY=your-key-here
# ELEVENLABS_API_KEY=your-key-here

# Install dependencies
poetry install

# Run the service
poetry run uvicorn src.main:app --reload
```

### Using Docker

```bash
cd docker

# Set API keys
export ANTHROPIC_API_KEY=your-key
export ELEVENLABS_API_KEY=your-key

# Start services
docker-compose up -d
```

## API Usage

### Generate Podcast

```bash
curl -X POST http://localhost:8000/api/v1/podcast/generate \
  -H "Content-Type: application/json" \
  -d '{
    "game_ids": ["12345", "67890"],
    "mode": "auto",
    "include_betting": true
  }'
```

**Response:**
```json
{
  "job_id": "pod_abc123def456",
  "status": "completed",
  "audio_url": "https://cdn.example.com/podcasts/2024/01/15/pod_abc123.mp3",
  "duration_seconds": 180.5,
  "script": "Welcome to 365Scores Daily Recap..."
}
```

### Modes

| Mode | Trigger | Content |
|------|---------|---------|
| `daily_recap` | >1 game | Multi-game summary with transitions |
| `game_spotlight` (pre-game) | 1 game, not started | Lineups, form, H2H, betting preview |
| `game_spotlight` (post-game) | 1 game, finished | Results, events, stats, MOTM |
| `auto` | Any | Automatically selects best mode |

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
podcast-generation-service/
├── src/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuration
│   ├── api/routes/             # API endpoints
│   ├── models/                 # Pydantic models
│   ├── services/
│   │   ├── orchestrator.py     # Main workflow
│   │   ├── retrieval/          # 365Scores API client
│   │   ├── script_engine/      # Claude integration
│   │   └── audio_manager/      # ElevenLabs + storage
│   ├── utils/                  # Helpers
│   └── exceptions/             # Custom errors
├── prompts/                    # LLM prompt templates
├── tests/                      # Test suite
├── docker/                     # Docker configuration
└── pyproject.toml              # Dependencies
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | (required) |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | (required) |
| `CLAUDE_MODEL` | Claude model ID | `claude-sonnet-4-20250514` |
| `ELEVENLABS_MODEL` | ElevenLabs model | `eleven_turbo_v2` |
| `STORAGE_TYPE` | `s3` or `local` | `local` |
| `S3_BUCKET_NAME` | S3 bucket for audio | - |

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src

# Run specific test file
poetry run pytest tests/unit/test_content_router.py
```

## Data Flow

1. **Fetch**: Retrieve game data from 365Scores Mobile API (`/data/games`)
2. **Route**: Determine content mode based on game count and status
3. **Enrich**: Add detailed stats, lineups, betting data as needed
4. **Script**: Generate natural language script via Claude with SSML markers
5. **Synthesize**: Convert script to audio via ElevenLabs turbo_v2
6. **Store**: Save to S3 or local filesystem, return URL

## SSML Markers

The script generator uses markers for natural pacing:

- `[PAUSE:short]` - 0.5s pause
- `[PAUSE:medium]` - 1.0s pause
- `[PAUSE:long]` - 1.5s pause
- `*word*` - Emphasis

## License

Proprietary - 365Scores
# 365Podcast
