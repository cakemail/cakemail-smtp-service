"""Cakemail Authentication API integration."""

import asyncio
from typing import Optional

import httpx
import structlog

from smtp_gateway.api.errors import (
    AuthenticationError,
    NetworkError,
    ServerError,
)
from smtp_gateway.config import get_settings


logger = structlog.get_logger()


async def validate_credentials(username: str, password: str) -> str:
    """Validate SMTP credentials against Cakemail Authentication API.

    This function implements Story 2.2 requirements:
    - Calls Cakemail auth endpoint with username/password
    - Returns API key on success
    - Raises AuthenticationError on auth failure (401, 403)
    - Implements retry logic with exponential backoff (2 retries)
    - Times out after 5 seconds per request

    Args:
        username: SMTP username (email address)
        password: SMTP password

    Returns:
        API key string on successful authentication

    Raises:
        AuthenticationError: If credentials are invalid (401, 403)
        ServerError: If API returns 5xx error after retries
        NetworkError: If network/timeout error occurs after retries
    """
    settings = get_settings()

    # Configure httpx client with timeout and retries
    timeout = httpx.Timeout(5.0, connect=5.0)

    # Retry configuration: 2 retries with exponential backoff
    max_retries = settings.api_max_retries
    retry_delays = [0.5, 1.0]  # Exponential backoff: 500ms, 1s

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):  # Initial attempt + 2 retries = 3 total
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.debug(
                    "Validating credentials with Cakemail API",
                    username=username,
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1,
                )

                response = await client.post(
                    f"{settings.cakemail_auth_url}/validate",
                    json={"username": username, "password": password},
                    headers={"Content-Type": "application/json"},
                )

                # Success case: 200 OK
                if response.status_code == 200:
                    data = response.json()
                    api_key = data.get("api_key")

                    if not api_key:
                        logger.error(
                            "API returned 200 but no api_key in response",
                            response_data=data,
                        )
                        raise ServerError("Invalid API response: missing api_key")

                    logger.info(
                        "Credentials validated successfully",
                        username=username,
                    )
                    return api_key

                # Authentication failures (don't retry)
                elif response.status_code in (401, 403):
                    logger.warning(
                        "Authentication failed",
                        username=username,
                        status_code=response.status_code,
                    )
                    raise AuthenticationError(
                        f"Invalid credentials for {username}"
                    )

                # Server errors (retry)
                elif response.status_code >= 500:
                    error_msg = f"API server error: {response.status_code}"
                    logger.warning(
                        "API server error, will retry",
                        status_code=response.status_code,
                        attempt=attempt + 1,
                    )
                    last_error = ServerError(error_msg)

                    # Retry with exponential backoff
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delays[attempt])
                        continue
                    else:
                        raise last_error

                # Other client errors (don't retry)
                else:
                    logger.warning(
                        "Unexpected API response",
                        status_code=response.status_code,
                        username=username,
                    )
                    raise ServerError(
                        f"Unexpected API response: {response.status_code}"
                    )

        except httpx.TimeoutException as e:
            error_msg = f"API request timeout: {e}"
            logger.warning(
                "API request timeout, will retry",
                error=str(e),
                attempt=attempt + 1,
            )
            last_error = NetworkError(error_msg)

            # Retry with exponential backoff
            if attempt < max_retries:
                await asyncio.sleep(retry_delays[attempt])
                continue
            else:
                raise last_error

        except httpx.RequestError as e:
            error_msg = f"Network error: {e}"
            logger.warning(
                "Network error, will retry",
                error=str(e),
                attempt=attempt + 1,
            )
            last_error = NetworkError(error_msg)

            # Retry with exponential backoff
            if attempt < max_retries:
                await asyncio.sleep(retry_delays[attempt])
                continue
            else:
                raise last_error

        except (AuthenticationError, ServerError) as e:
            # Re-raise auth/server errors without retry
            raise

    # Should never reach here, but just in case
    if last_error:
        raise last_error
    raise NetworkError("Authentication request failed after all retries")
