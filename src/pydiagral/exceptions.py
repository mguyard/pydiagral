"""Module defining custom exceptions for the Diagral API."""


class DiagralAPIError(Exception):
    """Base exception for Diagral API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the DiagralAPIError.

        Args:
            message (str): The error message.
            status_code (int | None): The status code of the error, if any.

        """
        self.message: str = message
        self.status_code: int | None = status_code
        super().__init__(self.message)


class ConfigurationError(DiagralAPIError):
    """Raised when configuration is invalid."""


class SessionError(DiagralAPIError):
    """Raised when session is invalid."""


class AuthenticationError(DiagralAPIError):
    """Raised when authentication fails."""


class PinCodeError(AuthenticationError):
    """Raised when Diagral rejects the PIN code.

    Diagral answers a wrong PIN with the same 401 as any other credential, so
    this is inferred: only `try_connection()` raises it, when the API key it
    has just created and validated is refused on the first call sending the PIN.
    """


class ValidationError(DiagralAPIError):
    """Raised when validation fails."""


class ModelValidationError(ValidationError, ValueError):
    """Raised when data does not satisfy a model's constraints.

    Also a ValueError, which is what model validation raised before.
    """


class ServerError(DiagralAPIError):
    """Raised when server returns 5xx error."""


class ClientError(DiagralAPIError):
    """Raised when client returns error."""


class APIKeyCreationError(DiagralAPIError):
    """Raised when API key creation fails."""


class APIValidationError(DiagralAPIError):
    """Raised when API validation fails."""
