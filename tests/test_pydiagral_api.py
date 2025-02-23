"""Module containing test cases for the DiagralAPI."""

from datetime import datetime, timezone
import logging
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

from pydiagral.exceptions import ConfigurationError, DiagralAPIError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
import json

from pydiagral import AuthenticationError, DiagralAPI, ValidationError
from pydiagral.models import (
    Anomalies,
    AnomalyDetail,
    AnomalyName,
    ApiKeyWithSecret,
    DeviceList,
    SystemDetails,
    SystemStatus,
    Webhook,
)

# Logger configuration
api_logger = logging.getLogger("pydiagral.api")
api_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
api_logger.addHandler(handler)

# Sample configuration data
USERNAME = "test_email@example.com"
PASSWORD = "test_password"
SERIAL_ID = "test_serial_id"
API_KEY = "test_api_key"
SECRET_KEY = "test_secret_key"
PIN_CODE = 1234
FAKE_TOKEN = "test_fake_token"
WEBHOOK_URL = "https://hook.example.com/webhook"


def load_sample(file_name):
    """Load configuration from a JSON file."""
    config_path = os.path.join(os.path.dirname(__file__), "./data", file_name)
    with open(config_path) as file:
        return json.load(file)


###############################
# DiagralAPI Login Test Cases #
###############################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_success_login(mock_request):
    """Test the successful login functionality of the DiagralAPI.

    This test mocks the request to the login endpoint and verifies that the
    access token is correctly set in the DiagralAPI instance.

    Args:
        mock_request (Mock): A mock object to simulate the request and response.

    Assertions:
        Asserts that the access token in the DiagralAPI instance is set to "fake_token".

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        assert diagral._DiagralAPI__access_token == FAKE_TOKEN  # noqa: SLF001


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_success_first_login(mock_request):
    """Test the successful login functionality of the DiagralAPI.

    This test mocks the request to the login endpoint and verifies that the
    access token is correctly set in the DiagralAPI instance.

    Args:
        mock_request (Mock): A mock object to simulate the request and response.

    Assertions:
        Asserts that the access token in the DiagralAPI instance is set to "fake_token".

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        assert diagral._DiagralAPI__access_token == FAKE_TOKEN  # noqa: SLF001


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_invalid_login(mock_request):
    """Test the login functionality with invalid credentials.

    This test simulates an invalid login attempt by setting the side effect of
    the mock_request to raise an AuthenticationError. It then verifies that
    the AuthenticationError is raised when attempting to log in with invalid
    credentials using the DiagralAPI.

    Args:
        mock_request (Mock): A mock object for simulating the request.

    Raises:
        AuthenticationError: If the login credentials are invalid.

    """
    mock_request.side_effect = AuthenticationError("Invalid credentials")
    with pytest.raises(AuthenticationError):
        async with DiagralAPI(
            username="invalid_email@example.com",
            password="invalid_password",
            serial_id=SERIAL_ID,
            apikey=API_KEY,
            secret_key=SECRET_KEY,
            pincode=PIN_CODE,
        ) as diagral:
            await diagral.login()


