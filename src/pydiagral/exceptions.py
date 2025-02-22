"""Module defining custom exceptions for the Diagral API."""


class DiagralAPIError(Exception):
    """Base exception for Diagral API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the DiagralAPIError.

        :param message: The error message.
        :param status_code: The status code of the error, if any.
        """
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ConfigurationError(DiagralAPIError):
    """Raised when configuration is invalid."""


class SessionError(DiagralAPIError):
    """Raised when session is invalid."""


class AuthenticationError(DiagralAPIError):
    """Raised when authentication fails."""


class ValidationError(DiagralAPIError):
    """Raised when validation fails."""


class ServerError(DiagralAPIError):
    """Raised when server returns 5xx error."""


class ClientError(DiagralAPIError):
    """Raised when client returns error."""
