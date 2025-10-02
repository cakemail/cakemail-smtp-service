"""Cakemail Email API integration."""

from typing import Dict, Optional

import httpx
import structlog

from smtp_gateway.api.errors import (
    NetworkError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from smtp_gateway.config import get_settings


logger = structlog.get_logger()


async def submit_email(
    api_key: str,
    email_data: Dict,
) -> Dict:
    """Submit email to Cakemail Email API.

    Story 2.5: Single recipient support
    Story 3.1: Multiple recipient support with per-recipient API calls

    Args:
        api_key: Authenticated API key from session
        email_data: Parsed email data with keys:
            - from: str
            - to: List[str]
            - cc: List[str]
            - bcc: List[str]
            - subject: str
            - body_text: str
            - body_html: Optional[str]

    Returns:
        Dictionary with:
        {
            "message_id": str or List[str],  # Message ID(s)
            "status": "accepted",
            "recipients": {
                "succeeded": List[str],
                "failed": List[Dict]
            }
        }

    Raises:
        ValidationError: If all recipients fail validation
        RateLimitError: If API returns 429 (rate limit)
        ServerError: If API returns 5xx (server error)
        NetworkError: If network/timeout error occurs
    """
    settings = get_settings()

    # Collect all recipients (Story 3.1)
    all_recipients = []
    all_recipients.extend(email_data.get("to", []))
    all_recipients.extend(email_data.get("cc", []))
    all_recipients.extend(email_data.get("bcc", []))

    if not all_recipients:
        raise ValidationError("No recipients specified")

    # For Story 3.1: Make individual API call per recipient
    # (Some APIs require per-recipient submission)
    succeeded_recipients = []
    failed_recipients = []
    message_ids = []

    # Configure httpx client with timeout
    timeout = httpx.Timeout(10.0, connect=10.0)

    # Submit email to each recipient individually
    for recipient_email in all_recipients:
        result = await _submit_to_single_recipient(
            api_key=api_key,
            email_data=email_data,
            recipient_email=recipient_email,
            timeout=timeout,
            settings=settings,
        )

        if result["status"] == "success":
            succeeded_recipients.append(recipient_email)
            message_ids.append(result["message_id"])
        else:
            failed_recipients.append({
                "email": recipient_email,
                "error": result["error"],
            })

    # Check if all recipients failed
    if not succeeded_recipients:
        # All failed - raise ValidationError with details
        error_summary = "; ".join([f"{r['email']}: {r['error']}" for r in failed_recipients])
        raise ValidationError(f"All recipients failed: {error_summary}")

    # At least one succeeded
    logger.info(
        "Email submitted with partial or full success",
        succeeded=len(succeeded_recipients),
        failed=len(failed_recipients),
        message_ids=message_ids,
    )

    return {
        "message_id": message_ids[0] if len(message_ids) == 1 else message_ids,
        "status": "accepted",
        "recipients": {
            "succeeded": succeeded_recipients,
            "failed": failed_recipients,
        },
    }


async def _submit_to_single_recipient(
    api_key: str,
    email_data: Dict,
    recipient_email: str,
    timeout: httpx.Timeout,
    settings,
) -> Dict[str, str]:
    """Submit email to a single recipient.

    Story 3.1: Helper function to make per-recipient API calls.

    Args:
        api_key: API key
        email_data: Email data
        recipient_email: Single recipient email address
        timeout: HTTP timeout
        settings: App settings

    Returns:
        {
            "status": "success" or "failed",
            "message_id": str (if success),
            "error": str (if failed)
        }
    """
    # Build API payload for single recipient
    api_payload = {
        "from": {
            "email": email_data["from"],
        },
        "to": [
            {"email": recipient_email},
        ],
        "subject": email_data["subject"],
        "text": email_data["body_text"],
    }

    # Add HTML if present (Story 3.2)
    if email_data.get("body_html"):
        api_payload["html"] = email_data["body_html"]

    # Add attachments if present (Story 3.4)
    if email_data.get("attachments"):
        api_payload["attachments"] = email_data["attachments"]

    # Single retry on network error
    max_attempts = 2
    last_error: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.debug(
                    "Submitting email to Cakemail API",
                    from_addr=email_data["from"],
                    to_addr=email_data["to"],
                    attempt=attempt + 1,
                )

                response = await client.post(
                    f"{settings.cakemail_api_url}/email",
                    json=api_payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

                # Success case: 200 or 202
                if response.status_code in (200, 202):
                    data = response.json()
                    message_id = data.get("message_id") or data.get("id")

                    if not message_id:
                        logger.error(
                            "API returned success but no message_id",
                            response_data=data,
                            recipient=recipient_email,
                        )
                        return {"status": "failed", "error": "Invalid API response: missing message_id"}

                    logger.info(
                        "Email submitted successfully",
                        message_id=message_id,
                        from_addr=email_data["from"],
                        to_addr=email_data["to"],
                    )

                    return {
                        "status": "success",
                        "message_id": message_id,
                    }

                # Validation error (don't retry) - Story 3.1: return error, don't raise
                elif response.status_code == 400:
                    data = response.json()
                    error_msg = data.get("error") or data.get("message") or "Validation error"
                    logger.warning(
                        "Email validation failed for recipient",
                        recipient=recipient_email,
                        status_code=response.status_code,
                        error=error_msg,
                    )
                    return {"status": "failed", "error": error_msg}

                # Rate limit - Story 3.1: raise (affects all recipients)
                elif response.status_code == 429:
                    logger.warning(
                        "Rate limit exceeded",
                        from_addr=email_data["from"],
                    )
                    raise RateLimitError("Rate limit exceeded, try again later")

                # Server errors - Story 3.1: return error for this recipient
                elif response.status_code >= 500:
                    error_msg = f"API server error: {response.status_code}"
                    logger.error(
                        "API server error for recipient",
                        recipient=recipient_email,
                        status_code=response.status_code,
                    )
                    return {"status": "failed", "error": error_msg}

                # Other client errors
                else:
                    error_msg = f"Unexpected API response: {response.status_code}"
                    logger.warning(
                        "Unexpected API response for recipient",
                        recipient=recipient_email,
                        status_code=response.status_code,
                    )
                    return {"status": "failed", "error": error_msg}

        except httpx.TimeoutException as e:
            error_msg = f"API request timeout: {e}"
            logger.warning(
                "API request timeout for recipient",
                recipient=recipient_email,
                error=str(e),
                attempt=attempt + 1,
            )
            last_error = error_msg

            # Retry on timeout
            if attempt < max_attempts - 1:
                continue
            else:
                return {"status": "failed", "error": last_error}

        except httpx.RequestError as e:
            error_msg = f"Network error: {e}"
            logger.warning(
                "Network error for recipient",
                recipient=recipient_email,
                error=str(e),
                attempt=attempt + 1,
            )
            last_error = error_msg

            # Retry on network error
            if attempt < max_attempts - 1:
                continue
            else:
                return {"status": "failed", "error": last_error}

        except (RateLimitError, NetworkError) as e:
            # Re-raise errors that affect all recipients
            raise

    # Should never reach here
    return {"status": "failed", "error": "Unknown error"}