################################
# DiagralAPI APIKey Test Cases #
################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_set_apikey(mock_request):
    """Test the `set_apikey` method of the `DiagralAPI` class.

    This test simulates the process of setting an API key by mocking the responses
    for login, set_apikey, and validate_apikey requests. It verifies that the
    `set_apikey` method correctly retrieves and returns the expected API key and
    secret key.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Assertions:
        - The `api_key` returned by `set_apikey` matches the expected `API_KEY`.
        - The `secret_key` returned by `set_apikey` matches the expected `SECRET_KEY`.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"api_key": API_KEY, "secret_key": SECRET_KEY},
            200,
        ),  # Response for set_apikey
        (
            {"api_keys": [{"api_key": API_KEY}, {"api_key": "random_key"}]},
            200,
        ),  # Response for validate_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        api_keys = await diagral.set_apikey()
        assert isinstance(api_keys, ApiKeyWithSecret)
        assert api_keys.api_key == API_KEY
        assert api_keys.secret_key == SECRET_KEY


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_set_apikey_with_invalid_user_rights(mock_request):
    """Test the `set_apikey` method of the `DiagralAPI` class when the user has invalid permissions.

    This test simulates the scenario where a user with invalid permissions tries to set an API key.
    It mocks the `mock_request` to raise an `AuthenticationError` indicating that the user does not have the right permissions.

    Args:
        mock_request (Mock): A mock object for simulating API requests.

    Raises:
        AuthenticationError: If the user does not have the right permissions.

    """

    mock_request.side_effect = AuthenticationError(
        "The user does not have the right permissions"
    )
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        AuthenticationError(
            "The user does not have the right permissions"
        ),  # Response for set_apikey
    ]
    async with DiagralAPI(
        username="invalid_email@example.com",
        password="invalid_password",
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.set_apikey()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_validate_apikey(mock_request):
    """Test the validate_apikey method of the DiagralAPI class.

    This test uses a mock request to simulate the responses from the API.
    It first simulates a successful login response with an access token,
    and then simulates a response for the validate_apikey method with a list of API keys.

    Args:
        mock_request (MagicMock): A mock object to simulate API requests and responses.

    Assertions:
        The test does not contain explicit assertions but ensures that the
        validate_apikey method can be called without errors after a successful login.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"api_keys": [{"api_key": API_KEY}, {"api_key": "random_key"}]},
            200,
        ),  # Response for validate_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.validate_apikey()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_validate_apikey_specific(mock_request):
    """Test the `validate_apikey` method of the `DiagralAPI` class with a specific API key.

    This test mocks the `mock_request` to simulate the responses for the login and
    validate_apikey API calls. It verifies that the `validate_apikey` method works
    correctly when provided with a specific API key.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Side Effects:
        Sets the side effects for the `mock_request` to return predefined responses
        for the login and validate_apikey API calls.

    Raises:
        AssertionError: If the `validate_apikey` method does not behave as expected.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"api_keys": [{"api_key": API_KEY}, {"api_key": "random_key"}]},
            200,
        ),  # Response for validate_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.validate_apikey(API_KEY)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_validate_apikey_not_existing(mock_request):
    """Test the `validate_apikey` method of the `DiagralAPI` class when the API key does not exist.

    This test mocks the responses for the login and validate_apikey requests. It first simulates a successful login
    response and then simulates a response for the validate_apikey request with a list of API keys that do not match
    the provided API key. The test expects an `AuthenticationError` to be raised when the `validate_apikey` method
    is called with a non-existing API key.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests and responses.

    Raises:
        AuthenticationError: If the API key validation fails.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"api_keys": [{"api_key": "random_key1"}, {"api_key": "random_key2"}]},
            200,
        ),  # Response for validate_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.validate_apikey()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_validate_apikey_with_invalid_user_rights(mock_request):
    """Test the `validate_apikey` method of the `DiagralAPI` class when the user does not have the right permissions.

    This test simulates the scenario where the user attempts to validate an API key but lacks the necessary permissions.
    It uses a mock request to simulate the responses from the API.

    Args:
        mock_request (MagicMock): A mock object to simulate API responses.

    Raises:
        AuthenticationError: If the user does not have the right permissions to validate the API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        AuthenticationError(
            "The user does not have the right permissions"
        ),  # Response for validate_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.validate_apikey()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_delete_apikey(mock_request):
    """Test the deletion of an API key using the DiagralAPI.

    This test mocks the responses for the login and delete_apikey requests.
    It verifies that the API key and secret key are set to None after deletion.

    Args:
        mock_request (MagicMock): A mock object to simulate API responses.

    Side Effects:
        Sets the side_effect attribute of mock_request to simulate API responses.

    Assertions:
        Asserts that the API key and secret key are None after calling delete_apikey.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        ({}, 200),  # Response for delete_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.delete_apikey()
        assert diagral._DiagralAPI__apikey is None  # noqa: SLF001
        assert diagral._DiagralAPI__secret_key is None  # noqa: SLF001


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_delete_apikey_specific(mock_request):
    """Test the deletion of a specific API key using the DiagralAPI.

    This test mocks the responses for the login and delete_apikey requests.
    It verifies that the delete_apikey method is called successfully after logging in.

    Args:
        mock_request (MagicMock): A mock object to simulate API responses.

    Side Effects:
        Sets the side_effect attribute of mock_request to simulate API responses.

    Assertions:
        Ensures that the delete_apikey method is called without errors.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        ({}, 200),  # Response for delete_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.delete_apikey(API_KEY)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_delete_apikey_with_validation_error(mock_request):
    """Test the `delete_apikey` method of the `DiagralAPI` class when a validation error occurs.

    This test simulates the scenario where the `delete_apikey` method raises a `ValidationError`.
    It uses a mock request to simulate the responses for the login and delete_apikey methods.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Raises:
        ValidationError: If the `delete_apikey` method raises a validation error.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        ValidationError("Validation Error"),  # Response for delete_apikey
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(ValidationError):
            await diagral.delete_apikey()


