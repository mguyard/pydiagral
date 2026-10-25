"""Module providing utility functions for Diagral API."""

import hashlib
import hmac
import re
from typing import Any
from urllib.parse import urlsplit

from .constants import (
    AUTOMATISM_CANALS,
    MAX_LISTED_VALUE_LENGTH,
    REDACTED,
    SENSITIVE_KEYS,
    SENSITIVE_URL_PATH_KEYS,
    SHAPE_VISIBLE_KEYS,
)


def generate_hmac_signature(
    timestamp: str, serial_id: str, api_key: str, secret_key: str
) -> str:
    """Generate an HMAC signature for the given parameters.

    The timestamp must be the one sent in the X-TIMESTAMP header, or the API
    rejects the signature.
    """
    message: str = f"{timestamp}.{serial_id}.{api_key}"
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


# A key that names a field, not an identifier such as a serial or a UUID.
_SCHEMA_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_SCHEMA_KEY_MAX_DIGITS = 2


def schema_key(key: str) -> str:
    """Return a payload key as is when it names a field, or "<key>" when it may not.

    A key with punctuation or more than two digits may be an identifier, such as
    a serial or a UUID used to index a dict, rather than part of Diagral's schema.
    """
    digits = sum(character.isdigit() for character in key)
    if _SCHEMA_KEY.fullmatch(key) and digits <= _SCHEMA_KEY_MAX_DIGITS:
        return key
    return "<key>"


def shape(data: Any) -> Any:
    """Return the structure of a payload without the values a user could have typed.

    Keys are kept, except those that may be identifiers, which read "<key:1>",
    "<key:2>"... Text becomes "<str:N>", N being its length, unless it is a state,
    a device type or a version (`constants.SHAPE_VISIBLE_KEYS`), a documented
    automatism canal, or "True" / "False". Numbers, booleans and None are kept.

    Examples:
        >>> shape({"label": "Kitchen", "mode": "ON", "index": 2, "groups": [1]})
        {'label': '<str:7>', 'mode': 'ON', 'index': 2, 'groups': [1]}

    """
    return _shape_value(None, data)


def _shape_value(key: str | None, value: Any) -> Any:
    """Return the shape of a value stored under key."""
    if isinstance(value, dict):
        shaped: dict[str, Any] = {}
        masked = 0
        for item_key, item in value.items():
            name = schema_key(item_key) if isinstance(item_key, str) else "<key>"
            if name == "<key>":
                masked += 1
                name = f"<key:{masked}>"
            shaped[name] = _shape_value(item_key, item)
        return shaped
    if isinstance(value, list):
        return [_shape_value(key, item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if _is_technical(key, value) else f"<str:{len(value)}>"
    return f"<{type(value).__name__}>"


def _is_technical(key: str | None, value: str) -> bool:
    """Tell whether a text value is technical enough to show in a shape."""
    if len(value) > MAX_LISTED_VALUE_LENGTH:
        return False
    name = key.lower() if isinstance(key, str) else ""
    return (
        name in SHAPE_VISIBLE_KEYS
        or (name == "canal" and value.upper() in AUTOMATISM_CANALS)
        or value.lower() in ("true", "false")
    )


def redact(data: Any) -> Any:
    """Return a copy of data with the values of sensitive keys replaced, for logging.

    Dicts and lists are walked recursively; any other value is returned as is.
    """
    if isinstance(data, dict):
        return {key: _redact_value(key, value) for key, value in data.items()}
    if isinstance(data, list):
        return [redact(item) for item in data]
    return data


def _redact_value(key: Any, value: Any) -> Any:
    """Return value redacted according to the key it is stored under."""
    if not isinstance(key, str):
        return redact(value)
    if key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if key.lower() in SENSITIVE_URL_PATH_KEYS:
        return _redact_url_path(value)
    return redact(value)


def _redact_url_path(value: Any) -> str:
    """Keep the scheme and host of a URL and replace the rest; redact anything else entirely."""
    if isinstance(value, str):
        parts = urlsplit(value)
        # hostname and port, not netloc, which may carry user:password@.
        if parts.scheme and parts.hostname:
            port = f":{parts.port}" if parts.port else ""
            return f"{parts.scheme}://{parts.hostname}{port}/{REDACTED}"
    return REDACTED


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
