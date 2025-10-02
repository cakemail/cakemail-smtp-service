"""API error classes and handling."""

# Placeholder for API errors (Epic 2)


class APIError(Exception):
    """Base class for API errors."""

    pass


class AuthenticationError(APIError):
    """Authentication failed."""

    pass


class ValidationError(APIError):
    """Request validation failed."""

    pass


class RateLimitError(APIError):
    """Rate limit exceeded."""

    pass


class ServerError(APIError):
    """Server error occurred."""

    pass


class NetworkError(APIError):
    """Network error occurred."""

    pass