#######################################
# DiagralAPI Configuration Test Cases #
#######################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_configuration(mock_request):
    """Test the `get_configuration` method of the `DiagralAPI` class.

    This test uses a mock request to simulate the API responses for login and
    getting the configuration. It verifies that the configuration retrieved
    has the expected alarm name.

    Args:
        mock_request (Mock): A mock object to simulate API requests and responses.

    Assertions:
        - The alarm name in the configuration should be "Sample Alarm".
        - The loop alert for the first sensor should be False

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("configuration_sample.json"),
            200,
        ),  # Response for get_configuration
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        configuration = await diagral.get_configuration()
        assert configuration.alarm.name == "Sample Alarm"
        assert not configuration.sensors[0].anomalies.loop_alert


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_configuration_without_apikey(mock_request):
    """Test the `get_configuration` method of the `DiagralAPI` class when no API key is provided.

    This test simulates the scenario where the user attempts to get the configuration
    without providing an API key and secret key. It mocks the responses for the login
    and get_configuration methods to raise an AuthenticationError.

    Args:
        mock_request (MagicMock): A mock object to simulate API responses.

    Raises:
        AuthenticationError: If the API key and secret key are not provided.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        AuthenticationError(
            "API key and secret key required to get configuration"
        ),  # Response for get_configuration
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.get_configuration()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_configuration_with_validation_error(mock_request):
    """Test the `get_configuration` method of the `DiagralAPI` class when no API key is provided.

    This test simulates the scenario where the `get_configuration` method is called without an API key,
    and it is expected to raise a `ValidationError`.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Side Effects:
        - The first call to `mock_request` simulates a successful login response with a fake access token.
        - The second call to `mock_request` simulates a `ValidationError` when attempting to get the configuration.

    Assertions:
        - Asserts that a `ValidationError` is raised when `get_configuration` is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        ValidationError("Validation Error"),  # Response for get_configuration
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(ValidationError):
            await diagral.get_configuration()


#####################################
# DiagralAPI Device Type Test Cases #
#####################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_device_infos(mock_request):
    """Test the `get_device_infos` method of the `DiagralAPI` class.

    This test uses a mock request to simulate the responses from the API for login and get_configuration.
    It verifies that the `get_device_infos` method returns a `DeviceList` object and checks the labels
    of the first command, sensor, and siren in the list.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Assertions:
        - The returned `devices_infos` is an instance of `DeviceList`.
        - The label of the first command in `devices_infos` is "COMMAND1".
        - The label of the first sensor in `devices_infos` is "SENSOR1".
        - The label of the first siren in `devices_infos` is "SIREN1".

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("configuration_sample.json"),
            200,
        ),  # Response for get_configuration
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.get_configuration()
        devices_infos = await diagral.get_devices_info()
        assert isinstance(devices_infos, DeviceList)
        assert devices_infos.commands[0].label == "COMMAND1"
        assert devices_infos.sensors[0].label == "SENSOR1"
        assert devices_infos.sirens[0].label == "SIREN1"


########################################
# DiagralAPI System Details Test Cases #
########################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_details(mock_request):
    """Test the `get_system_details` method of the `DiagralAPI` class.

    This test mocks the responses for the login and get_system_details API calls.
    It verifies that the `get_system_details` method returns an instance of `SystemDetails`
    with the expected attributes.

    Args:
        mock_request (MagicMock): A mock object to simulate API responses.

    Assertions:
        - The returned `system_details` is an instance of `SystemDetails`.
        - The `device_type` attribute of `system_details` is "PLUG_IP~DIAGRAL".
        - The `ip_address` attribute of `system_details` is "1.1.1.1".

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("system_details_sample.json"),
            200,
        ),  # Response for get_system_details
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_details = await diagral.get_system_details()
        assert isinstance(system_details, SystemDetails)
        assert system_details.device_type == "PLUG_IP~DIAGRAL"
        assert system_details.ip_address == "1.1.1.1"


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_details_without_apikey(mock_request):
    """Test the `get_system_details` method of the `DiagralAPI` class without providing an API key.

    This test mocks the request to simulate a successful login response and then attempts to call
    the `get_system_details` method. It expects an `AuthenticationError` to be raised due to the
    missing API key.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests.

    Raises:
        AuthenticationError: If the `get_system_details` method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.get_system_details()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_details_without_pincode(mock_request):
    """Test the `get_system_details` method of the `DiagralAPI` class without providing a pincode.

    This test mocks the request to simulate the login response and checks if the `get_system_details`
    method raises an `AuthenticationError` when called without a pincode.

    Args:
        mock_request (MagicMock): Mock object to simulate API requests.

    Raises:
        AuthenticationError: If the `get_system_details` method is called without a pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.get_system_details()


#######################################
# DiagralAPI System Status Test Cases #
#######################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_status(mock_request):
    """Test the `get_system_status` method of the `DiagralAPI` class.

    This test mocks the `mock_request` to simulate the responses for the login and
    get_system_status API calls. It verifies that the `get_system_status` method
    returns an instance of `SystemStatus` with the expected status and activated groups.

    Args:
        mock_request (Mock): The mock object to simulate API responses.

    Assertions:
        - The returned system status is an instance of `SystemStatus`.
        - The status of the system is "OFF".
        - The activated groups list is empty.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"status": "OFF", "activated_groups": []},
            200,
        ),  # Response for get_system_status
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.get_system_status()
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "OFF"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_status_without_apikey(mock_request):
    """Test the `get_system_status` method of the `DiagralAPI` class without providing an API key.

    This test simulates the behavior of the `DiagralAPI` when attempting to get the system status
    without an API key. It uses a mock request to simulate the responses from the API.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Steps:
    1. Set up the mock responses for the login and get_system_status API calls.
    2. Create an instance of `DiagralAPI` with the provided credentials.
    3. Perform the login operation.
    4. Attempt to get the system status and expect an `AuthenticationError` to be raised.

    Raises:
        AuthenticationError: If the API key is not provided or invalid.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.get_system_status()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_status_without_pincode(mock_request):
    """Test the `get_system_status` method of the `DiagralAPI` class without providing a pincode.

    This test simulates the behavior of the `DiagralAPI` when attempting to get the system status
    without a pincode. It uses a mock request to simulate the API responses for login and
    get_system_status endpoints.

    Args:
        mock_request (Mock): A mock object to simulate API requests and responses.

    Setup:
        - The mock_request is configured to return a fake access token for the login request.
        - The mock_request is configured to return a system status response indicating the system is "OFF"
          and no groups are activated.

    Test Steps:
        1. Create an instance of `DiagralAPI` with the provided credentials.
        2. Call the `login` method to authenticate and obtain an access token.
        3. Attempt to call the `get_system_status` method without providing a pincode.
        4. Verify that an `AuthenticationError` is raised, indicating that a pincode is required.

    Expected Result:
        - An `AuthenticationError` is raised when attempting to get the system status without a pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.get_system_status()


