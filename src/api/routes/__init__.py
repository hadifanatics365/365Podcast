"""API routes for the podcast generation service."""

from .health import router as health_router
from .podcast import router as podcast_router

__all__ = ["health_router", "podcast_router"]
