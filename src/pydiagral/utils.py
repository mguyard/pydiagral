"""Module providing utility functions for Diagral API."""

import hashlib
import hmac
from typing import Any

from .constants import REDACTED, SENSITIVE_KEYS


def generate_hmac_signature(
    timestamp: str, serial_id: str, api_key: str, secret_key: str
) -> str:
    """Generate an HMAC signature for the given parameters.

    The timestamp must be the one sent in the X-TIMESTAMP header, or the API
    rejects the signature.
    """
    message: str = f"{timestamp}.{serial_id}.{api_key}"
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def redact(data: Any) -> Any:
    """Return a copy of data with the values of sensitive keys replaced, for logging.

    Dicts and lists are walked recursively; any other value is returned as is.
    """
    if isinstance(data, dict):
        return {
            key: REDACTED
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS
            else redact(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact(item) for item in data]
    return data


class Redacted:
    """Wrap data so that it is redacted only when a log record is formatted.

    Pass it as a logging argument: the copy is skipped when DEBUG is disabled.
    """

    __slots__ = ("data",)

    def __init__(self, data: Any) -> None:
        """Store the data to redact."""
        self.data = data

    def __str__(self) -> str:
        """Return the redacted data as a string."""
        return str(redact(self.data))

    __repr__ = __str__
