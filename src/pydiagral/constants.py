"""Constants for the Diagral API integration."""

BASE_URL = "https://appv3.tt-monitor.com/emerald"
API_VERSION = "v1"

# Brands sharing the Emerald cloud, as the login endpoint names them.
VENDORS = ("DIAGRAL", "DAITEM", "EDAITEM", "LOGISTYALMA", "DISTRIBUTION")
DEFAULT_VENDOR = "DIAGRAL"

# From the OpenAPI specification: the mode an automatism is configured with, the
# actions it accepts (they add OFF; how the two relate is not documented), and the
# canals that address it.
AUTOMATISM_MODES = ("ON", "PULSE", "SWITCH", "TIMER")
AUTOMATISM_ACTIONS = ("PULSE", "OFF", "ON", "SWITCH", "TIMER")
AUTOMATISM_CANALS = (
    "LUMIERE_1",
    "RELAIS_1",
    "RELAIS_2",
    "RELAIS_3",
    "RELAIS_4",
    "RELAIS_1_CENTRALE",
    "RELAIS_2_CENTRALE",
)

# Seconds allowed for a whole request (connection, sending, response).
DEFAULT_REQUEST_TIMEOUT = 30

# Where the models ask users to report a payload they do not fit.
ISSUES_URL = "https://github.com/mguyard/pydiagral/issues"

# Entries `models.unexpected_data()` keeps: webhooks are external input, and a
# forged one must not grow the registry without bound.
MAX_UNEXPECTED_DATA = 100
# Longest value from a documented list that the registry copies as is.
MAX_LISTED_VALUE_LENGTH = 32
# Keys whose text values `utils.shape()` shows: states, device types and
# versions, never text a user typed. Compared lowercase.
SHAPE_VISIBLE_KEYS = frozenset(
    {
        "box",
        "boxradio",
        "central",
        "centralradio",
        "devicetype",
        "firmwareversion",
        "ipodaversion",
        "mode",
        "plug",
        "plugknx",
        "status",
        "type",
        "vendor",
    }
)

# Header and field names whose values are replaced by REDACTED in debug logs.
# Compared lowercase.
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "api_keys",
        "authorization",
        "password",
        "pincode",
        "secret_key",
        "serial",
        "serial_id",
        "transmitter_id",
        "username",
        "x-apikey",
        "x-hmac",
        "x-pin-code",
    }
)
# URL fields whose path is a secret (a webhook id lets anyone post forged
# events): the scheme and host are kept, the path is replaced by REDACTED.
SENSITIVE_URL_PATH_KEYS = frozenset({"webhook_url"})
REDACTED = "**REDACTED**"
