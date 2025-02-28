import asyncio  # noqa: D100
import logging
import os

from dotenv import load_dotenv

from pydiagral.models import (
    Anomalies,
    ApiKeyWithSecret,
    SystemDetails,
    SystemStatus,
    TryConnectResult,
    Webhook,
)
from src.pydiagral import DiagralAPI, DiagralAPIError

# Load environment variables
load_dotenv()

# Logging configuration
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_LOGGER: logging.Logger = logging.getLogger(__name__)

# Connection information (replace with your own data)
# For this, create a .env file in the root of the project with the following content:
#   USERNAME=your_username
#   PASSWORD=your_password
#   SERIAL_ID=your_serial_id
#   API_KEY=your_api_key
#   SECRET_KEY=your_secret_key
#   PIN_CODE=your_pin_code
#   WEBHOOK_URL=your_webhook_url
#   LOG_LEVEL=INFO
USERNAME: str | None = os.getenv("USERNAME")
PASSWORD: str | None = os.getenv("PASSWORD")
SERIAL_ID: str | None = os.getenv("SERIAL_ID")
API_KEY: str | None = os.getenv("API_KEY")  # Optional
SECRET_KEY: str | None = os.getenv("SECRET_KEY")  # Optional
PIN_CODE = int(os.getenv("PIN_CODE"))  # Optional
WEBHOOK_URL: str | None = os.getenv("WEBHOOK_URL")  # Optional

######################################## CUSTOMIZE THE TESTS ########################################
#   What do you want to test ?
#   Switch to True the actions you want to test
TRY_CONNECTION_WITH_KEYS = False
TRY_CONNECTION_WITHOUT_KEYS = False
TRY_CONNECTION_WITH_KEYS_EPHEMERAL = False
TRY_CONNECTION_WITHOUT_KEYS_EPHEMERAL = False
APIKEY_CREATION = False
APIKEY_DELETION = False
LIST_GROUPS = False
LIST_SYSTEM_DETAILS = False
LIST_SYSTEM_STATUS = False
LIST_SYSTEM_CONFIGURATION = False
WEHBOOK_REGISTRATION = False
WEBHOOK_DELETION = False
GET_ANOMALIES = False
TEST_FULL_ACTIONS = False
TEST_PRESENCE = False
TEST_PARTIAL_ACTIONS = False

######################################## DON'T MODIFY BELOW THIS LINE ########################################

if (
    APIKEY_CREATION
    or TRY_CONNECTION_WITHOUT_KEYS
    or TRY_CONNECTION_WITHOUT_KEYS_EPHEMERAL
):
    API_KEY = None
    SECRET_KEY = None


