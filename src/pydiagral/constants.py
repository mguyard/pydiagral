"""Constants for the Diagral API integration."""

BASE_URL = "https://appv3.tt-monitor.com/emerald"
API_VERSION = "v1"

# Brands sharing the Emerald cloud, as the login endpoint names them.
VENDORS = ("DIAGRAL", "DAITEM", "EDAITEM", "LOGISTYALMA", "DISTRIBUTION")
DEFAULT_VENDOR = "DIAGRAL"

# Seconds allowed for a whole request (connection, sending, response).
DEFAULT_REQUEST_TIMEOUT = 30

# Where the models ask users to report a payload they do not fit.
ISSUES_URL = "https://github.com/mguyard/pydiagral/issues"

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
# URL fields whose path is a secret (a webhook id lets anyone post forged
# events): the scheme and host are kept, the path is replaced by REDACTED.
SENSITIVE_URL_PATH_KEYS = frozenset({"webhook_url"})
REDACTED = "**REDACTED**"
