"""Module for interacting with the Diagral API.

This module provides a DiagralAPI class that encapsulates all the functionality
for communicating with the Diagral alarm system API, including authentication,
retrieving system status, and controlling various aspects of the alarm system.
"""

from __future__ import annotations

from datetime import datetime
import logging
import re
import time
from typing import Any, Self

import aiohttp

from .constants import API_VERSION, BASE_URL
from .exceptions import (
    AuthenticationError,
    ClientError,
    ConfigurationError,
    DiagralAPIError,
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
    HTTPErrorResponse,
    HTTPValidationError,
    LoginResponse,
    Rudes,
    SystemDetails,
    SystemStatus,
    Webhook,
)
from .utils import generate_hmac_signature

_LOGGER = logging.getLogger(__name__)

# Minimum Python version: 3.10


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
        serial_id: str,
        apikey: str | None = None,
        secret_key: str | None = None,
        pincode: int | None = None,
    ) -> None:
        """Initialize the DiagralAPI instance.

        Args:
            username (str): The email address for Diagral API authentication.
            password (str): The password for Diagral API authentication.
            serial_id (str): The serial ID of the Diagral system.
            apikey (str | None, optional): The API key for additional authentication. Defaults to None.
            secret_key (str | None, optional): The secret key for additional authentication. Defaults to None.
            pincode (int | None, optional): The PIN code for the Diagral system. Defaults to None.

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
        self.username = username

        # Validate password
        if not password or not isinstance(password, str):
            raise ConfigurationError("password must be a non-empty string")
        self.__password = password

        # Validate serial_id
        if not serial_id or not isinstance(serial_id, str):
            raise ConfigurationError("serial_id must be a non-empty string")
        self.serial_id = serial_id

        # Set apikey and secret_key
        self.__apikey = apikey
        self.__secret_key = secret_key

        # Validate pincode
        if pincode is not None:
            if not isinstance(pincode, int):
                raise ConfigurationError("pincode must be an integer")
        self.__pincode = pincode

        # Initialize session and access_token
        self.session: aiohttp.ClientSession | None = None
        self.__access_token: str | None = None
        self.access_token_expires: datetime | None = None

        # Set default values for other attributes
        self.alarm_configuration: AlarmConfiguration | None = None

    async def __aenter__(self) -> Self:
        """Initialize the aiohttp ClientSession."""
        self.session = aiohttp.ClientSession()
        _LOGGER.info("Successfully initialized DiagralAPI session")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Close the aiohttp ClientSession."""
        if self.session:
            await self.session.close()

    async def _request(
        self, method: str, endpoint: str, timeout: float = 30, **kwargs
    ) -> tuple[dict[str, Any], int]:
        """Make an asynchronous HTTP request to the specified endpoint.

        Args:
            method (str): The HTTP method to use for the request (e.g., 'GET', 'POST').
            endpoint (str): The API endpoint to send the request to.
            timeout (float, optional): The timeout for the request in seconds. Defaults to 30.
            **kwargs (any): Additional keyword arguments to pass to the request.

        Returns:
            tuple[dict[str, Any], int]: A tuple containing:
                - dict[str, Any]: The JSON response from the API.
                - int: The HTTP status code of the response.

        Raises:
            SessionError: If the session is not initialized.
            DiagralAPIError: If the request results in a 400 status code or other API errors.
            AuthenticationError: If the request results in a 401 or 403 status code.
            ValidationError: If the request results in a 422 status code.
            ServerError: If the request results in a 500 or 503 status code.
            ClientError: If there is a network error.
            aiohttp.ContentTypeError: If the response is not valid JSON.

        """
        if not self.session:
            error_msg = "Session not initialized from __aenter__."
            _LOGGER.error(error_msg)
            raise SessionError(error_msg)

        url = f"{BASE_URL}/{API_VERSION}/{endpoint}"
        headers = kwargs.pop("headers", {})
        _LOGGER.debug(
            "Sending %s request to %s with headers %s and data %s",
            method,
            url,
            headers,
            kwargs.get("json", {}),
        )

        try:
            async with self.session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            ) as response:
                response_data = await response.json()
                if response.status == 400:
                    response = HTTPErrorResponse(**response_data)
                    raise DiagralAPIError(
                        f"Bad request - Detail : {response.detail}",
                    )
                if response.status == 401:
                    response = HTTPErrorResponse(**response_data)
                    raise AuthenticationError(
                        f"Unauthorized - Invalid or expired token - Detail : {response.detail}"
                    )
                if response.status == 403:
                    response = HTTPErrorResponse(**response_data)
                    raise AuthenticationError(
                        f"Forbidden - The user does not have the right permissions - Detail : {response.detail}"
                    )
                if response.status == 422:
                    _LOGGER.debug("test: %s", response_data)
                    response = HTTPValidationError(**response_data)
                    raise ValidationError(
                        f"Validation Error - Detail : {response.detail}"
                    )
                if response.status == 500:
                    response = HTTPErrorResponse(**response_data)
                    raise ServerError(
                        f"Internal Server Error - Detail : {response.detail}"
                    )
                if response.status == 503:
                    response = HTTPErrorResponse(**response_data)
                    raise ServerError(
                        f"Service temporarily unavailable - Detail : {response.detail}"
                    )
                if response.status >= 400:
                    _LOGGER.debug(
                        "Received response with status code: %d and content %s",
                        response.status,
                        await response.json(),
                    )
                    raise DiagralAPIError(
                        f"API error: {response.status} - Error Message : {await response.text()}",
                        status_code=response.status,
                    )
                return await response.json(), response.status
        except aiohttp.ContentTypeError as e:
            raise ValidationError(f"Invalid JSON response: {e}") from e
        except aiohttp.ClientError as e:
            raise ClientError(f"Network error: {e}") from e

    async def login(self) -> None:
        """Asynchronously logs in to the Diagral API using the provided username and password.

        This method sends a POST request to the authentication endpoint with the necessary credentials.
        If the login is successful, it retrieves and stores the access token.
        If the login fails, it raises an appropriate error.

        Raises:
            AuthenticationError: If the login fails or the access token cannot be obtained.

        """

        if not self.session:
            error_msg = "Session not initialized from __aenter__."
            _LOGGER.error(error_msg)
            raise SessionError(error_msg)

        _LOGGER.debug("Attempting to login to Diagral API")
        _DATA = {"username": self.username, "password": self.__password}
        try:
            response_data, *_ = await self._request(
                "POST", "users/authenticate/login?vendor=DIAGRAL", json=_DATA
            )
            _LOGGER.debug("Login Response data: %s", response_data)
            login_response = LoginResponse.from_dict(response_data)
            _LOGGER.debug("Login response: %s", login_response)

            self.__access_token = login_response.access_token
            if not self.__access_token:
                error_msg = "Failed to obtain authentication access_token"
                _LOGGER.error(error_msg)
                raise AuthenticationError(error_msg)

            _LOGGER.info("Successfully logged in to Diagral API")
        except DiagralAPIError as e:
            error_msg = f"Failed to login : {e!s}"
            _LOGGER.error(error_msg)
            raise AuthenticationError(error_msg) from e

    async def set_apikey(self) -> ApiKeyWithSecret:
        """Asynchronously set the API key for the Diagral API.

        This method first ensures that the access token is valid and not expired.
        If the access token is expired, it attempts to log in again to refresh it.
        Then, it sends a request to create a new API key using the current access token.
        If the API key is successfully created, it verifies the API key to ensure its validity.

        Returns:
            ApiKeyWithSecret: An instance of ApiKeyWithSecret containing the created API key and secret key.

        Raises:
            AuthenticationError: If the API key is not found in the response or if the created API key fails validation.

        """

        if not self.__access_token:
            await self.login()

        if (
            self.__access_token
            and self.access_token_expires
            and datetime.now() >= self.access_token_expires
        ):
            _LOGGER.warning("Access token has expired, attempting to login again")
            await self.login()

        _DATA = {"serial_id": self.serial_id}
        _HEADERS = {
            "Authorization": f"Bearer {self.__access_token}",
        }

        try:
            response_data, *_ = await self._request(
                "POST", "users/api_key", json=_DATA, headers=_HEADERS
            )
            set_apikey_response = ApiKeyWithSecret.from_dict(response_data)
            self.__apikey = set_apikey_response.api_key
            if not self.__apikey:
                error_msg = "API key not found in response"
                _LOGGER.error(error_msg)
                raise AuthenticationError(error_msg)
            self.__secret_key = set_apikey_response.secret_key
            if not self.__secret_key:
                error_msg = "Secret key not found in response"
                _LOGGER.error(error_msg)
                raise AuthenticationError(error_msg)

            _LOGGER.info("Successfully created new API key: ...%s", self.__apikey[-4:])
            # Verify if the API key is valid
            try:
                await self.validate_apikey()
                _LOGGER.info(
                    "Successfully verified new API key: ...%s", self.__apikey[-4:]
                )
            except AuthenticationError as e:
                _LOGGER.error("Created API key failed validation: %s", e)
                self.__apikey = None
                raise
        except DiagralAPIError as e:
            error_msg = f"Failed to create API key: {e!s}"
            _LOGGER.error(error_msg)
            raise AuthenticationError(error_msg) from e

        return ApiKeyWithSecret(api_key=self.__apikey, secret_key=self.__secret_key)

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
            ConfigurationError: If no API key is provided or if the API key is invalid.

        """

        apikey_to_validate = apikey or self.__apikey

        if not apikey_to_validate:
            _LOGGER.warning("No API key provided to validate")
            raise ConfigurationError("No API key provided to validate")

        if not self.__access_token:
            await self.login()

        _HEADERS = {
            "Authorization": f"Bearer {self.__access_token}",
        }
        response_data, *_ = await self._request(
            "GET",
            f"users/systems/{self.serial_id}/api_keys",
            headers=_HEADERS,
        )
        validate_apikey_response = ApiKeys.from_dict(response_data)
        is_valid = any(
            key_info.api_key == apikey_to_validate
            for key_info in validate_apikey_response.api_keys
        )
        if is_valid:
            _LOGGER.info("API key successfully validated")
        else:
            raise AuthenticationError(
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

        """

        apikey_to_delete = apikey or self.__apikey

        if not apikey_to_delete:
            raise AuthenticationError("An API key is required to delete it")

        if not self.__access_token:
            await self.login()

        _HEADERS = {
            "Authorization": f"Bearer {self.__access_token}",
        }
        await self._request(
            "DELETE",
            f"users/systems/{self.serial_id}/api_keys/{apikey_to_delete}",
            headers=_HEADERS,
        )
        _LOGGER.info("Successfully deleted API key: ...%s", apikey_to_delete[-4:])

        if apikey is None:
            self.__apikey = None
            self.__secret_key = None

    async def get_configuration(self) -> None:
        """Asynchronously retrieve the configuration of the Diagral system.

        This method retrieves the configuration of the Diagral system by sending a GET
        request to the appropriate endpoint. If the access token is not available, it
        attempts to log in to obtain one. Upon successful retrieval, it logs an informational
        message with the configuration details. The retrieved configuration is stored in
        the self.alarm_configuration attribute, allowing it to be reused within the same
        session without needing to collect it multiple times.

        Returns:
            AlarmConfiguration: The configuration details of the Diagral system.

        Raises:
            AuthenticationError: If the access token is not available.

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get configuration"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "GET", f"systems/{self.serial_id}/configurations", headers=_HEADERS
        )
        self.alarm_configuration = AlarmConfiguration.from_dict(response_data)
        _LOGGER.debug(
            "Successfully retrieved configuration: %s", self.alarm_configuration
        )
        return self.alarm_configuration

    async def get_devices_info(self) -> DeviceList:
        """Asynchronously retrieves information about various device types from the alarm configuration.

        The method retrieve information for each device type (cameras, commands, sensors, sirens,
        transmitters) from the alarm configuration, and compiles this information into a dictionary.

        Returns:
            dict: A dictionary where the keys are device types and the values are lists of dictionaries
            containing device information (index and label).

        Raises:
            ConfigurationError: If the alarm configuration cannot be retrieved.

        """

        if not self.alarm_configuration:
            await self.get_configuration()

        if not self.alarm_configuration:
            raise ConfigurationError("Failed to retrieve alarm configuration")

        device_types = sorted(
            ["cameras", "commands", "sensors", "sirens", "transmitters"]
        )
        devices_infos = {}
        for device_type in device_types:
            _LOGGER.debug("Retrieving devices information for %s", device_type)
            devices = getattr(self.alarm_configuration, device_type, None)
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

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        if not self.__pincode:
            raise AuthenticationError("PIN code required to get system details")

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-PIN-CODE": str(self.__pincode),
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "GET", f"systems/{self.serial_id}", headers=_HEADERS
        )
        _LOGGER.debug("Successfully retrieved system details: %s", response_data)
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

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        if not self.__pincode:
            raise AuthenticationError("PIN code required to get system details")

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-PIN-CODE": str(self.__pincode),
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "GET", f"systems/{self.serial_id}/status", headers=_HEADERS
        )
        _LOGGER.debug("Successfully retrieved system status: %s", response_data)
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

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        if not self.__pincode:
            raise AuthenticationError(f"PIN code required to do system action {action}")

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-PIN-CODE": str(self.__pincode),
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "POST", f"systems/{self.serial_id}/{action}", headers=_HEADERS
        )
        _LOGGER.debug(
            "Successfully performed action %s: %s", action.upper(), response_data
        )
        return SystemStatus.from_dict(response_data)

    async def start_system(self) -> SystemStatus:
        """Asynchronously starts the system.

        This method sends a request to start the system and returns the system status.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after starting the system.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        return await self.__system_action("start")

    async def stop_system(self) -> SystemStatus:
        """Asynchronously stops the system.

        This method sends a request to stop the system and returns the system status.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after stopping the system.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        return await self.__system_action("stop")

    async def presence(self) -> SystemStatus:
        """Asynchronously starts the system in presence mode.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after starting the system in presence mode.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions.
            AuthenticationError: If the API key, secret key, or PIN code is missing.

        """

        return await self.__system_action("presence")

    async def partial_start_system(self, id: int = 1) -> SystemStatus:  # NOT-TESTED
        """Initiate a partial start of the system.

        Args:
            id (int, optional): The ID of the partial start. Must be either 1 or 2. Defaults to 1.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after performing the partial start.

        Raises:
            ConfigurationError: If the provided ID is not 1 or 2.

        """

        if id not in [1, 2]:
            raise ConfigurationError("Partial Start Id must be 1 or 2")

        return await self.__system_action(f"partial_start_{id}")

    async def __action_group_system(
        self, action: str, groups: list[int]
    ) -> SystemStatus:  # TO-TEST
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

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        if not self.__pincode:
            raise AuthenticationError("PIN code required to get system details")

        # Get the configuration if it is not already available
        if not self.alarm_configuration:
            await self.get_configuration()

        # Check if the groups are valid
        invalid_groups = [
            group
            for group in groups
            if group not in [g.index for g in self.alarm_configuration.groups]
        ]
        if invalid_groups:
            raise ConfigurationError(
                f"The following groups do not exist in your system: {invalid_groups}"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-PIN-CODE": str(self.__pincode),
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        data = {"groups": groups}
        response_data, *_ = await self._request(
            "POST",
            f"systems/{self.serial_id}/{action}",
            headers=_HEADERS,
            json=data,
        )
        _LOGGER.debug(
            "Successfully %s %s: %s", action.replace("_", " "), groups, response_data
        )
        return SystemStatus.from_dict(response_data)

    async def activate_group(self, groups: list[int]) -> SystemStatus:
        """Asynchronously activates a group of systems.

        Args:
            groups (list[int]): A list of integers representing the groups to be activated.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after activating the groups.

        Raises:
            ConfigurationError: If the action is not one of the allowed actions.
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
            ConfigurationError: If the action is not one of the allowed actions.
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

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        if not self.__pincode:
            raise AuthenticationError("PIN code required to get system details")

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-PIN-CODE": str(self.__pincode),
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "POST",
            f"systems/{self.serial_id}/{type}/{product_id}/{action}",
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
            ConfigurationError: If the action is not 'enable'
            AuthenticationError: If the API key, secret key, or PIN code is not provided.

        """
        return await self.__action_product(
            action="enable", type=type, product_id=product_id
        )

    async def disable_product(
        self, type: str, product_id: int
    ) -> SystemStatus:  # NOT-TESTED
        """Asynchronously enables a product in the system.

        Args:
            type (str): The type of the product to enable.
            product_id (int): The unique identifier of the product to enable.

        Returns:
            SystemStatus: An instance of SystemStatus containing the system status after disabling the product.

        Raises:
            ConfigurationError: If the action is not 'disable'
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

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        try:
            response_data, *_ = await self._request(
                "GET",
                f"systems/{self.serial_id}/anomalies",
                headers=_HEADERS,
            )
        except DiagralAPIError as e:
            if e.status_code == 404 and "No anomalies found" in e.message:
                _LOGGER.info("No anomalies found for the system")
                return {}
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

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "GET",
            f"systems/{self.serial_id}/rudes",
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

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "GET",
            f"webhooks/{self.serial_id}/subscription",
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

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        if action == "register" and not any(
            [subscribe_to_anomaly, subscribe_to_alert, subscribe_to_state]
        ):
            _LOGGER.warning("No subscriptions selected, skipping webhook registration")
            return None

        if not re.match(r"^https?://", webhook_url):
            raise ValidationError(
                "Invalid webhook URL. Must start with http:// or https://"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
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
                f"webhooks/{self.serial_id}/subscription",
                headers=_HEADERS,
                json=data,
            )
        except DiagralAPIError as e:
            if "Subscription already exists" in str(e):
                raise DiagralAPIError(
                    "Webhook subscription already exists. Please use the 'update' action to modify it."
                ) from e
            if "There is no subscription for" in str(e):
                raise DiagralAPIError(
                    "No subscription found for the specified serial ID"
                ) from e
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

        Returns:
            None

        """

        if not self.__apikey or not self.__secret_key:
            raise AuthenticationError(
                "API key and secret key required to get system details"
            )

        _TIMESTAMP = str(int(time.time()))
        _HMAC = generate_hmac_signature(
            timestamp=_TIMESTAMP,
            serial_id=self.serial_id,
            api_key=self.__apikey,
            secret_key=self.__secret_key,
        )

        _HEADERS = {
            "X-HMAC": _HMAC,
            "X-TIMESTAMP": _TIMESTAMP,
            "X-APIKEY": self.__apikey,
        }
        response_data, *_ = await self._request(
            "DELETE",
            f"webhooks/{self.serial_id}/subscription",
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