#############################################
# DiagralAPI System Interraction Test Cases #
#############################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_start_system(mock_request):
    """Test the start_system method of the DiagralAPI class.

    This test mocks the responses for the login and get_system_status API calls.
    It verifies that the start_system method returns a SystemStatus object with
    the expected status and activated_groups attributes.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Assertions:
        - The system_status is an instance of SystemStatus.
        - The status attribute of system_status is "TEMPO_GROUP".
        - The activated_groups attribute of system_status is an empty list.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"status": "TEMPO_GROUP", "activated_groups": []},
            200,
        ),  # Response for __system_action
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.start_system()
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "TEMPO_GROUP"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_start_system_without_apikey(mock_request):
    """Test the `start_system` method of the `DiagralAPI` class without providing an API key.

    This test mocks the request to simulate a successful login response and then attempts
    to start the system. It expects an `AuthenticationError` to be raised due to the missing
    API key.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Raises:
        AuthenticationError: If the system cannot be started due to missing API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.start_system()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_start_system_without_pincode(mock_request):
    """Test the `start_system` method of the `DiagralAPI` class without providing a pincode.

    This test mocks the `mock_request` to simulate the login response with a fake access token.
    It then attempts to start the system without a pincode, expecting an `AuthenticationError` to be raised.

    Args:
        mock_request (Mock): The mock object for simulating API requests.

    Raises:
        AuthenticationError: If the system cannot be started without a pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.start_system()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_stop_system(mock_request):
    """Test the stop_system method of the DiagralAPI class.

    This test uses a mock request to simulate the responses from the API.
    It verifies that the system is stopped correctly and the status is updated.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Steps:
    1. Set up the mock request to return predefined responses for login and system action.
    2. Create an instance of DiagralAPI with the necessary credentials.
    3. Log in to the API.
    4. Call the stop_system method to stop the system.
    5. Assert that the returned system status is an instance of SystemStatus.
    6. Assert that the system status is "OFF" and no groups are activated.

    Expected Result:
    The system status should be "OFF" and no groups should be activated.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"status": "OFF", "activated_groups": []},
            200,
        ),  # Response for __system_action
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.stop_system()
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "OFF"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_stop_system_without_apikey(mock_request):
    """Test stopping the system without an API key.

    This test simulates the scenario where the system is stopped without providing
    an API key. It mocks the login request to return a fake access token and then
    attempts to stop the system. The test expects an AuthenticationError to be raised.

    Args:
        mock_request (MagicMock): The mock object for simulating HTTP requests.

    Raises:
        AuthenticationError: If the system stop is attempted without a valid API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.stop_system()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_stop_system_without_pincode(mock_request):
    """Test stopping the system without providing a pincode.

    This test mocks the request to simulate the login response and then attempts
    to stop the system without a pincode. It verifies that an AuthenticationError
    is raised in this scenario.

    Args:
        mock_request (Mock): The mock object for simulating HTTP requests.

    Raises:
        AuthenticationError: If stopping the system without a pincode fails.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.stop_system()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_presence(mock_request):
    """Test the presence method of the DiagralAPI class.

    This test uses a mock request to simulate the responses from the Diagral API.
    It verifies that the presence method returns a SystemStatus object with the
    correct status and activated_groups attributes.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Assertions:
        - The system_status is an instance of SystemStatus.
        - The status attribute of system_status is "PRESENCE".
        - The activated_groups attribute of system_status is an empty list.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"status": "PRESENCE", "activated_groups": []},
            200,
        ),  # Response for __system_action
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.presence()
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "PRESENCE"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_presence_without_apikey(mock_request):
    """Test the `presence` method of the `DiagralAPI` class without providing an API key.

    This test simulates a scenario where the `presence` method is called without an API key,
    expecting an `AuthenticationError` to be raised.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Setup:
        - Mocks the response for the login request to return a fake access token.

    Test Steps:
        1. Create an instance of `DiagralAPI` with the provided credentials.
        2. Call the `login` method to authenticate.
        3. Attempt to call the `presence` method.
        4. Verify that an `AuthenticationError` is raised.

    Raises:
        AuthenticationError: If the `presence` method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.presence()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_presence_without_pincode(mock_request):
    """Test the presence method of DiagralAPI without providing a pincode.

    This test mocks the request to simulate a successful login response and then
    attempts to call the presence method. It expects an AuthenticationError to be
    raised due to the absence of a pincode.

    Args:
        mock_request (Mock): The mock object for simulating API requests.

    Raises:
        AuthenticationError: If the presence method is called without a pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.presence()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_1(mock_request):
    """Test the partial start of the system with group 1.

    This test mocks the requests to the Diagral API to simulate the login and
    partial start system actions. It verifies that the system status returned
    by the partial start system action is as expected.

    Args:
        mock_request (Mock): The mock object for simulating API requests.

    Assertions:
        - The system status is an instance of SystemStatus.
        - The system status has a status of "TEMPO_1".
        - The system status has an empty list of activated groups.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"status": "TEMPO_1", "activated_groups": []},
            200,
        ),  # Response for __system_action
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.partial_start_system(1)
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "TEMPO_1"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_1_without_apikey(mock_request):
    """Test the partial_start_system method of DiagralAPI without an API key.

    This test simulates a scenario where the user attempts to start the system
    partially without providing an API key. It mocks the login request to return
    a fake access token and then attempts to start the system. The test expects
    an AuthenticationError to be raised due to the missing API key.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests.

    Raises:
        AuthenticationError: If the partial_start_system method is called without
                             a valid API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.partial_start_system(1)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_1_without_pincode(mock_request):
    """Test the partial_start_system method of DiagralAPI without providing a pincode.

    This test mocks the request to return a fake access token upon login and then
    attempts to start the system partially without a pincode. It expects an
    AuthenticationError to be raised.

    Args:
        mock_request (MagicMock): Mock object to simulate API requests.

    Raises:
        AuthenticationError: If the system cannot be started without a pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.partial_start_system(1)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_2(mock_request):
    """Test the partial start of the system with mode 2.

    This test mocks the request responses for the login and system action endpoints.
    It verifies that the `partial_start_system` method of the `DiagralAPI` class
    correctly handles the response and returns a `SystemStatus` object with the expected
    status and activated groups.

    Args:
        mock_request (Mock): The mock object for simulating HTTP requests.

    Assertions:
        - The returned `system_status` is an instance of `SystemStatus`.
        - The `status` attribute of `system_status` is "TEMPO_2".
        - The `activated_groups` attribute of `system_status` is an empty list.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {"status": "TEMPO_2", "activated_groups": []},
            200,
        ),  # Response for __system_action
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.partial_start_system(2)
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "TEMPO_2"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_2_without_apikey(mock_request):
    """Test the partial_start_system method of the DiagralAPI class without an API key.

    This test simulates a scenario where the user attempts to start the system partially
    without providing an API key. It mocks the login request to return a fake access token
    and then attempts to start the system partially. The test expects an AuthenticationError
    to be raised due to the missing API key.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests.

    Raises:
        AuthenticationError: If the partial_start_system method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.partial_start_system(2)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_2_without_pincode(mock_request):
    """Test the partial_start_system method of the DiagralAPI class without providing a pincode.

    This test mocks the request to the Diagral API and simulates a successful login response.
    It then attempts to partially start the system with an invalid pincode, expecting an
    AuthenticationError to be raised.

    Args:
        mock_request (MagicMock): Mock object to simulate API requests.

    Raises:
        AuthenticationError: If the partial_start_system method is called without a valid pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.partial_start_system(2)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_partial_start_system_3_failed(mock_request):
    """Test the partial_start_system method of the DiagralAPI class when the system fails to start partially.

    This test mocks the request to the Diagral API and simulates a successful login response.
    It then attempts to partially start the system with an invalid parameter (3) and expects
    a ConfigurationError to be raised.

    Args:
        mock_request (MagicMock): The mock object for simulating API requests.

    Raises:
        ConfigurationError: If the partial start system fails due to invalid configuration.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(ConfigurationError):
            await diagral.partial_start_system(3)


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_activate_group(mock_request):
    """Test the activation of a group using the DiagralAPI.

    This test simulates the activation of a group by mocking the responses for login,
    getting configuration, and activating the group. It verifies that the system status
    is correctly updated and that the activated groups are as expected.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Steps:
    1. Mock the responses for login, get_configuration, and __action_group_system.
    2. Create an instance of DiagralAPI with the provided credentials.
    3. Perform login and get_configuration operations.
    4. Activate the group with IDs [1, 2].
    5. Assert that the returned system status is an instance of SystemStatus.
    6. Assert that the system status is "TEMPO_GROUP".
    7. Assert that the activated groups are [1, 2].

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("configuration_sample.json"),
            200,
        ),  # Response for get_configuration
        (
            {"status": "TEMPO_GROUP", "activated_groups": [1, 2]},
            200,
        ),  # Response for __action_group_system
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.get_configuration()
        system_status = await diagral.activate_group([1, 2])
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "TEMPO_GROUP"
        assert system_status.activated_groups == [1, 2]


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_activate_group_without_apikey(mock_request):
    """Test the `activate_group` method of the `DiagralAPI` class without providing an API key.

    This test mocks the request to simulate the login response and verifies that an
    `AuthenticationError` is raised when attempting to activate a group without an API key.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests.

    Raises:
        AuthenticationError: If the activation of the group fails due to missing API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.activate_group([1, 2])


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_activate_group_without_pincode(mock_request):
    """Test the activation of a group without providing a pincode.

    This test mocks the request to the Diagral API and simulates the response for a login request.
    It then attempts to activate a group without a pincode and expects an AuthenticationError to be raised.

    Args:
        mock_request (Mock): The mock object for simulating API requests.

    Raises:
        AuthenticationError: If the activation of the group fails due to missing pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.activate_group([1, 2])


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_activate_group_invalid_group(mock_request):
    """Test the activation of a group with an invalid group ID.

    This test simulates the activation of a group with an invalid group ID (99)
    and expects a ConfigurationError to be raised. It uses a mock request to
    simulate the responses for login and get_configuration API calls.

    Args:
        mock_request (Mock): A mock object to simulate API responses.

    Raises:
        ConfigurationError: If an invalid group ID is provided.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("configuration_sample.json"),
            200,
        ),  # Response for get_configuration
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.get_configuration()
        with pytest.raises(ConfigurationError):
            await diagral.activate_group([1, 2, 99])


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_disable_group(mock_request):
    """Test the disable_group method of the DiagralAPI class.

    This test uses a mock request to simulate API responses for login, get_configuration,
    and disable_group actions. It verifies that the disable_group method correctly disables
    the specified groups and returns the expected system status.

    Args:
        mock_request (MagicMock): A mock object to simulate API requests and responses.

    Assertions:
        - The system status returned by disable_group is an instance of SystemStatus.
        - The status of the system is "OFF".
        - The activated_groups list is empty, indicating that the groups were successfully disabled.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("configuration_sample.json"),
            200,
        ),  # Response for get_configuration
        (
            {"status": "OFF", "activated_groups": []},
            200,
        ),  # Response for __action_group_system
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.get_configuration()
        system_status = await diagral.disable_group([1, 2])
        assert isinstance(system_status, SystemStatus)
        assert system_status.status == "OFF"
        assert system_status.activated_groups == []


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_disable_group_without_apikey(mock_request):
    """Test the `disable_group` method of the `DiagralAPI` class without providing an API key.

    This test simulates a scenario where the user attempts to disable a group of devices
    without an API key, expecting an `AuthenticationError` to be raised.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Setup:
        - Mocks the login response to return a fake access token.

    Test Steps:
        1. Create an instance of `DiagralAPI` with the provided credentials.
        2. Call the `login` method to authenticate.
        3. Attempt to disable a group of devices without an API key.
        4. Verify that an `AuthenticationError` is raised.

    Raises:
        AuthenticationError: If the `disable_group` method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.disable_group([1, 2])


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_disable_group_without_pincode(mock_request):
    """Test the `disable_group` method of the `DiagralAPI` class without providing a pincode.

    This test mocks the request to simulate the login response and verifies that the
    `disable_group` method raises an `AuthenticationError` when attempting to disable
    groups without a pincode.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests.

    Raises:
        AuthenticationError: If the `disable_group` method is called without a pincode.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.disable_group([1, 2])


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_disable_group_invalid_group(mock_request):
    """Test the `disable_group` method with an invalid group.

    This test simulates the scenario where the `disable_group` method is called with an invalid group ID.
    It uses a mock request to simulate the responses for login and get_configuration API calls.

    Steps:
    1. Mock the responses for the login and get_configuration API calls.
    2. Create an instance of `DiagralAPI` with the provided credentials.
    3. Perform login and get_configuration operations.
    4. Attempt to disable a group with an invalid group ID and expect a `ConfigurationError` to be raised.

    Args:
        mock_request (Mock): The mock object to simulate API responses.

    Raises:
        ConfigurationError: If an invalid group ID is provided.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            load_sample("configuration_sample.json"),
            200,
        ),  # Response for get_configuration
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.get_configuration()
        with pytest.raises(ConfigurationError):
            await diagral.activate_group([1, 2, 99])


