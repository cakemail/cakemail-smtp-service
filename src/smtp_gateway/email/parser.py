"""Email message parsing (MIME, headers, attachments)."""

import base64
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses
from typing import Dict, List, Optional

import structlog


logger = structlog.get_logger()


def _decode_header(header_value: Optional[str]) -> str:
    """Decode email header value (handles RFC 2047 encoding).

    Args:
        header_value: Raw header value (may be encoded)

    Returns:
        Decoded string value
    """
    if not header_value:
        return ""

    try:
        # decode_header returns list of (bytes, charset) tuples
        # make_header reassembles them into a single string
        return str(make_header(decode_header(header_value)))
    except Exception:
        # If decoding fails, return as-is
        return str(header_value)


def _extract_recipients(msg: Message, header_name: str) -> List[str]:
    """Extract email addresses from To, Cc, or Bcc headers.

    Story 3.1: Parse multiple recipients from email headers.

    Args:
        msg: Parsed email message
        header_name: Header name (To, Cc, or Bcc)

    Returns:
        List of email addresses (just addresses, not names)
    """
    header_value = msg.get(header_name, "")
    if not header_value:
        return []

    # getaddresses parses "Name <email@example.com>" format
    # Returns list of (name, email) tuples
    addresses = getaddresses([header_value])

    # Extract just the email addresses, filter out empty ones
    return [email for name, email in addresses if email]


def parse_email_message(raw_content: bytes) -> Dict:
    """Parse SMTP email message into structured format.

    Story 2.4: Simple single-part plain text emails
    Story 3.1: Multiple recipients (To, CC, BCC)

    Args:
        raw_content: Raw email message bytes from DATA command

    Returns:
        Dictionary with parsed email data:
        {
            "from": str,              # Sender email address
            "to": List[str],          # To recipients (Story 3.1)
            "cc": List[str],          # CC recipients (Story 3.1)
            "bcc": List[str],         # BCC recipients (Story 3.1)
            "subject": str,           # Email subject
            "body_text": str,         # Plain text body
            "body_html": Optional[str]  # HTML body (Story 3.2)
        }

    Raises:
        ValueError: If email is malformed or missing required fields
    """
    try:
        # Parse email using Python's email.parser
        msg: Message = message_from_bytes(raw_content)

        # Extract sender (required)
        from_addr = _decode_header(msg.get("From"))
        if not from_addr:
            raise ValueError("Missing required header: From")

        # Extract recipients (Story 3.1: multiple recipients)
        to_recipients = _extract_recipients(msg, "To")
        cc_recipients = _extract_recipients(msg, "Cc")
        bcc_recipients = _extract_recipients(msg, "Bcc")

        # At least one recipient required
        if not to_recipients and not cc_recipients and not bcc_recipients:
            raise ValueError("At least one recipient required (To, Cc, or Bcc)")

        # Extract subject
        subject = _decode_header(msg.get("Subject", ""))

        # Extract body content (Story 3.2: both text and HTML)
        body_text = _extract_plain_text_body(msg)
        body_html = _extract_html_body(msg)

        # Extract attachments (Story 3.4)
        attachments = _extract_attachments(msg)

        # Extract advanced headers (Story 3.5)
        reply_to = _decode_header(msg.get("Reply-To", ""))
        message_id = msg.get("Message-ID", "")
        date = msg.get("Date", "")

        # Extract custom X-* headers (Story 3.5)
        custom_headers = {}
        for header_name, header_value in msg.items():
            if header_name.startswith("X-"):
                custom_headers[header_name] = _decode_header(header_value)

        logger.debug(
            "Email parsed successfully",
            from_addr=from_addr,
            to_count=len(to_recipients),
            cc_count=len(cc_recipients),
            bcc_count=len(bcc_recipients),
            subject=subject,
            body_length=len(body_text) if body_text else 0,
            attachment_count=len(attachments),
        )

        return {
            "from": from_addr,
            "to": to_recipients,
            "cc": cc_recipients,
            "bcc": bcc_recipients,
            "subject": subject,
            "body_text": body_text or "",
            "body_html": body_html,
            "attachments": attachments,
            "reply_to": reply_to,
            "message_id": message_id,
            "date": date,
            "custom_headers": custom_headers,
        }

    except Exception as e:
        logger.error("Failed to parse email message", error=str(e))
        raise ValueError(f"Invalid email format: {e}")


