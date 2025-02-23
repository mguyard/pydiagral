import asyncio  # noqa: D100
import logging
import os

from dotenv import load_dotenv

from src.pydiagral import DiagralAPI, DiagralAPIError

# Load environment variables
load_dotenv()

# Logging configuration
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
SERIAL_ID = os.getenv("SERIAL_ID")
API_KEY = os.getenv("API_KEY")  # Optional
SECRET_KEY = os.getenv("SECRET_KEY")  # Optional
PIN_CODE = int(os.getenv("PIN_CODE"))  # Optional
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Optional

######################################## CUSTOMIZE THE TESTS ########################################
#   What do you want to test ?
#   Switch to True the actions you want to test
APIKEY_CREATION = True
APIKEY_DELETION = True
LIST_GROUPS = True
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

if APIKEY_CREATION:
    API_KEY = None
    SECRET_KEY = None


async def test_diagral_api():  # noqa: D103
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
        logger.info("Initialisation de DiagralAPI réussie")

        # Connection to the Diagral API
        async with diagral as alarm:
            logger.info("Connection to the Diagral API successful")
            if APIKEY_CREATION and (not API_KEY or not SECRET_KEY):
                await alarm.login()  # Login to the API
                # await asyncio.sleep(3700) # Wait for the access token to expire
                api_keys = await alarm.set_apikey()  # Create a new API key
                logger.info("API Key: %s", api_keys.api_key)  # Display the API key
                logger.info(
                    "Secret Key: %s", api_keys.secret_key
                )  # Display the secret key
                await (
                    alarm.validate_apikey()
                )  # Validate the API key - Optional as already done in set_apikey
                if APIKEY_DELETION:
                    await alarm.delete_apikey()  # Delete the API key

            await alarm.get_configuration()  # Get the configuration

            if LIST_GROUPS:
                await alarm.get_devices_info()
                for group in alarm.alarm_configuration.groups:
                    logger.info(
                        "Group %i: %s",
                        group.index,
                        group.name,
                    )

            if LIST_SYSTEM_DETAILS:
                system_details = (
                    await alarm.get_system_details()
                )  # Get the system details
                logger.info("System Details: %s", system_details)

            if LIST_SYSTEM_STATUS:
                system_status = await alarm.get_system_status()  # Get the system status
                logger.info("System Status: %s", system_status)

            if LIST_SYSTEM_CONFIGURATION:
                logger.info(
                    "System Configuration: %s",
                    alarm.alarm_configuration.grp_marche_partielle2,
                )

            if WEHBOOK_REGISTRATION and WEBHOOK_URL:
                logger.info("-----> WEBHOOK <-----")
                webhook_register_output = await alarm.register_webhook(
                    webhook_url=WEBHOOK_URL,
                    subscribe_to_anomaly=True,
                    subscribe_to_alert=True,
                    subscribe_to_state=True,
                )
                logger.info("Webhook Register Output: %s", webhook_register_output)
                webhook_update_output = await alarm.update_webhook(
                    webhook_url=WEBHOOK_URL,
                    subscribe_to_anomaly=True,
                    subscribe_to_alert=True,
                    subscribe_to_state=True,
                )
                logger.info("Webhook Update Output: %s", webhook_update_output)
                if WEBHOOK_DELETION:
                    await alarm.delete_webhook()
                    webhook_sub = await alarm.get_webhook()

                logger.info("Webhook Subscription: %s", webhook_sub)

            if GET_ANOMALIES:
                logger.info("-----> ANOMALIES <-----")
                anomalies = await alarm.get_anomalies()
                logger.info("Anomalies: %s", anomalies)

            if TEST_FULL_ACTIONS:
                start_result = await alarm.start_system()  # Start the system
                logger.info("Start System with result: %s", start_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                stop_result = await alarm.stop_system()  # Stop the system
                logger.info("Stop System with result: %s", stop_result)

            if TEST_PRESENCE:
                presence_result = await alarm.presence()  # Activate the presence mode
                logger.info("Presence with result: %s", presence_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                stop_result = await alarm.stop_system()  # Stop the system
                logger.info("Stop System with result: %s", stop_result)

            if TEST_PARTIAL_ACTIONS:
                activategroup_result = await alarm.activate_group(groups=[1, 2])
                logger.info("Activate Group with result: %s", activategroup_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                disablegroup_result = await alarm.disable_group(groups=[2])
                logger.info("Disable Group with result: %s", disablegroup_result)
                await asyncio.sleep(30)  # Wait for 30 seconds
                stop_result = await alarm.stop_system()
                logger.info("Stop System with result: %s", stop_result)

    except DiagralAPIError as e:
        logger.error("Erreur : %s", e)


if __name__ == "__main__":
    asyncio.run(test_diagral_api())
