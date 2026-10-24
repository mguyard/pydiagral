"""Module providing utility functions for Diagral API."""

import hashlib
import hmac


def generate_hmac_signature(
    timestamp: str, serial_id: str, api_key: str, secret_key: str
) -> str:
    """Generate an HMAC signature for the given parameters.

    The timestamp must be the one sent in the X-TIMESTAMP header, or the API
    rejects the signature.
    """
    message: str = f"{timestamp}.{serial_id}.{api_key}"
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
