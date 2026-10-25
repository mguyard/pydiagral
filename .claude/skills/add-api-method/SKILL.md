---
name: add-api-method
description: Add or change a DiagralAPI method in pydiagral — endpoint, HMAC headers, response model with aliases, public exports, tests mocking _request(), and the hass-diagral compatibility check. Use for "add method", "new endpoint", "implement API call", "add support for".
---

# Add an API Method — pydiagral

Use this skill to add a `DiagralAPI` method for a Diagral endpoint, or to change an existing one. The rules it applies are in `AGENTS.md` → Invariants and Contracts.

---

## 1. Gather First

1. **Endpoint**: HTTP method and path relative to `{BASE_URL}/{API_VERSION}/` — e.g. `systems/{serial_id}/status`, `webhooks/{serial_id}/subscription`.
2. **Authentication**: bearer token (`login()` first — the API key endpoints), or HMAC with or without `X-PIN-CODE` (the system endpoints).
3. **Request body** and **response schema**, with the exact JSON key names.
4. **Error responses** worth translating into a clearer exception.
5. **Python name** in snake_case.

If the user cannot provide the schema, look for the endpoint in an existing method before guessing. Never call the real API to find out.

---

## 2. Response Model (`models.py`)

```python
@dataclass
class ZoneStatus(CamelCaseModel):
    """Status of a zone.

    Attributes:
        zone_id (int | None): The zone identifier, aliased as "zoneId".
        label (str | None): The zone label.

    """

    zone_id: int | None = field(default=None, metadata={"alias": "zoneId"})
    label: str | None = None
```

- **Every field whose API key differs from the Python name needs an `alias`** — including plain camelCase. `from_dict()` matches the field name or alias case-insensitively and does not convert snake_case to camelCase; a missing alias leaves the field `None` with no error.
- Nested models and `list[Model]` are converted recursively from the type hints.
- Fields are `X | None = None` unless the API always returns them.
- Document each field under `Attributes:` — mkdocstrings publishes it.

---

## 3. Method (`api.py`)

The HMAC pattern, as `get_system_status()` does it:

```python
async def get_zone_status(self) -> ZoneStatus:
    """Asynchronously retrieve the zone status.

    Returns:
        ZoneStatus: The status of the zone.

    Raises:
        AuthenticationError: If the API key, secret key or PIN code is not provided.

    """
    if not self.__apikey or not self.__secret_key:
        raise AuthenticationError("API key and secret key required to get zone status")
    if not self.__pincode:
        raise AuthenticationError("PIN code required to get zone status")

    _TIMESTAMP = str(int(time.time()))
    _HMAC: str = generate_hmac_signature(
        timestamp=_TIMESTAMP,
        serial_id=self.serial_id,
        api_key=self.__apikey,
        secret_key=self.__secret_key,
    )
    _HEADERS: dict[str, str] = {
        "X-PIN-CODE": self.__pincode,
        "X-HMAC": _HMAC,
        "X-TIMESTAMP": _TIMESTAMP,
        "X-APIKEY": self.__apikey,
    }
    response_data, *_ = await self._request(
        "GET", f"systems/{self.serial_id}/zones", headers=_HEADERS
    )
    return ZoneStatus.from_dict(response_data)
```

- **`_request()` returns `(body, status)`** — unpack it.
- Never log `_HEADERS`, and never log the response at a level above `debug` if it carries personal data.
- Missing credentials raise `AuthenticationError` in most methods; a few older ones raise `ConfigurationError`. Use `AuthenticationError` for new methods, and leave the old ones alone — changing the type breaks callers' `except` clauses.
- Translating an API error: catch `DiagralAPIError`, match on the server message, re-raise with `from err`, and **re-raise everything else**. A bare `except` that falls through leaves `response_data` unbound.
- Keep the annotation true to what is returned.

---

## 4. Exports (`__init__.py`)

`__all__` exports only `DiagralAPI`, the main exceptions and `ApiKeyWithSecret`. Consumers — hass-diagral included — import models from `pydiagral.models` directly, so a new model needs no export. Add one to `__all__` only if it is meant as top-level API.

---

## 5. Tests (`tests/test_pydiagral_api.py`)

Follow `testing-pydiagral`. At minimum, per method:

- the nominal path, asserting on the returned model **and on the request made** (method, endpoint, headers present);
- each credential precondition (`..._without_apikey`, `..._without_pincode`);
- each API error the method translates.

---

## 6. Changing an Existing Method

Before renaming, removing or changing the signature, return type, exception type or error message of a public method or model, check `AGENTS.md` → Contracts and search hass-diagral:

```bash
gh search code --repo mguyard/hass-diagral "<method_or_symbol>"
```

A change it depends on is a breaking change: `BREAKING CHANGE:` footer, and a coordinated hass-diagral update.

---

## 7. Done When

- [ ] Model with aliases for every renamed key, documented under `Attributes:`
- [ ] Method through `_request()`, Google docstring, accurate annotation, no secret logged
- [ ] Tests: nominal with request assertion, preconditions, error paths
- [ ] `ruff check .`, `ruff format --check .` and `mypy` clean
- [ ] `pytest` green
- [ ] `docs/index.md` / `README.md` feature list updated if the capability is user-visible (see `docs-pydiagral`)
