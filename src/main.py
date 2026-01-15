"""FastAPI application entry point for the Podcast Generation Service."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import health_router, podcast_router
from src.api.routes.mobile import router as mobile_router
from src.config import get_settings
from src.exceptions import PodcastGenerationError
from src.services.scheduler import get_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Podcast Generation Service")
    settings = get_settings()
    logger.info(f"Environment: debug={settings.debug}")

    # Start the podcast pre-generation scheduler
    scheduler = get_scheduler()
    await scheduler.start()
    logger.info("Podcast scheduler started")

    yield

    # Shutdown
    await scheduler.stop()
    logger.info("Shutting down Podcast Generation Service")


# Create FastAPI application
app = FastAPI(
    title="365Scores Podcast Generation Service",
    description="""
## Overview

Converts sports game data into professional podcast audio using AI.

## Features

- **Daily Recap Mode**: Cohesive summary of multiple matches
- **Game Spotlight Mode**: Deep dive into a single game (pre-game or post-game)
- **Dynamic Routing**: Automatically determines the best mode based on input
- **Betting Integration**: Includes odds and betting insights
- **SSML Support**: Natural pacing with pause markers

## Workflow

1. **Fetch Data**: Retrieves game data from 365Scores API
2. **Orchestrate**: Determines content mode and structure
3. **Generate Script**: Uses Claude AI for natural language generation
4. **Synthesize Audio**: Uses ElevenLabs TTS for voice synthesis
5. **Deliver**: Returns audio file URL

## Authentication

API key authentication (configured via environment variables).
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(PodcastGenerationError)
async def podcast_error_handler(
    request: Request,
    exc: PodcastGenerationError,
) -> JSONResponse:
    """Handle podcast generation errors."""
    return JSONResponse(
        status_code=500,
        content=exc.to_dict(),
    )


# Include routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(podcast_router, prefix="/api/v1")
app.include_router(mobile_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root() -> dict:
    """Root endpoint with service info."""
    return {
        "service": "365Scores Podcast Generation Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.api_workers,
    )
