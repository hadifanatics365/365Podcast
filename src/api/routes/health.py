"""Health check endpoints."""

from fastapi import APIRouter

from src.models.responses import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service health status.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """
    Readiness check for container orchestration.

    Returns ready status when service can accept requests.
    """
    # TODO: Add checks for dependencies (Redis, APIs)
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Liveness check for container orchestration.

    Returns alive status if service is running.
    """
    return {"alive": True}
