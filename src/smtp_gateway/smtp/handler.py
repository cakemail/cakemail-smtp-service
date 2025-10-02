"""SMTP command handlers."""

from typing import Any, Optional

import structlog
from aiosmtpd.smtp import SMTP as SMTPProtocol
from aiosmtpd.smtp import Envelope, Session

from smtp_gateway.config import get_settings
from smtp_gateway.metrics import (
    smtp_connections_total,
    smtp_connection_duration_seconds,
)


logger = structlog.get_logger()


class SMTPHandler:
    """SMTP command handler implementing aiosmtpd interface.

    This handler manages the SMTP session lifecycle and implements
    SMTP commands including AUTH for Story 2.1.
    """

    def __init__(self) -> None:
        """Initialize the SMTP handler."""
        self.settings = get_settings()
        self._connection_start_time: dict[str, float] = {}
        # Track authenticated sessions (peer -> credentials)
        self._authenticated_sessions: dict[str, dict] = {}

    async def handle_EHLO(
        self,
        server: SMTPProtocol,
        session: Session,
        envelope: Envelope,
        hostname: str,
        responses: list[str],
    ) -> list[str]:
        """Handle EHLO command.

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Current envelope
            hostname: Client-provided hostname
            responses: List of capability responses to return

        Returns:
            List of SMTP response strings
        """
        session.host_name = hostname

        logger.info(
            "EHLO command received",
            peer=session.peer,
            hostname=hostname,
        )

        # Return server capabilities
        # For Story 1.2, we only advertise basic capabilities
        # Future stories will add STARTTLS, AUTH, SIZE, etc.
        return responses

    async def handle_QUIT(
        self,
        server: SMTPProtocol,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """Handle QUIT command.

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Current envelope

        Returns:
            SMTP response string
        """
        logger.info(
            "QUIT command received",
            peer=session.peer,
        )

        return "221 Bye"

    def connection_made(self, session: Session) -> None:
        """Called when a new connection is established.

        Args:
            session: The new session
        """
        import time

        peer_address = session.peer[0] if session.peer else "unknown"

        # Track connection start time for metrics
        self._connection_start_time[peer_address] = time.time()

        # Increment connection counter
        smtp_connections_total.labels(status="success").inc()

        logger.info(
            "SMTP connection established",
            peer=session.peer,
        )

    def connection_lost(self, session: Session, error: Optional[Exception] = None) -> None:
        """Called when a connection is closed.

        Args:
            session: The closed session
            error: Optional error that caused connection to close
        """
        import time

        peer_address = session.peer[0] if session.peer else "unknown"

        # Calculate connection duration for metrics
        if peer_address in self._connection_start_time:
            duration = time.time() - self._connection_start_time[peer_address]
            smtp_connection_duration_seconds.observe(duration)
            del self._connection_start_time[peer_address]

        # Log connection close
        if error:
            logger.warning(
                "SMTP connection closed with error",
                peer=session.peer,
                error=str(error),
            )
        else:
            logger.info(
                "SMTP connection closed",
                peer=session.peer,
            )

    async def handle_AUTH(
        self,
        server: SMTPProtocol,
        session: Session,
        envelope: Envelope,
        args: list[str],
    ) -> str:
        """Handle AUTH command.

        Supports AUTH PLAIN and AUTH LOGIN (Story 2.1).
        Requires STARTTLS before authentication.
        Validates credentials with Cakemail API (Story 2.3).

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Current envelope
            args: AUTH command arguments

        Returns:
            SMTP response string
        """
        from smtp_gateway.api.auth import validate_credentials
        from smtp_gateway.api.errors import (
            AuthenticationError,
            NetworkError,
            ServerError,
        )
        from smtp_gateway.smtp.auth import parse_auth_plain

        # Check if connection is encrypted (TLS active)
        if not hasattr(session, "ssl") or session.ssl is None:
            logger.warning(
                "AUTH command rejected - STARTTLS required",
                peer=session.peer,
            )
            return "530 5.7.0 Must issue STARTTLS command first"

        # Parse args
        if not args:
            return "501 Syntax error: AUTH mechanism required"

        mechanism = args[0].upper()
        peer_key = session.peer[0] if session.peer else "unknown"

        # AUTH PLAIN
        if mechanism == "PLAIN":
            if len(args) < 2:
                # Initial response not provided, send empty challenge
                return "334 "

            auth_string = args[1]
            try:
                # Parse credentials (Story 2.1)
                username, password = parse_auth_plain(auth_string)

                logger.info(
                    "AUTH PLAIN credentials parsed, validating with API",
                    peer=session.peer,
                    username=username,
                )

                # Validate credentials with Cakemail API (Story 2.3)
                try:
                    api_key = await validate_credentials(username, password)

                    # Store validated session with API key
                    self._authenticated_sessions[peer_key] = {
                        "username": username,
                        "api_key": api_key,
                        "authenticated": True,
                    }

                    logger.info(
                        "Authentication successful",
                        peer=session.peer,
                        username=username,
                    )

                    return "235 2.7.0 Authentication successful"

                except AuthenticationError:
                    # Invalid credentials - return 535 and close connection
                    logger.warning(
                        "Authentication failed - invalid credentials",
                        peer=session.peer,
                        username=username,
                    )
                    # Clear any partial session data
                    self._authenticated_sessions.pop(peer_key, None)
                    return "535 5.7.8 Authentication failed"

                except (ServerError, NetworkError) as e:
                    # Temporary error - return 451 to allow retry
                    logger.error(
                        "Temporary authentication failure",
                        peer=session.peer,
                        username=username,
                        error=str(e),
                    )
                    return "451 4.7.0 Temporary authentication failure, please try again"

            except ValueError as e:
                logger.warning(
                    "AUTH PLAIN parsing failed",
                    peer=session.peer,
                    error=str(e),
                )
                return "535 5.7.8 Authentication credentials invalid"

        # AUTH LOGIN
        elif mechanism == "LOGIN":
            # AUTH LOGIN is interactive - not fully implemented yet
            # This will be completed when we add proper state management
            logger.info(
                "AUTH LOGIN attempted (not yet fully implemented)",
                peer=session.peer,
            )
            return "504 5.5.4 AUTH mechanism LOGIN not implemented yet"

        else:
            logger.warning(
                "Unsupported AUTH mechanism",
                peer=session.peer,
                mechanism=mechanism,
            )
            return "504 5.5.4 AUTH mechanism not supported"

    async def handle_MAIL(
        self,
        server: SMTPProtocol,
        session: Session,
        envelope: Envelope,
        address: str,
        mail_options: list[str],
    ) -> str:
        """Handle MAIL FROM command.

        Requires authentication before accepting MAIL FROM (Story 2.3).

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Current envelope
            address: Sender email address
            mail_options: MAIL command options

        Returns:
            SMTP response string
        """
        peer_key = session.peer[0] if session.peer else "unknown"

        # Check if session is authenticated (Story 2.3)
        session_data = self._authenticated_sessions.get(peer_key)
        if not session_data or not session_data.get("authenticated"):
            logger.warning(
                "MAIL FROM rejected - authentication required",
                peer=session.peer,
                address=address,
            )
            return "530 5.7.0 Authentication required"

        # Authentication passed, allow MAIL FROM
        logger.info(
            "MAIL FROM accepted",
            peer=session.peer,
            address=address,
            username=session_data.get("username"),
        )

        # Set envelope sender
        envelope.mail_from = address
        envelope.mail_options.extend(mail_options)

        return f"250 OK"

    async def handle_RCPT(
        self,
        server: SMTPProtocol,
        session: Session,
        envelope: Envelope,
        address: str,
        rcpt_options: list[str],
    ) -> str:
        """Handle RCPT TO command.

        Accepts recipient address for authenticated sessions.

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Current envelope
            address: Recipient email address
            rcpt_options: RCPT command options

        Returns:
            SMTP response string
        """
        peer_key = session.peer[0] if session.peer else "unknown"

        # Check if session is authenticated
        session_data = self._authenticated_sessions.get(peer_key)
        if not session_data or not session_data.get("authenticated"):
            logger.warning(
                "RCPT TO rejected - authentication required",
                peer=session.peer,
                address=address,
            )
            return "530 5.7.0 Authentication required"

        # Story 3.1: Allow up to 100 recipients
        max_recipients = self.settings.max_recipients  # Default: 100
        if len(envelope.rcpt_tos) >= max_recipients:
            logger.warning(
                "Too many recipients",
                peer=session.peer,
                address=address,
                count=len(envelope.rcpt_tos),
                max=max_recipients,
            )
            return f"452 4.5.3 Too many recipients (max {max_recipients})"

        logger.info(
            "RCPT TO accepted",
            peer=session.peer,
            address=address,
            username=session_data.get("username"),
        )

        # Add recipient to envelope
        envelope.rcpt_tos.append(address)
        envelope.rcpt_options.extend(rcpt_options)

        return "250 OK"

    async def handle_DATA(
        self,
        server: SMTPProtocol,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """Handle DATA command and parse email message (Story 2.4).

        Receives email content, parses headers and body.
        Story 2.4 scope: Single recipient, plain text only.

        Args:
            server: SMTP server instance
            session: Current session
            envelope: Current envelope (contains content and recipients)

        Returns:
            SMTP response string
        """
        from smtp_gateway.email.parser import parse_email_message

        peer_key = session.peer[0] if session.peer else "unknown"

        # Check if session is authenticated
        session_data = self._authenticated_sessions.get(peer_key)
        if not session_data or not session_data.get("authenticated"):
            logger.warning(
                "DATA rejected - authentication required",
                peer=session.peer,
            )
            return "530 5.7.0 Authentication required"

        # Validate envelope has sender and recipient
        if not envelope.mail_from:
            return "503 5.5.1 Error: MAIL FROM required"

        if not envelope.rcpt_tos:
            return "503 5.5.1 Error: RCPT TO required"

        try:
            # Parse email message from envelope content
            email_data = parse_email_message(envelope.content)

            logger.info(
                "Email message parsed successfully",
                peer=session.peer,
                from_addr=email_data.get("from"),
                to_addr=email_data.get("to"),
                subject=email_data.get("subject"),
            )

            # Story 2.6: Submit email to Cakemail API
            from smtp_gateway.api.email import submit_email
            from smtp_gateway.api.errors import (
                NetworkError,
                RateLimitError,
                ServerError,
                ValidationError,
            )

            api_key = session_data.get("api_key")
            if not api_key:
                logger.error(
                    "API key missing from session",
                    peer=session.peer,
                )
                return "451 4.3.0 Internal error: missing API key"

            try:
                # Submit email to Cakemail API
                result = await submit_email(api_key, email_data)
                message_id = result.get("message_id")

                logger.info(
                    "Email forwarded to Cakemail API successfully",
                    peer=session.peer,
                    message_id=message_id,
                    from_addr=email_data.get("from"),
                    to_addr=email_data.get("to"),
                )

                return f"250 2.0.0 Message accepted for delivery: {message_id}"

            except ValidationError as e:
                # API validation error (400) - permanent failure
                logger.warning(
                    "Email rejected by Cakemail API - validation error",
                    peer=session.peer,
                    error=str(e),
                )
                return f"550 5.6.0 Message rejected: {e}"

            except RateLimitError as e:
                # Rate limit (429) - temporary failure
                logger.warning(
                    "Rate limit exceeded",
                    peer=session.peer,
                    error=str(e),
                )
                return "451 4.7.1 Rate limit exceeded, try again later"

            except ServerError as e:
                # API server error (500) - temporary failure
                logger.error(
                    "Cakemail API server error",
                    peer=session.peer,
                    error=str(e),
                )
                return "451 4.3.0 Temporary failure, try again later"

            except NetworkError as e:
                # Network error - temporary failure
                logger.error(
                    "Network error submitting to Cakemail API",
                    peer=session.peer,
                    error=str(e),
                )
                return "451 4.4.0 Service temporarily unavailable"

        except ValueError as e:
            logger.warning(
                "Email parsing failed",
                peer=session.peer,
                error=str(e),
            )
            return f"550 5.6.0 Message rejected: {e}"
