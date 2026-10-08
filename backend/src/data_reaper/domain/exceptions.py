"""The `AppException` hierarchy for every controlled error.

The API layer's single exception handler maps `status_code` straight to
the HTTP response, so each subclass fixes a sensible default.
"""


class AppException(Exception):
    """Base of every controlled error.

    Attributes:
        message: Human-readable summary, safe to return to clients.
        status_code: HTTP status the API layer responds with.
    """

    message: str
    status_code: int

    def __init__(self, message: str, status_code: int) -> None:
        """Store the message and HTTP status."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ValidationException(AppException):
    """A client-caused error: bad input, missing, or denied."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Default to HTTP 400; pass 401/403/404/409 as needed."""
        super().__init__(message, status_code)


class ConfigurationException(AppException):
    """A required setting is missing or invalid; fails at startup."""

    def __init__(self, message: str) -> None:
        """Always HTTP 500: the deployment is at fault."""
        super().__init__(message, 500)


class ExternalServiceException(AppException):
    """An upstream service, including the database, failed."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        """Default to HTTP 502."""
        super().__init__(message, status_code)


class InvalidRowException(ValidationException):
    """One CSV row can't be imported.

    A required value is missing, or a value isn't of its column's type.
    Only this row is rejected; the import goes on with the next one and
    records the reason (CONTRIBUTING R1.6.5).
    """

    def __init__(self, reason: str) -> None:
        """Always HTTP 422; the reason names the column at fault."""
        super().__init__(reason, 422)