###################################
# DiagralAPI Anomalies Test Cases #
###################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_anomalies(mock_request):
    """Test the `get_anomalies` method.

    This test simulates the scenario where the `get_anomalies` method is called to retrieve anomalies from the Diagral API.
    It uses a mock request to simulate the responses for login and get_anomalies API calls.

    Steps:
    1. Mock the responses for the login and get_anomalies API calls.
    2. Create an instance of `DiagralAPI` with the provided credentials.
    3. Perform login and get_anomalies operations.
    4. Verify the structure and content of the anomalies retrieved.

    Args:
        mock_request (Mock): The mock object to simulate API responses.

    Asserts:
        - The anomalies object is an instance of `Anomalies`.
        - The central anomalies are an instance of `AnomalyDetail`.
        - The central anomaly names are an instance of `AnomalyName`.
        - The sensor anomalies are an instance of `AnomalyDetail`.
        - The sensor anomaly names are an instance of `AnomalyName`.
        - The sensor details (serial, index, group, label) match the expected values.
        - The sensor anomaly names match the expected values.
        - The central anomaly names match the expected values.

    """

    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {
                "created_at": "2025-02-16T10:15:12.625165",
                "sensors": [
                    {
                        "serial": "12345678",
                        "index": 1,
                        "group": 2,
                        "label": "Sensor Test",
                        "anomaly_names": [
                            {"id": 12345678, "name": "TestSensorAnomaly"}
                        ],
                    }
                ],
                "central": [
                    {
                        "anomaly_names": [
                            {"id": 12345678, "name": "mainPowerSupplyAlert"}
                        ]
                    }
                ],
            },
            200,
        ),  # Response for get_anomalies
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        anomalies: Anomalies = await diagral.get_anomalies()
        assert isinstance(anomalies, Anomalies)
        assert isinstance(anomalies.created_at, datetime)
        assert isinstance(anomalies.central[0], AnomalyDetail)
        assert isinstance(anomalies.central[0].anomaly_names[0], AnomalyName)
        assert isinstance(anomalies.sensors[0], AnomalyDetail)
        assert isinstance(anomalies.sensors[0].anomaly_names[0], AnomalyName)
        assert anomalies.created_at == datetime(
            2025, 2, 16, 10, 15, 12, 625165, tzinfo=timezone.utc
        )
        assert anomalies.sensors[0].serial == "12345678"
        assert anomalies.sensors[0].index == 1
        assert anomalies.sensors[0].group == 2
        assert anomalies.sensors[0].label == "Sensor Test"
        assert anomalies.sensors[0].anomaly_names[0].id == 12345678
        assert anomalies.sensors[0].anomaly_names[0].name == "TestSensorAnomaly"
        assert anomalies.central[0].anomaly_names[0].id == 12345678
        assert anomalies.central[0].anomaly_names[0].name == "mainPowerSupplyAlert"