async def test_diagral_api() -> None:  # noqa: D103,C901
    try:
        # Initialization of the DiagralAPI object
        diagral = DiagralAPI(
            username=USERNAME,
            password=PASSWORD,
            serial_id=SERIAL_ID,
            apikey=API_KEY,
            secret_key=SECRET_KEY,
            pincode=PIN_CODE,
        )
        _LOGGER.info("Initialisation de DiagralAPI réussie")

        # Connection to the Diagral API
        async with diagral as alarm:
            _LOGGER.info("Connection to the Diagral API successful")
            if APIKEY_CREATION and (not API_KEY or not SECRET_KEY):
                await alarm.login()  # Login to the API
                # await asyncio.sleep(3700) # Wait for the access token to expire
                api_keys: ApiKeyWithSecret = (
                    await alarm.set_apikey()
                )  # Create a new API key
                _LOGGER.info("API Key: %s", api_keys.api_key)  # Display the API key
                _LOGGER.info(
                    "Secret Key: %s", api_keys.secret_key
                )  # Display the secret key
                await (
                    alarm.validate_apikey()
                )  # Validate the API key - Optional as already done in set_apikey

            if TRY_CONNECTION_WITH_KEYS:
                connection: TryConnectResult = await alarm.try_connection(
                    ephemeral=False
                )  # Try to connect to the API with keys
                if connection.result:
                    _LOGGER.info("Connection (with provided keys) successful")
                else:
                    _LOGGER.error("Connection (with provided keys) failed")

            if TRY_CONNECTION_WITHOUT_KEYS:
                connection: TryConnectResult = await alarm.try_connection(
                    ephemeral=False
                )  # Try to connect to the API with keys
                if connection.result:
                    _LOGGER.info("Connection (with provided keys) successful")
                    _LOGGER.info("Generated keys are : %s", connection.keys)
                    _LOGGER.info("Running cleanup by deleting the generated keys")
                    await alarm.delete_apikey(connection.keys.api_key)  # For cleanup
                else:
                    _LOGGER.error("Connection (with provided keys) failed")

            if TRY_CONNECTION_WITH_KEYS_EPHEMERAL:
                connection: TryConnectResult = await alarm.try_connection(
                    ephemeral=True
                )  # Try to connect to the API without keys
                if connection.result:
                    if connection.keys is not None:
                        _LOGGER.warning(
                            "Keys was returned. Not a normal behavior as keys was provided"
                        )
                    _LOGGER.info("Connection (without provided keys) successful")
                else:
                    _LOGGER.error("Connection (without provided keys) failed")

            if TRY_CONNECTION_WITHOUT_KEYS_EPHEMERAL:
                connection: TryConnectResult = await alarm.try_connection(
                    ephemeral=True
                )  # Try to connect to the API without keys
                if connection.result:
                    if connection.keys is not None:
                        _LOGGER.warning(
                            "Keys was returned. Not a normal behavior as keys was provided"
                        )
                    _LOGGER.info("Connection (without provided keys) successful")
                else:
                    _LOGGER.error("Connection (without provided keys) failed")

            if LIST_GROUPS:
                await alarm.get_devices_info()
                for group in alarm.alarm_configuration.groups:
                    _LOGGER.info(
                        "Group %i: %s",
                        group.index,
                        group.name,
                    )

            if LIST_SYSTEM_DETAILS:
                system_details: SystemDetails = (
                    await alarm.get_system_details()
                )  # Get the system details
                _LOGGER.info("System Details: %s", system_details)

            if LIST_SYSTEM_STATUS:
                system_status: SystemStatus = (
                    await alarm.get_system_status()
                )  # Get the system status
                _LOGGER.info("System Status: %s", system_status)

            if LIST_SYSTEM_CONFIGURATION:
                if not alarm.alarm_configuration:
                    await alarm.get_configuration()  # Get the configuration
                _LOGGER.info(
                    "System Configuration: %s",
                    alarm.alarm_configuration.grp_marche_partielle2,
                )

            if WEHBOOK_REGISTRATION and WEBHOOK_URL:
                _LOGGER.info("-----> WEBHOOK <-----")
                webhook_register_output: Webhook | None = await alarm.register_webhook(
                    webhook_url=WEBHOOK_URL,
                    subscribe_to_anomaly=True,
                    subscribe_to_alert=True,
                    subscribe_to_state=True,
                )
                _LOGGER.info("Webhook Register Output: %s", webhook_register_output)
                webhook_update_output: Webhook | None = await alarm.update_webhook(
                    webhook_url=WEBHOOK_URL,
                    subscribe_to_anomaly=True,
                    subscribe_to_alert=True,
                    subscribe_to_state=True,
                )
                _LOGGER.info("Webhook Update Output: %s", webhook_update_output)
                if WEBHOOK_DELETION:
                    await alarm.delete_webhook()
                    webhook_sub: Webhook = await alarm.get_webhook()

                _LOGGER.info("Webhook Subscription: %s", webhook_sub)

            if GET_ANOMALIES:
                _LOGGER.info("-----> ANOMALIES <-----")
                anomalies: Anomalies | dict = await alarm.get_anomalies()
                _LOGGER.info("Anomalies: %s", anomalies)

            if TEST_FULL_ACTIONS:
                start_result: SystemStatus = (
                    await alarm.start_system()
                )  # Start the system
                _LOGGER.info("Start System with result: %s", start_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                stop_result: SystemStatus = await alarm.stop_system()  # Stop the system
                _LOGGER.info("Stop System with result: %s", stop_result)

            if TEST_PRESENCE:
                presence_result: SystemStatus = (
                    await alarm.presence()
                )  # Activate the presence mode
                _LOGGER.info("Presence with result: %s", presence_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                stop_result = await alarm.stop_system()  # Stop the system
                _LOGGER.info("Stop System with result: %s", stop_result)

            if TEST_PARTIAL_ACTIONS:
                activategroup_result: SystemStatus = await alarm.activate_group(
                    groups=[1, 2]
                )
                _LOGGER.info("Activate Group with result: %s", activategroup_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                disablegroup_result: SystemStatus = await alarm.disable_group(
                    groups=[2]
                )
                _LOGGER.info("Disable Group with result: %s", disablegroup_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                stop_result = await alarm.stop_system()
                _LOGGER.info("Stop System with result: %s", stop_result)

            alarm_name: str = await alarm.get_alarm_name()  # Get the alarm name
            _LOGGER.info("Alarm Name is: %s", alarm_name)

            if (
                APIKEY_DELETION and APIKEY_CREATION
            ):  # Only when the API key has been created
                await alarm.delete_apikey()  # Delete the API key

    except DiagralAPIError as e:
        _LOGGER.error("Erreur : %s", e)


if __name__ == "__main__":
    asyncio.run(test_diagral_api())
