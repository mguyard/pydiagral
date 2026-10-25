"""Module for interacting with the Diagral API.

This module provides a DiagralAPI class that encapsulates all the functionality
for communicating with the Diagral alarm system API, including authentication,
retrieving system status, and controlling various aspects of the alarm system.
"""

from __future__ import annotations

import logging
import math
import re
import time
from typing import Any, Literal, Self, overload

import aiohttp

from .constants import (
    API_VERSION,
    BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_VENDOR,
    REDACTED,
    VENDORS,
)
from .exceptions import (
    APIKeyCreationError,
    APIValidationError,
    AuthenticationError,
    ClientError,
    ConfigurationError,
    DiagralAPIError,
    ModelValidationError,
    PinCodeError,
    ServerError,
    SessionError,
    ValidationError,
)
from .models import (
    AlarmConfiguration,
    Anomalies,
    ApiKeys,
    ApiKeyWithSecret,
    DeviceList,
    LoginResponse,
    Ping,
    Rudes,
    SystemApiKeys,
    SystemDetails,
    SystemStatus,
    TryConnectResult,
    Webhook,
)
from .utils import Redacted, generate_hmac_signature

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Minimum Python version: 3.11


class DiagralAPI:
    """Provide interface for interacting with the Diagral API.

    This class encapsulates all the functionality for communicating with
    the Diagral alarm system API, including authentication, retrieving
    system status, and controlling various aspects of the alarm system.
    """

    def __init__(
        self,
        username: str,
        password: str,
        serial_id: str | None = None,
        apikey: str | None = None,
        secret_key: str | None = None,
        pincode: str | None = None,
        *,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        session: aiohttp.ClientSession | None = None,
        vendor: str = DEFAULT_VENDOR,
    ) -> None:
        """Initialize the DiagralAPI instance.

        Args:
            username (str): The email address for Diagral API authentication.
            password (str): The password for Diagral API authentication.
            serial_id (str | None, optional): The serial ID of the Diagral system. Defaults to
                None, which only `login()`, `get_systems()` and `ping()` accept: list the
                account's serials with `get_systems()`, then create the client with one.
            apikey (str | None, optional): The API key for additional authentication. Defaults to None.
            secret_key (str | None, optional): The secret key for additional authentication. Defaults to None.
            pincode (str | None, optional): The PIN code for the Diagral system. Defaults to None.
            request_timeout (float, optional): Seconds allowed for each request to the Diagral
                cloud, keyword-only. Defaults to 30. To give one call a shorter deadline, wrap it
                in `asyncio.timeout()`; that deadline cannot exceed this value.
            session (aiohttp.ClientSession | None, optional): A session to send requests
                with, keyword-only. The caller keeps ownership: it is neither replaced nor
                closed. Defaults to None, where the client opens its own session on enter
                and closes it on exit.
            vendor (str, optional): The brand the account belongs to, keyword-only: one of
                `DIAGRAL`, `DAITEM`, `EDAITEM`, `LOGISTYALMA` or `DISTRIBUTION`, in any case.
                Defaults to `DIAGRAL`.

        Raises:
            ConfigurationError: If any required field is empty or invalid.

        """
        # Validate username as an email
        if (
            not username
            or not isinstance(username, str)
            or not self.__is_valid_email(username)
        ):
            raise ConfigurationError("username must be a valid non-empty email address")
        self.username: str = username

        # Validate password
        if not password or not isinstance(password, str):
            raise ConfigurationError("password must be a non-empty string")
        self.__password: str = password

        # Validate serial_id
        if serial_id is not None and (not serial_id or not isinstance(serial_id, str)):
            raise ConfigurationError("serial_id must be a non-empty string or None")
        self.serial_id: str | None = serial_id

        # Set apikey and secret_key
        self.__apikey: str | None = apikey
        self.__secret_key: str | None = secret_key

        # Validate pincode
        if pincode is not None:
            if not isinstance(pincode, str) or (
                isinstance(pincode, str) and not pincode.isdigit()
            ):
                raise ConfigurationError("pincode must be an string of digits")
        self.__pincode: str | None = pincode

        # bool is an int subclass: True would otherwise be accepted as 1 second.
        if (
            isinstance(request_timeout, bool)
            or not isinstance(request_timeout, int | float)
            or not math.isfinite(request_timeout)
            or request_timeout <= 0
        ):
            raise ConfigurationError("request_timeout must be a positive number")
        self.__request_timeout: float = request_timeout

        if not isinstance(vendor, str) or vendor.upper() not in VENDORS:
            raise ConfigurationError(f"vendor must be one of {', '.join(VENDORS)}")
        self.vendor: str = vendor.upper()

        # Initialize session and access_token
        self.session: aiohttp.ClientSession | None = session
        self.__owns_session: bool = session is None
        self.__access_token: str | None = None

        # Set default values for other attributes
        self.alarm_configuration: AlarmConfiguration | None = None

    @property
    def request_timeout(self) -> float:
        """Seconds allowed for each request to the Diagral cloud."""
        return self.__request_timeout

    @property
    def __serial(self) -> str:
        """The serial ID, for the calls that address the system.

        Raises:
            ConfigurationError: If the client was created without one.

        """
        if self.serial_id is None:
            raise ConfigurationError(
                "serial_id is required for this call; create the client with one"
            )
        return self.serial_id

    async def __aenter__(self) -> Self:
        """Open the aiohttp ClientSession, unless the caller provided one."""
        # Entering twice must not orphan the first session.
        if self.__owns_session and (self.session is None or self.session.closed):
            self.session = aiohttp.ClientSession()
            _LOGGER.info("Successfully initialized DiagralAPI session")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close the aiohttp ClientSession, unless the caller provided it."""
        if self.__owns_session and self.session:
            await self.session.close()
            self.session = None

    @overload
    async def _request(
        self,
        method: str,
        endpoint: str,
        timeout: float | None = None,
        *,
        log_endpoint: str | None = None,
        versioned: bool = True,
        list_body: Literal[False] = False,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], int]: ...

    @overload
    async def _request(
        self,
        method: str,
        endpoint: str,
        timeout: float | None = None,
        *,
        log_endpoint: str | None = None,
        versioned: bool = True,
        list_body: Literal[True],
        **kwargs: Any,
    ) -> tuple[list[Any], int]: ...

    async def _request(
        self,
        method: str,
        endpoint: str,
        timeout: float | None = None,
        *,
        log_endpoint: str | None = None,
        versioned: bool = True,
        list_body: bool = False,
        **kwargs: Any,
    ) -> tuple[dict[str, Any] | list[Any], int]:
        """Make an asynchronous HTTP request to the specified endpoint.

        Args:
            method (str): The HTTP method to use for the request (e.g., 'GET', 'POST').
            endpoint (str): The API endpoint to send the request to.
            timeout (float | None, optional): The timeout for this request in seconds.
                Defaults to the client's `request_timeout`.
            log_endpoint (str | None, optional): The endpoint to show in the debug log instead of
                `endpoint`, when the path itself carries a secret. The serial ID is
                redacted from either one. Defaults to None.
            versioned (bool, optional): Whether `endpoint` sits under the API version.
                Defaults to True; False only for the unversioned root.
            list_body (bool, optional): Whether the endpoint answers with a JSON list instead
                of an object. Defaults to False.
            **kwargs (any): Additional keyword arguments to pass to the request.

        Returns:
            tuple[dict[str, Any] | list[Any], int]: A tuple containing:
                - dict[str, Any] | list[Any]: The JSON response from the API, a list when
                  `list_body` is True.
                - int: The HTTP status code of the response.

        Raises:
            SessionError: If the session is not initialized or is closed.
            DiagralAPIError: If the request results in a 400 status code or other API errors.
            AuthenticationError: If the request results in a 401 or 403 status code.
            ValidationError: If the request results in a 422 status code or a successful
                response is not a JSON object.
            ServerError: If the request results in a 5xx status code.
            ClientError: If there is a network error or timeout.

        """
        if self.session is None or self.session.closed:
            error_msg = "Session not initialized from __aenter__, or already closed."
            _LOGGER.error(error_msg)
            raise SessionError(error_msg)

        prefix: str = f"{BASE_URL}/{API_VERSION}" if versioned else BASE_URL
        url: str = f"{prefix}/{endpoint}"
        headers: Any = kwargs.pop("headers", {})
        logged_endpoint = log_endpoint or endpoint
        if self.serial_id:
            # Most paths name the central; users attach debug logs to public issues.
            logged_endpoint = logged_endpoint.replace(self.serial_id, REDACTED)
        _LOGGER.debug(
            "Sending %s request to %s with headers %s and data %s",
            method,
            f"{prefix}/{logged_endpoint}",
            Redacted(headers),
            Redacted(kwargs.get("json", {})),
        )

        try:
            async with self.session.request(
                method,
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(
                    total=self.__request_timeout if timeout is None else timeout
                ),
                **kwargs,
            ) as response:
                status = response.status
                _LOGGER.debug("Received Diagral HTTP status %s", status)
                if status >= 400:
                    if status in (401, 403):
                        raise AuthenticationError(
                            f"Diagral authentication error (HTTP {status})",
                            status_code=status,
                        )
                    if status >= 500:
                        raise ServerError(
                            f"Diagral service error (HTTP {status})", status_code=status
                        )
                    if status == 422:
                        raise ValidationError(
                            f"Diagral request validation error (HTTP {status})",
                            status_code=status,
                        )
                    # Error pages may be HTML, empty or malformed JSON; the status
                    # above already chose the exception class.
                    try:
                        error_data = await response.json()
                    except (aiohttp.ContentTypeError, ValueError):
                        error_data = {}
                    detail = (
                        error_data.get("detail")
                        if isinstance(error_data, dict)
                        else None
                    )
                    # Retain only protocol messages needed by callers. Arbitrary
                    # server errors can echo credentials or validation inputs.
                    known_detail = next(
                        (
                            message
                            for message in (
                                "No anomalies found",
                                "Subscription already exists",
                                "No subscription found for",
                                "There is no subscription for",
                            )
                            if isinstance(detail, str) and message in detail
                        ),
                        None,
                    )
                    error_message = f"Diagral API error (HTTP {status})"
                    if known_detail:
                        error_message = f"{error_message}: {known_detail}"
                    raise DiagralAPIError(error_message, status_code=status)
                if status in (204, 205):
                    return ([] if list_body else {}), status
                try:
                    response_data = await response.json()
                except (aiohttp.ContentTypeError, ValueError):
                    raise ValidationError(
                        f"Invalid JSON response from Diagral (HTTP {status})",
                        status_code=status,
                    ) from None
                expected, name = (list, "list") if list_body else (dict, "object")
                if not isinstance(response_data, expected):
                    raise ValidationError(
                        f"Expected a JSON {name} from Diagral (HTTP {status})",
                        status_code=status,
                    )
                return response_data, status
        except TimeoutError:
            # aiohttp exceptions may contain a URL with an API key. Suppress
            # their context so callers can safely log the resulting exception.
            raise ClientError("Diagral request timed out") from None
        except aiohttp.ClientError:
            raise ClientError("Network error communicating with Diagral") from None

    async def login(self) -> None:
        """Asynchronously logs in to the Diagral API using the provided username and password.

        This method sends a POST request to the authentication endpoint with the necessary credentials.
        If the login is successful, it retrieves and stores the access token.
        If the login fails, it raises an appropriate error.

        Raises:
            AuthenticationError: If the login fails or the access token cannot be obtained.
            ServerError: If the Diagral service is unavailable.
            ClientError: If there is a network error or timeout.

        """

        _LOGGER.debug("Attempting to login to Diagral API")
        _DATA: dict[str, str] = {"username": self.username, "password": self.__password}
        try:
            response_data, *_ = await self._request(
                "POST", f"users/authenticate/login?vendor={self.vendor}", json=_DATA
            )
        except AuthenticationError:
            _LOGGER.warning("Diagral authentication rejected")
            raise

        _LOGGER.debug("Login response data: %s", Redacted(response_data))
        login_response: LoginResponse = LoginResponse.from_dict(response_data)
        self.__access_token = login_response.access_token
        if not self.__access_token:
            error_msg = "Failed to obtain authentication access_token"
            _LOGGER.error(error_msg)
            raise AuthenticationError(error_msg)

        _LOGGER.info("Successfully logged in to Diagral API")

    async def set_apikey(self) -> ApiKeyWithSecret:
        """Asynchronously set the API key for the Diagral API.

        It sends a request to create a new API key using the current access token.
        If the API key is successfully created, it verifies the API key to ensure its validity.

        Returns:
            ApiKeyWithSecret: An instance of ApiKeyWithSecret containing the created API key and secret key.

        Raises:
            APIKeyCreationError: If the API key creation fails.
            APIValidationError: If the API key validation fails.
            DiagralAPIError: If authentication, transport or the Diagral service fails.
            ConfigurationError: If the client was created without a serial ID.

        """

        if not self.__access_token:
            await self.login()

        _DATA: dict[str, str] = {"serial_id": self.__serial}
        _HEADERS: dict[str, str] = {
            "Authorization": f"Bearer {self.__access_token}",
        }

        try:
            response_data, *_ = await self._request(
                "POST", "users/api_key", json=_DATA, headers=_HEADERS
            )
            set_apikey_response: ApiKeyWithSecret = ApiKeyWithSecret.from_dict(
                response_data
            )
            # ApiKeyWithSecret already rejects an empty key or secret.
            self.__apikey = set_apikey_response.api_key
            self.__secret_key = set_apikey_response.secret_key

            _LOGGER.info("Successfully created new API key")
            try:
                await self.validate_apikey()
                _LOGGER.info("Successfully verified new API key")
            except DiagralAPIError:
                _LOGGER.error("Created API key failed validation")
                await self.__discard_created_apikey()
                raise
        except ModelValidationError as err:
            raise APIKeyCreationError("Invalid API key response") from err
        except DiagralAPIError:
            _LOGGER.error("Failed to create or validate API key")
            raise

        return ApiKeyWithSecret(api_key=self.__apikey, secret_key=self.__secret_key)

    async def __discard_created_apikey(self) -> None:
        """Delete a key `set_apikey()` created but cannot hand over, best effort."""
        try:
            await self.delete_apikey()
        except DiagralAPIError:
            _LOGGER.warning("Unable to delete the API key that could not be used")
        finally:
            self.__apikey = None
            self.__secret_key = None

    async def validate_apikey(self, apikey: str | None = None) -> None:
        """Validate the current or provided API key by checking it against the list of valid keys.

        This method performs the following steps:
        1. Checks if the API key is available. If not, logs a warning and raises an AuthenticationError.
        2. Ensures that an access token is available by calling the login method if necessary.
        3. Sends a GET request to retrieve the list of valid API keys associated with the user's system.
        4. Checks if the current or provided API key is in the list of valid keys.
        5. Logs a success message if the API key is valid, otherwise raises an AuthenticationError.

        Args:
            apikey (str | None, optional): The API key to validate. If not provided, the instance's API key is used. Defaults to None.

        Raises:
            ConfigurationError: If no API key is provided or if the API key is invalid, or if the client was created without a serial ID.
            APIValidationError: If the API key is invalid or not found in the list of valid keys.

        """

        apikey_to_validate = apikey or self.__apikey

        if not apikey_to_validate:
            _LOGGER.warning("No API key provided to validate")
            raise ConfigurationError("No API key provided to validate")

        if not self.__access_token:
            await self.login()

        _HEADERS: dict[str, str] = {
            "Authorization": f"Bearer {self.__access_token}",
        }
        response_data, *_ = await self._request(
            "GET",
            f"users/systems/{self.__serial}/api_keys",
            headers=_HEADERS,
        )
        validate_apikey_response: ApiKeys = ApiKeys.from_dict(response_data)
        is_valid = any(
            key_info.api_key == apikey_to_validate
            for key_info in validate_apikey_response.api_keys
        )
        if is_valid:
            _LOGGER.info("API key successfully validated")
        else:
            raise APIValidationError(
                "API key is invalid or not found in the list of valid keys"
            )

    async def delete_apikey(self, apikey: str | None = None) -> None:
        """Asynchronously delete the specified or current API key.

        This method deletes the API key associated with the instance or the provided API key.
        If the API key is not available, it raises an AuthenticationError. If the access token
        is not available, it attempts to log in to obtain one. The method then sends a DELETE
        request to the appropriate endpoint to delete the API key. Upon successful deletion,
        it logs an informational message and sets the `apikey` and `secret_key` attributes to None.

        Args:
            apikey (str | None, optional): The API key to delete. If not provided, the instance's API key is used. Defaults to None.

        Raises:
            AuthenticationError: If the API key is not available.
            ConfigurationError: If the client was created without a serial ID.

        """

        apikey_to_delete = apikey or self.__apikey

        if not apikey_to_delete:
            raise AuthenticationError("An API key is required to delete it")

        if not self.__access_token:
            await self.login()

        _HEADERS: dict[str, str] = {
            "Authorization": f"Bearer {self.__access_token}",
        }
        await self._request(
            "DELETE",
            f"users/systems/{self.__serial}/api_keys/{apikey_to_delete}",
            headers=_HEADERS,
            log_endpoint=f"users/systems/{self.__serial}/api_keys/{REDACTED}",
        )
        _LOGGER.info("Successfully deleted API key: ...%s", apikey_to_delete[-4:])

        if apikey is None:
            self.__apikey = None
            self.__secret_key = None

    async def get_systems(self) -> list[SystemApiKeys]:
        """List the systems of the account, with the API keys created for each.

        Only the username and password are needed, so the client may be created without
        a serial ID: this is how to discover the serial IDs of an account.

        Returns:
            list[SystemApiKeys]: One entry per system of the account.

        Raises:
            AuthenticationError: If the login fails.
            ModelValidationError: If a system in the response is not an object.
            DiagralAPIError: If transport or the Diagral service fails.

        """

        if not self.__access_token:
            await self.login()

        _HEADERS: dict[str, str] = {
            "Authorization": f"Bearer {self.__access_token}",
        }
        response_data, *_ = await self._request(
            "GET", "users/systems", headers=_HEADERS, list_body=True
        )
        systems = [SystemApiKeys.from_dict(system) for system in response_data]
        _LOGGER.debug("Retrieved %d systems for the account", len(systems))
        return systems

    async def try_connection(self, ephemeral: bool = True) -> TryConnectResult:
        """Test connection with the Diagral system.

        This method tests the connection by either using provided API credentials or generating
        temporary ones. It validates the connection by checking the system status.

        Args:
            ephemeral (bool, optional): If True, temporary API keys will be deleted after
                connection test. Defaults to True.

        Returns:
            TryConnectResult: Object containing connection test results and optionally API keys
                if non-ephemeral temporary keys were generated.

        Raises:
            APIKeyCreationError: If creation of temporary API keys fails
            APIValidationError: If API key validation fails
            SessionError: If the session is not initialized or is closed.
            DiagralAPIError: If the request results in a 400 status code or other API errors.
            AuthenticationError: If authentication fails or request results in a 401 or 403 status code.
            PinCodeError: If the client was created without API keys and Diagral refuses
                the PIN code. With API keys given, a wrong PIN raises AuthenticationError,
                as a wrong key does.
            ValidationError: If the request results in a 422 status code.
            ServerError: If the request results in a 500 or 503 status code.
            ClientError: If there is a network error.
            ConfigurationError: If the client was created without a serial ID.

        Note:
            If API credentials are not provided during client initialization, temporary
            keys will be generated (if ephemeral) for the connection test. These keys will be:
            - Deleted after the test if ephemeral=True
            - Returned in the result if ephemeral=False

        """

        result: TryConnectResult = TryConnectResult()
        api_keys_provided = bool(self.__apikey and self.__secret_key)

        # If API keys are not provided, generate temporary keys
        if not api_keys_provided:
            api_key_response: ApiKeyWithSecret = await self.set_apikey()

        # Retrieve system status to validate connection
        try:
            await self.get_system_status()
        except DiagralAPIError as err:
            # If connection fails, clean up keys
            if not api_keys_provided:
                try:
                    await self.delete_apikey()
                except DiagralAPIError:
                    _LOGGER.warning(
                        "Unable to clean up temporary API key after connection failure"
                    )
                # The key was just created and validated: the PIN is the only
                # credential this call adds.
                if isinstance(err, AuthenticationError) and err.status_code == 401:
                    raise PinCodeError(
                        "Diagral rejected the PIN code (HTTP 401)", status_code=401
                    ) from err
            raise

        # If connection is successful, clean up temporary keys if requested (ephemeral)
        if ephemeral and not api_keys_provided:
            await self.delete_apikey()
        elif not ephemeral and not api_keys_provided:
            result.keys = api_key_response

        result.result = True
        return result

    async def ping(self) -> Ping:
        """Check that the Diagral cloud answers. No credential is needed.

        Returns:
            Ping: The status the cloud reports.

        Raises:
            SessionError: If the session is not initialized or is closed.
            ServerError: If the Diagral service is unavailable.
            ClientError: If there is a network error or timeout.
            ValidationError: If the answer is not a JSON object.

        """
        response_data, *_ = await self._request("GET", "", versioned=False)
        return Ping.from_dict(response_data)

    def __credentials(
        self, purpose: str, *, with_pin: bool = False
    ) -> tuple[str, str, str | None]:
        """Return the API key, secret key and PIN code an operation needs.

        Raises:
            AuthenticationError: Naming `purpose`, if one of them is missing.

        """
        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(f"API key and secret key required to {purpose}")
        if with_pin and not self.__pincode:
            raise AuthenticationError(f"PIN code required to {purpose}")
        return self.__apikey, self.__secret_key, self.__pincode if with_pin else None

    def __hmac_headers(self, purpose: str, *, with_pin: bool = False) -> dict[str, str]:
        """Build the signed headers of an HMAC-authenticated request.

        Raises:
            AuthenticationError: Naming `purpose`, if a credential is missing.

        """
        apikey, secret_key, pincode = self.__credentials(purpose, with_pin=with_pin)
        timestamp = str(int(time.time()))
        headers: dict[str, str] = {"X-PIN-CODE": pincode} if pincode else {}
        headers |= {
            "X-HMAC": generate_hmac_signature(
                timestamp=timestamp,
                serial_id=self.__serial,
                api_key=apikey,
                secret_key=secret_key,
            ),
            "X-TIMESTAMP": timestamp,
            "X-APIKEY": apikey,
        }
        return headers

    async def get_configuration(self) -> AlarmConfiguration:
        """Asynchronously retrieve the configuration of the Diagral system.

        This method retrieves the configuration of the Diagral system by sending a GET
        request to the appropriate endpoint, signed with the API key and secret key. The
        retrieved configuration is stored in
        the self.alarm_configuration attribute, allowing it to be reused within the same
        session without needing to collect it multiple times.

        Returns:
            AlarmConfiguration: The configuration details of the Diagral system.

        Raises:
            AuthenticationError: If the API key or the secret key is missing.
            ConfigurationError: If the client was created without a serial ID.

        """

        _HEADERS = self.__hmac_headers("get configuration")
        response_data, *_ = await self._request(
            "GET", f"systems/{self.__serial}/configurations", headers=_HEADERS
        )
        self.alarm_configuration = AlarmConfiguration.from_dict(response_data)
        # The redacted payload is already logged by from_dict().
        _LOGGER.debug("Successfully retrieved configuration")
        return self.alarm_configuration

    async def get_alarm_name(self) -> str | None:
        """Get the name of the alarm from the configuration.

        Returns:
            str | None: The name of the alarm from the configuration, or None when the
                configuration does not name it.

        Raises:
            ConfigurationError: If unable to retrieve the alarm configuration, or if the client was created without a serial ID.

        Note:
            This method will attempt to fetch the configuration if it hasn't been loaded yet.

        """

        if not self.alarm_configuration:
            await self.get_configuration()

        if not self.alarm_configuration:
            raise ConfigurationError("Failed to retrieve alarm configuration")

        alarm = self.alarm_configuration.alarm
        return alarm.name if alarm else None

    async def get_devices_info(self) -> DeviceList:
        """Asynchronously retrieves information about various device types from the alarm configuration.

        The method retrieves the index and label of each device of every type (cameras,
        commands, sensors, sirens, transmitters) from the alarm configuration.

        Returns:
            DeviceList: One list of `DeviceInfos` per device type.

        Raises:
            ConfigurationError: If the alarm configuration cannot be retrieved, or if the client was created without a serial ID.

        """

        if not self.alarm_configuration:
            await self.get_configuration()

        if not self.alarm_configuration:
            raise ConfigurationError("Failed to retrieve alarm configuration")

        device_types: list[str] = [
            "cameras",
            "commands",
            "sensors",
            "sirens",
            "transmitters",
        ]
        devices_infos = {}
        for device_type in device_types:
            _LOGGER.debug("Retrieving devices information for %s", device_type)
            devices: Any | None = getattr(self.alarm_configuration, device_type, None)
            if devices is not None:
                devices_infos[device_type] = [
                    {"index": device.index, "label": device.label} for device in devices
                ]
            else:
                devices_infos[device_type] = []
        _LOGGER.debug("Successfully retrieved devices information: %s", devices_infos)
        return DeviceList.from_dict(devices_infos)

    async def get_system_details(self) -> SystemDetails:
        """Asynchronously retrieves the system details.

        This method fetches the system details using the provided API key, secret key,
        and PIN code. It generates the necessary HMAC signature and includes it in the
        request headers.

        Returns:
            SystemDetails: An instance of SystemDetails containing the retrieved system information.

        Raises:
            AuthenticationError: If the API key, secret key, or PIN code is not provided.
            ConfigurationError: If the client was created without a serial ID.

        """

        _HEADERS = self.__hmac_headers("get system details", with_pin=True)
        response_data, *_ = await self._request(
            "GET", f"systems/{self.__serial}", headers=_HEADERS
        )
        _LOGGER.debug(
            "Successfully retrieved system details: %s", Redacted(response_data)
        )
        return SystemDetails.from_dict(response_data)

    async def get_system_status(self) -> SystemStatus:
        """Asynchronously retrieves the system status.

        This method fetches the current status of the system using the provided API key,
        secret key, and PIN code. It generates an HMAC signature for authentication and
        sends a GET request to the system status endpoint.

        Returns:
            SystemStatus: An instance of SystemStatus containing the retrieved system status.

        Raises:
            AuthenticationError: If the API key, secret key, or PIN code is not provided.
            ConfigurationError: If the client was created without a serial ID.

        """

        _HEADERS = self.__hmac_headers("get system status", with_pin=True)
        response_data, *_ = await self._request(
            "GET", f"systems/{self.__serial}/status", headers=_HEADERS
        )
        _LOGGER.debug(
            "Successfully retrieved system status: %s", Redacted(response_data)
        )
        return SystemStatus.from_dict(response_data)

    async def __system_action(self, action: str) -> SystemStatus:
        """Perform a system action such as start, stop, presence, partial start 1, or partial start 2.

        Args:
            action (str): The action to perform. Must be one of 'start', 'stop', 'presence', 'partial_start_1', or 'partial_start_2'.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after performing the action.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        if action not in [
            "start",
            "stop",
            "presence",
            "partial_start_1",
            "partial_start_2",
        ]:
            raise ConfigurationError(
                "Action must be one of 'start', 'stop', 'presence', 'partial_start_1', or 'partial_start_2'"
            )

        _HEADERS = self.__hmac_headers(f"do system action {action}", with_pin=True)
        response_data, *_ = await self._request(
            "POST", f"systems/{self.__serial}/{action}", headers=_HEADERS
        )
        _LOGGER.debug(
            "Successfully performed action %s: %s",
            action.upper(),
            Redacted(response_data),
        )
        return SystemStatus.from_dict(response_data)

    async def start_system(self) -> SystemStatus:
        """Asynchronously starts the system.

        This method sends a request to start the system and returns the system status.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after starting the system.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions, or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        return await self.__system_action("start")

    async def stop_system(self) -> SystemStatus:
        """Asynchronously stops the system.

        This method sends a request to stop the system and returns the system status.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after stopping the system.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions, or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        return await self.__system_action("stop")

    async def presence(self) -> SystemStatus:
        """Asynchronously starts the system in presence mode.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after starting the system in presence mode.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions, or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        return await self.__system_action("presence")

    async def partial_start_system(self, id: int = 1) -> SystemStatus:
        """Initiate a partial start of the system.

        Args:
            id (int, optional): The ID of the partial start. Must be either 1 or 2. Defaults to 1.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after performing the partial start.

        Raises:
            ConfigurationError: If the provided ID is not 1 or 2, or if the client was created without a serial ID.

        """

        if id not in [1, 2]:
            raise ConfigurationError("Partial Start Id must be 1 or 2")

        return await self.__system_action(f"partial_start_{id}")

    async def __action_group_system(
        self, action: str, groups: list[int]
    ) -> SystemStatus:
        """Perform an action on a group of systems.

        This method activates or disables a group of systems based on the provided action.

        Args:
            action (str): The action to perform. Must be either 'activate_group' or 'disable_group'.
            groups (list[int]): A list of group indices to perform the action on.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after performing the action.

        Raises:
            ConfigurationError: If the action is not 'activate_group' or 'disable_group', or if the groups are invalid.
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """

        if action not in ["activate_group", "disable_group"]:
            raise ConfigurationError(
                "Action must be either 'activate_group' or 'disable_group'"
            )

        # Checked before fetching the configuration; the headers are signed after it.
        self.__credentials(f"{action.replace('_', ' ')} {groups}", with_pin=True)

        configuration = self.alarm_configuration or await self.get_configuration()
        existing_groups = [g.index for g in configuration.groups or []]
        invalid_groups: list[int] = [
            group for group in groups if group not in existing_groups
        ]
        if invalid_groups:
            raise ConfigurationError(
                f"The following groups do not exist in your system: {invalid_groups}"
            )

        _HEADERS = self.__hmac_headers(
            f"{action.replace('_', ' ')} {groups}", with_pin=True
        )
        data: dict[str, list[int]] = {"groups": groups}
        response_data, *_ = await self._request(
            "POST",
            f"systems/{self.__serial}/{action}",
            headers=_HEADERS,
            json=data,
        )
        _LOGGER.debug(
            "Successfully %s %s: %s",
            action.replace("_", " "),
            groups,
            Redacted(response_data),
        )
        return SystemStatus.from_dict(response_data)

    async def activate_group(self, groups: list[int]) -> SystemStatus:
        """Asynchronously activates a group of systems.

        Args:
            groups (list[int]): A list of integers representing the groups to be activated.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after activating the groups.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions, or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """

        if not isinstance(groups, list) or not all(
            isinstance(item, int) for item in groups
        ):
            raise ConfigurationError("Groups must be a list of integers")

        return await self.__action_group_system("activate_group", groups)

    async def disable_group(self, groups: list[int]) -> SystemStatus:
        """Asynchronously disables a group of systems.

        Args:
            groups (list[int]): A list of integers representing the groups to disable.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after disabling the groups.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions, or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """

        if not isinstance(groups, list) or not all(
            isinstance(item, int) for item in groups
        ):
            raise ConfigurationError("Groups must be a list of integers")

        return await self.__action_group_system("disable_group", groups)

    async def __action_product(
        self, action: str, type: str, product_id: int
    ) -> SystemStatus:  # NOT-TESTED
        """Perform an action on a product in the Diagral system.

        This method enables or disables a product based on the provided action.

        Args:
            action (str): The action to perform. Must be either 'enable' or 'disable'.
            type (str): The type of product to perform the action on.
            product_id (int): The ID of the product to perform the action on.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after performing the action.

        Raises:
            ConfigurationError: If the action is not 'enable' or 'disable', or if the product type is invalid.
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """

        if action not in ["enable", "disable"]:
            raise ConfigurationError("Action must be either 'enable' or 'disable'")

        if type not in ["CENTRAL", "SENSOR", "COMMAND", "ALARM", "BOX", "PLUG"]:
            raise ConfigurationError(
                "Product type must be one of 'CENTRAL', 'SENSOR', 'COMMAND', 'ALARM', 'BOX', or 'PLUG'"
            )

        _HEADERS = self.__hmac_headers(f"{action} product", with_pin=True)
        response_data, *_ = await self._request(
            "POST",
            f"systems/{self.__serial}/{type}/{product_id}/{action}",
            headers=_HEADERS,
        )
        return SystemStatus.from_dict(response_data)

    async def enable_product(
        self, type: str, product_id: int
    ) -> SystemStatus:  # NOT-TESTED
        """Asynchronously enables a product in the system.

        Args:
            type (str): The type of the product to enable.
            product_id (int): The unique identifier of the product to enable.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after enabling the product.

        Raises:
            ConfigurationError: If the action is not 'enable', or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """
        return await self.__action_product(
            action="enable", type=type, product_id=product_id
        )

    async def disable_product(
        self, type: str, product_id: int
    ) -> SystemStatus:  # NOT-TESTED
        """Asynchronously disables a product in the system.

        Args:
            type (str): The type of the product to disable.
            product_id (int): The unique identifier of the product to disable.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after disabling the product.

        Raises:
            ConfigurationError: If the action is not 'disable', or if the client was created without a serial ID.
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """
        return await self.__action_product(
            action="disable", type=type, product_id=product_id
        )

    async def get_anomalies(self) -> Anomalies | dict:
        """Asynchronously retrieves anomalies for the system.

        This method fetches the anomalies associated with the system identified by the serial ID. It requires valid API key and secret key for authentication.

        Returns:
            Anomalies | dict: An instance of the Anomalies class populated with the data retrieved from the API, or an empty dictionary if no anomalies are found.

        Raises:
            AuthenticationError: If the API key or secret key is not provided.
            ConfigurationError: If the client was created without a serial ID.

        """

        _HEADERS = self.__hmac_headers("get anomalies")
        try:
            response_data, *_ = await self._request(
                "GET",
                f"systems/{self.__serial}/anomalies",
                headers=_HEADERS,
            )
        except DiagralAPIError as e:
            if e.status_code == 404 and "No anomalies found" in e.message:
                _LOGGER.info("No anomalies found for the system")
                return {}
            raise
        return Anomalies.from_dict(response_data)

    async def delete_anomalies(self, anomaly_id: int) -> None:  # NOT-IMPLEMENTED
        """Asynchronously delete the list of anomalies.

        This method is currently not implemented.

        Raises:
            NotImplementedError: This method is not yet implemented.

        """
        raise NotImplementedError("Method not yet implemented")

    async def get_automatism_rudes(self) -> Rudes:  # NOT-TESTED
        """Asynchronously retrieves the automatism Rudes for the system.

        This method fetches the Rudes data for the system identified by the serial ID.
        It requires valid API and secret keys for authentication.

        Returns:
            Rudes: An instance of the Rudes class populated with the data from the response.

        Raises:
            AuthenticationError: If the API key or secret key is not provided.
            ConfigurationError: If the client was created without a serial ID.

        """

        _HEADERS = self.__hmac_headers("get automatism rudes")
        response_data, *_ = await self._request(
            "GET",
            f"systems/{self.__serial}/rudes",
            headers=_HEADERS,
        )
        return Rudes.from_dict(response_data)

    async def set_automatism_action(
        self, canal: str, action: str
    ) -> None:  # NOT-IMPLEMENTED
        """Set the automatism action.

        This method is currently not implemented.

        Args:
            canal (str): The canal for the automatism action.
            action (str): The action to be set for the automatism.

        Raises:
            NotImplementedError: Always, as this method is not yet implemented.

        """
        raise NotImplementedError("Method not yet implemented")

    async def get_webhook(self) -> Webhook:
        """Retrieve the webhook subscription details for the system.

        Returns:
            Webhook: An instance of the Webhook class containing the subscription details.

        Raises:
            AuthenticationError: If the API key or secret key is not provided.
            ConfigurationError: If the client was created without a serial ID.

        """

        _HEADERS = self.__hmac_headers("get webhook")
        response_data, *_ = await self._request(
            "GET",
            f"webhooks/{self.__serial}/subscription",
            headers=_HEADERS,
        )
        return Webhook.from_dict(response_data)

    async def __webhook_action_create_update(
        self,
        action: str,
        webhook_url: str,
        subscribe_to_anomaly: bool = False,
        subscribe_to_alert: bool = False,
        subscribe_to_state: bool = False,
    ) -> Webhook | None:
        """Create or update a webhook subscription.

        Args:
            action (str): The action to perform, either 'register' or 'update'.
            webhook_url (str): The URL of the webhook to register or update.
            subscribe_to_anomaly (bool, optional): Whether to subscribe to anomaly notifications. Defaults to False.
            subscribe_to_alert (bool, optional): Whether to subscribe to alert notifications. Defaults to False.
            subscribe_to_state (bool, optional): Whether to subscribe to state notifications. Defaults to False.

        Returns:
            Webhook | None: The created or updated Webhook object, or None if registration is skipped.

        Raises:
            ConfigurationError: If the action is not 'register' or 'update'.
            AuthenticationError: If the API key or secret key is missing.
            ValidationError: If the webhook URL is invalid or if the subscription already exists.

        """
        if action not in ["register", "update"]:
            raise ConfigurationError("Action must be either 'register' or 'update'")

        if action == "register" and not any(
            [subscribe_to_anomaly, subscribe_to_alert, subscribe_to_state]
        ):
            _LOGGER.warning("No subscriptions selected, skipping webhook registration")
            return None

        if not re.match(r"^https?://", webhook_url):
            raise ValidationError(
                "Invalid webhook URL. Must start with http:// or https://"
            )

        _HEADERS = self.__hmac_headers(f"{action} webhook")
        data = {
            "webhook_url": webhook_url,
            "subscribe_to_anomaly": subscribe_to_anomaly,
            "subscribe_to_alert": subscribe_to_alert,
            "subscribe_to_state": subscribe_to_state,
        }
        method = "POST" if action == "register" else "PUT"
        try:
            response_data, *_ = await self._request(
                method,
                f"webhooks/{self.__serial}/subscription",
                headers=_HEADERS,
                json=data,
            )
        except DiagralAPIError as e:
            if "Subscription already exists" in str(e):
                raise DiagralAPIError(
                    "Webhook subscription already exists. Please use the 'update' action to modify it.",
                    status_code=e.status_code,
                ) from e
            if "There is no subscription for" in str(e):
                raise DiagralAPIError(
                    "No subscription found for the specified serial ID",
                    status_code=e.status_code,
                ) from e
            raise
        return Webhook.from_dict(response_data)

    async def register_webhook(
        self,
        webhook_url: str,
        subscribe_to_anomaly: bool = False,
        subscribe_to_alert: bool = False,
        subscribe_to_state: bool = False,
    ) -> Webhook | None:
        """Register a webhook with the specified URL and subscription options.

        Args:
            webhook_url (str): The URL to which the webhook will send data.
            subscribe_to_anomaly (bool, optional): If True, subscribe to anomaly events. Defaults to False.
            subscribe_to_alert (bool, optional): If True, subscribe to alert events. Defaults to False.
            subscribe_to_state (bool, optional): If True, subscribe to state events. Defaults to False.

        Returns:
            Webhook | None: The registered Webhook object if successful, otherwise None.

        Raises:
            AuthenticationError: If the API key or secret key is missing.
            ConfigurationError: If the client was created without a serial ID.
            ValidationError: If the webhook URL does not start with http:// or https://.
            DiagralAPIError: If a subscription already exists; use `update_webhook()`.

        """
        return await self.__webhook_action_create_update(
            "register",
            webhook_url,
            subscribe_to_anomaly,
            subscribe_to_alert,
            subscribe_to_state,
        )

    async def update_webhook(
        self,
        webhook_url: str,
        subscribe_to_anomaly: bool = False,
        subscribe_to_alert: bool = False,
        subscribe_to_state: bool = False,
    ) -> Webhook | None:
        """Update the webhook configuration with the specified parameters.

        Args:
            webhook_url (str): The URL of the webhook to update.
            subscribe_to_anomaly (bool, optional): Whether to subscribe to anomaly notifications. Defaults to False.
            subscribe_to_alert (bool, optional): Whether to subscribe to alert notifications. Defaults to False.
            subscribe_to_state (bool, optional): Whether to subscribe to state notifications. Defaults to False.

        Returns:
            Webhook | None: The registered Webhook object if successful, otherwise None.

        Raises:
            AuthenticationError: If the API key or secret key is missing.
            ConfigurationError: If the client was created without a serial ID.
            ValidationError: If the webhook URL does not start with http:// or https://.
            DiagralAPIError: If no subscription exists yet; use `register_webhook()`.

        """
        return await self.__webhook_action_create_update(
            "update",
            webhook_url,
            subscribe_to_anomaly,
            subscribe_to_alert,
            subscribe_to_state,
        )

    async def delete_webhook(self) -> None:
        """Asynchronously deletes the webhook subscription for the current system.

        Raises:
            AuthenticationError: If the API key or secret key is not provided.
            ConfigurationError: If the client was created without a serial ID.

        Returns:
            None

        """

        _HEADERS = self.__hmac_headers("delete webhook")
        await self._request(
            "DELETE",
            f"webhooks/{self.__serial}/subscription",
            headers=_HEADERS,
        )

    @staticmethod
    def __is_valid_email(email: str) -> bool:
        """Validate the format of an email address.

        Args:
            email (str): The email address to validate.

        Returns:
            bool: True if the email is valid, False otherwise.

        """
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(email_regex, email) is not None