#################################
# DiagralAPI WebHook Test Cases #
#################################


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_webhook(mock_request):
    """Test the `get_webhook` method of the `DiagralAPI` class.

    This test mocks the responses for the login and webhook retrieval actions.
    It verifies that the `get_webhook` method returns a `Webhook` object with the expected attributes.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Assertions:
        - The returned object is an instance of `Webhook`.
        - The `transmitter_id` attribute of the webhook is "TRANSMITTER".
        - The `webhook_url` attribute of the webhook is `WEBHOOK_URL`.
        - The `alert` subscription of the webhook is `True`.
        - The `anomaly` subscription of the webhook is `True`.
        - The `state` subscription of the webhook is `True`.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {
                "transmitter_id": "TRANSMITTER",
                "webhook_url": WEBHOOK_URL,
                "subscriptions": {"anomaly": True, "alert": True, "state": True},
            },
            200,
        ),  # Response for __webhook_action_create_update
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        webhook = await diagral.get_webhook()
        assert isinstance(webhook, Webhook)
        assert webhook.transmitter_id == "TRANSMITTER"
        assert webhook.webhook_url == WEBHOOK_URL
        assert webhook.subscriptions.alert is True
        assert webhook.subscriptions.anomaly is True
        assert webhook.subscriptions.state is True


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_webhook_without_apikey(mock_request):
    """Test the `get_webhook` method of the `DiagralAPI` class without providing an API key.

    This test mocks the request to simulate the login response and checks if the
    `get_webhook` method raises an `AuthenticationError` when called without an API key.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests.

    Raises:
        AuthenticationError: If the `get_webhook` method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.get_webhook()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_register_webhook(mock_request):
    """Test the `register_webhook` method of the `DiagralAPI` class.

    This test verifies that the `register_webhook` method correctly registers a webhook
    with the specified URL and subscriptions. It mocks the responses for the login and
    webhook registration actions to ensure the method behaves as expected.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Assertions:
        - The returned webhook object is an instance of the `Webhook` class.
        - The `transmitter_id` of the webhook matches the expected value.
        - The `webhook_url` of the webhook matches the expected value.
        - The `alert` subscription of the webhook is set to True.
        - The `anomaly` subscription of the webhook is set to True.
        - The `state` subscription of the webhook is set to True.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {
                "transmitter_id": "TRANSMITTER",
                "webhook_url": WEBHOOK_URL,
                "subscriptions": {"anomaly": True, "alert": True, "state": True},
            },
            200,
        ),  # Response for __webhook_action_create_update
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        webhook = await diagral.register_webhook(
            webhook_url=WEBHOOK_URL,
            subscribe_to_anomaly=True,
            subscribe_to_alert=True,
            subscribe_to_state=True,
        )
        assert isinstance(webhook, Webhook)
        assert webhook.transmitter_id == "TRANSMITTER"
        assert webhook.webhook_url == WEBHOOK_URL
        assert webhook.subscriptions.alert is True
        assert webhook.subscriptions.anomaly is True
        assert webhook.subscriptions.state is True


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_register_webhook_without_apikey(mock_request):
    """Test the `register_webhook` method of the `DiagralAPI` class without providing an API key.

    This test simulates the scenario where the user attempts to register a webhook without an API key.
    It mocks the request to return a fake access token upon login and then checks if the `register_webhook`
    method raises an `AuthenticationError` when called without an API key.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests and responses.

    Raises:
        AuthenticationError: If the `register_webhook` method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.register_webhook(
                webhook_url=WEBHOOK_URL,
                subscribe_to_anomaly=True,
                subscribe_to_alert=True,
                subscribe_to_state=True,
            )


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_register_webhook_with_bad_url(mock_request):
    """Test the `register_webhook` method with an invalid URL format.

    This test ensures that the `register_webhook` method raises a `ValidationError`
    when provided with a webhook URL that has an incorrect format.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Setup:
        - Mocks the login response with a fake access token.

    Test Steps:
        1. Create an instance of `DiagralAPI` with the necessary credentials.
        2. Call the `login` method to authenticate.
        3. Attempt to register a webhook with an invalid URL format.
        4. Verify that a `ValidationError` is raised.

    Raises:
        ValidationError: If the webhook URL format is invalid.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(ValidationError):
            await diagral.register_webhook(
                webhook_url="htt://badurl_format",
                subscribe_to_anomaly=True,
                subscribe_to_alert=True,
                subscribe_to_state=True,
            )


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_register_webhook_subscription_already_exist(mock_request):
    """Test the `register_webhook` method when the webhook subscription already exists.

    This test simulates the scenario where the webhook subscription already exists
    by mocking the responses of the `DiagralAPI` methods. It ensures that the
    `DiagralAPIError` is raised when attempting to register a webhook that is
    already subscribed.

    Args:
        mock_request (MagicMock): Mock object to simulate API responses.

    Raises:
        DiagralAPIError: If the webhook subscription already exists.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        DiagralAPIError(
            "Subscription already exists"
        ),  # Response for __webhook_action_create_update
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(DiagralAPIError):
            await diagral.register_webhook(
                webhook_url=WEBHOOK_URL,
                subscribe_to_anomaly=True,
                subscribe_to_alert=True,
                subscribe_to_state=True,
            )


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_register_webhook_no_subscription_exist(mock_request):
    """Test the `register_webhook` method when no subscription exists.

    This test simulates the scenario where the `register_webhook` method is called,
    but there is no existing subscription for the provided serial ID. It mocks the
    responses for the login and webhook registration actions to trigger the
    appropriate error handling.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests and responses.

    Raises:
        DiagralAPIError: Expected to be raised when there is no subscription for the given serial ID.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        DiagralAPIError(
            "There is no subscription for XXXX"
        ),  # Response for __webhook_action_create_update
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(DiagralAPIError):
            await diagral.register_webhook(
                webhook_url=WEBHOOK_URL,
                subscribe_to_anomaly=True,
                subscribe_to_alert=True,
                subscribe_to_state=True,
            )


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_update_webhook(mock_request):
    """Test the `update_webhook` method of the `DiagralAPI` class.

    This test mocks the responses for the login and webhook update actions, and verifies
    that the webhook is correctly registered with the expected attributes.

    Args:
        mock_request (Mock): A mock object to simulate HTTP requests and responses.

    Assertions:
        - The returned webhook is an instance of the `Webhook` class.
        - The `transmitter_id` of the webhook is "TRANSMITTER".
        - The `webhook_url` of the webhook is `WEBHOOK_URL`.
        - The `alert` subscription of the webhook is `True`.
        - The `anomaly` subscription of the webhook is `True`.
        - The `state` subscription of the webhook is `True`.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        (
            {
                "transmitter_id": "TRANSMITTER",
                "webhook_url": WEBHOOK_URL,
                "subscriptions": {"anomaly": True, "alert": True, "state": True},
            },
            200,
        ),  # Response for __webhook_action_create_update
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        webhook = await diagral.register_webhook(
            webhook_url=WEBHOOK_URL,
            subscribe_to_anomaly=True,
            subscribe_to_alert=True,
            subscribe_to_state=True,
        )
        assert isinstance(webhook, Webhook)
        assert webhook.transmitter_id == "TRANSMITTER"
        assert webhook.webhook_url == WEBHOOK_URL
        assert webhook.subscriptions.alert is True
        assert webhook.subscriptions.anomaly is True
        assert webhook.subscriptions.state is True


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_delete_webhook(mock_request):
    """Test the delete_webhook method of the DiagralAPI class.

    This test simulates the deletion of a webhook by mocking the responses for the login
    and delete_webhook API calls. It verifies that the delete_webhook method is called
    successfully after logging in.

    Args:
        mock_request (MagicMock): A mock object to simulate API responses.

    Side Effects:
        Sets the side_effect attribute of mock_request to simulate API responses.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        ({}, 204),  # Response for delete_webhook
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        await diagral.delete_webhook()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_delete_webhook_failure(mock_request):
    """Test the failure scenario of deleting a webhook with insufficient permissions.

    This test simulates the process of attempting to delete a webhook using the
    DiagralAPI when the user does not have the necessary permissions. It mocks
    the responses for the login and delete_webhook requests to trigger an
    AuthenticationError.

    Args:
        mock_request (MagicMock): A mock object to simulate API requests and responses.

    Raises:
        AuthenticationError: If the user does not have the right permissions to delete the webhook.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
        AuthenticationError(
            "The user does not have the right permissions"
        ),  # Response for delete_webhook
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.delete_webhook()


@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_delete_webhook_without_apikey(mock_request):
    """Test the `delete_webhook` method of the `DiagralAPI` class without providing an API key.

    This test simulates the scenario where the `delete_webhook` method is called without an API key,
    and verifies that an `AuthenticationError` is raised.

    Args:
        mock_request (MagicMock): A mock object to simulate HTTP requests and responses.

    Setup:
        - Mocks the response for the login request with a fake access token.

    Test Steps:
        1. Create an instance of `DiagralAPI` with the provided credentials.
        2. Call the `login` method to authenticate.
        3. Attempt to call the `delete_webhook` method without an API key.
        4. Verify that an `AuthenticationError` is raised.

    Raises:
        AuthenticationError: If the `delete_webhook` method is called without an API key.

    """
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),  # Response for login
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        with pytest.raises(AuthenticationError):
            await diagral.delete_webhook()
