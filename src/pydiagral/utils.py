"""Module providing utility functions for Diagral API."""

import hashlib
import hmac
import time


def generate_hmac_signature(
    timestamp: str, serial_id: str, api_key: str, secret_key: str
) -> str:
    """Generate an HMAC signature for the given parameters."""
    timestamp = str(int(time.time()))
    message = f"{timestamp}.{serial_id}.{api_key}"
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
