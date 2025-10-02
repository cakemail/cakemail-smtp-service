"""FastAPI HTTP server for health and metrics endpoints."""

from typing import Any

import structlog
from fastapi import FastAPI
from prometheus_client import generate_latest

from smtp_gateway.config import get_settings
from smtp_gateway.http.health import router as health_router


logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create FastAPI application.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="SMTP Gateway",
        description="Cakemail SMTP Gateway - Health and Metrics API",
        version="0.1.0",
    )

    # Include health check router
    app.include_router(health_router, prefix="/health", tags=["health"])

    # Metrics endpoint
    @app.get("/metrics", tags=["metrics"])
    async def metrics() -> Any:
        """Prometheus metrics endpoint."""
        return generate_latest()

    return app


async def create_http_server() -> Any:
    """Create and start HTTP server.

    Creates a uvicorn server running FastAPI in the same event loop
    as the SMTP server for Story 1.4.

    Returns:
        HTTP server instance (uvicorn Server)
    """
    import asyncio

    import uvicorn

    settings = get_settings()

    logger.info(
        "Creating HTTP server",
        host=settings.http_host,
        port=settings.http_port,
    )

    # Create FastAPI app
    app = create_app()

    # Create uvicorn config
    config = uvicorn.Config(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_level="warning",  # Reduce noise, we have our own logging
        access_log=False,  # Disable access logs
    )

    # Create server instance
    server = uvicorn.Server(config)

    # Start server in background task
    asyncio.create_task(server.serve())

    logger.info(
        "HTTP server started",
        host=settings.http_host,
        port=settings.http_port,
    )

    return server
