class SplunkOllyError(Exception):
    """Base error for this package."""


class ApiError(SplunkOllyError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ApiError):
    """401/403 - token missing, invalid, expired or lacking API scope."""


class NotFoundError(ApiError):
    """404 - resource does not exist."""


class RateLimitError(ApiError):
    """429 - still throttled after retries."""


class SignalFlowError(ApiError):
    """SignalFlow program failed to compile or execute."""
