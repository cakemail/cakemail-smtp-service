"""Health check endpoints."""

from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Liveness probe endpoint.

    Returns 200 OK if the process is running.
    Used by Kubernetes to determine if the pod should be restarted.
    """
    return {"status": "ok", "check": "liveness"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    """Readiness probe endpoint.

    Returns 200 OK if the service is ready to accept traffic.
    Used by Kubernetes to determine if the pod should receive traffic.
    """
    # TODO: Check if SMTP server is accepting connections
    # For now, always return ready
    return {"status": "ok", "check": "readiness"}
