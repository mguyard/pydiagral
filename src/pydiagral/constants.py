"""Constants for the Diagral API integration."""

BASE_URL = "https://appv3.tt-monitor.com/emerald"
API_VERSION = "v1"

# Header and field names whose values are replaced by REDACTED in debug logs.
# Compared lowercase.
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "password",
        "pincode",
        "secret_key",
        "x-apikey",
        "x-hmac",
        "x-pin-code",
    }
)
REDACTED = "**REDACTED**"