def _extract_plain_text_body(msg: Message) -> Optional[str]:
    """Extract plain text body from email message.

    Story 2.4 scope: Single-part plain text only.
    Story 3.2: Added multipart/alternative support.

    Args:
        msg: Parsed email message

    Returns:
        Plain text body content, or None if not found
    """
    # For single-part messages, get the payload directly
    if not msg.is_multipart():
        content_type = msg.get_content_type()

        # Accept text/plain
        if content_type == "text/plain":
            payload = msg.get_payload(decode=True)
            if payload:
                # Decode bytes to string
                charset = msg.get_content_charset() or "utf-8"
                try:
                    return payload.decode(charset, errors="replace")
                except (UnicodeDecodeError, LookupError):
                    # Fallback to utf-8 if charset is invalid
                    return payload.decode("utf-8", errors="replace")
        else:
            logger.debug(
                "Non-text/plain single-part message",
                content_type=content_type,
            )
            return None
    else:
        # Story 3.2: Handle multipart/alternative messages
        # Walk through parts to find text/plain
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not part.is_multipart():
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset, errors="replace")
                    except (UnicodeDecodeError, LookupError):
                        return payload.decode("utf-8", errors="replace")

    return None


def _extract_html_body(msg: Message) -> Optional[str]:
    """Extract HTML body from email message.

    Story 3.2: Extract HTML from multipart/alternative messages.

    Args:
        msg: Parsed email message

    Returns:
        HTML body content, or None if not found
    """
    # For single-part HTML messages
    if not msg.is_multipart():
        content_type = msg.get_content_type()
        if content_type == "text/html":
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    return payload.decode(charset, errors="replace")
                except (UnicodeDecodeError, LookupError):
                    return payload.decode("utf-8", errors="replace")
    else:
        # Multipart: walk through parts to find text/html
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html" and not part.is_multipart():
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset, errors="replace")
                    except (UnicodeDecodeError, LookupError):
                        return payload.decode("utf-8", errors="replace")

    return None


def _extract_attachments(msg: Message) -> List[Dict]:
    """Extract file attachments from email message.

    Story 3.4: Extract MIME attachments and base64 encode for API.

    Args:
        msg: Parsed email message

    Returns:
        List of attachment dictionaries with:
        {
            "filename": str,
            "content_type": str,
            "content": str (base64 encoded),
            "size": int (bytes)
        }
    """
    attachments = []

    for part in msg.walk():
        # Skip multipart containers
        if part.is_multipart():
            continue

        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition", "")

        # Check if this is an attachment
        # Attachments have Content-Disposition: attachment or inline with filename
        # OR they are non-text content types (images, application/*, etc.)
        is_attachment = (
            "attachment" in content_disposition.lower()
            or "inline" in content_disposition.lower()
            or (
                content_type not in ("text/plain", "text/html")
                and part.get_filename() is not None
            )
        )

        if is_attachment:
            filename = part.get_filename()
            if filename:
                # Decode filename if encoded
                filename = _decode_header(filename)

                # Get payload
                payload = part.get_payload(decode=True)
                if payload:
                    # Base64 encode for API (Story 3.4)
                    content_b64 = base64.b64encode(payload).decode("ascii")

                    attachments.append({
                        "filename": filename,
                        "content_type": content_type,
                        "content": content_b64,
                        "size": len(payload),
                    })

                    logger.debug(
                        "Extracted attachment",
                        filename=filename,
                        content_type=content_type,
                        size=len(payload),
                    )

    return attachments
