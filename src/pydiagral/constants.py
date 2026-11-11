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
        "refcode",
        "status",
        "type",
        "vendor",
    }
)
# Besides SENSITIVE_KEYS, key fragments whose values `utils.shape()` hides whatever
# their type: the raw JSON may send a serial or a phone number as a number.
SHAPE_HIDDEN_KEY_PARTS = ("serial", "phone", "vocal", "contact")
# Longest integer `utils.shape()` shows: indexes, groups, delays and counters fit,
# identifiers, timestamps and phone numbers do not.
MAX_SHAPE_INT_DIGITS = 6

# Header and field names whose values are replaced by REDACTED in debug logs.
# Compared lowercase.
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "api_keys",
        "authorization",
        "password",
        "mastercode",
        "ttmsessionid",
        "sessionid",
        "centralid",
        "transmitterid",
        "systemid",
        "radioid",
        "cryptkey",
        "encryptionkey",
        "privatekey",
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

# Emergency path: short sessions, bounded inventory polling, no command retry.
TOPAZE_REQUEST_TIMEOUT = 8
TOPAZE_CLEANUP_TIMEOUT = 3
TOPAZE_INVENTORY_TIMEOUT = 18
TOPAZE_INVENTORY_POLL_INTERVAL = 1
TOPAZE_CONFIGURATION_TTL = 3600
TOPAZE_BASE_URL = "https://appv3.tt-monitor.com/topaze"
TOPAZE_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json;charset=UTF-8",
    "X-App-Version": "1.12.1",
    "X-Identity-Provider": "JANRAIN",
    "ttmSessionIdNotRequired": "true",
    "X-Vendor": "diagral",
}

STATUS_OFF = "off"
STATUS_GROUP = "group"
STATUS_PRESENCE = "presence"
STATUS_TEMPO_GROUP = "tempo_group"

# Probe actual Emerald reads before using the alternate cloud service.
FAILOVER_PRIMARY_TIMEOUT = 10
FAILOVER_TOPAZE_TIMEOUT = 120
API_EMERALD = "emerald"
API_TOPAZE = "topaze"
