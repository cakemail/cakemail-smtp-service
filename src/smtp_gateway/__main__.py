"""Entry point for the SMTP Gateway application."""

import asyncio
import signal
import sys
from typing import Any

import structlog

from smtp_gateway.config import get_settings
from smtp_gateway.logging import setup_logging


logger = structlog.get_logger()


async def main() -> None:
    """Main entry point for the SMTP Gateway."""
    # Setup logging
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info(
        "Starting SMTP Gateway",
        version="0.1.0",
        smtp_port=settings.smtp_port,
        http_port=settings.http_port,
    )

    # Import here to avoid circular dependencies
    from smtp_gateway.http.server import create_http_server
    from smtp_gateway.smtp.server import create_smtp_server

    # Create servers
    smtp_server = await create_smtp_server()
    http_server = await create_http_server()

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig: int) -> None:
        """Handle shutdown signals."""
        logger.info("Received shutdown signal", signal=signal.Signals(sig).name)
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: signal_handler(s))

    # Start servers
    logger.info("SMTP Gateway started successfully")

    try:
        # Wait for shutdown signal
        await shutdown_event.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Shutting down SMTP Gateway")

        # Cleanup servers
        if smtp_server:
            # aiosmtpd Controller uses stop() method
            smtp_server.stop()

        if http_server:
            await http_server.shutdown()

        logger.info("SMTP Gateway stopped")


def run() -> None:
    """Run the application with proper async handling."""
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
