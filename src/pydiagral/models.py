"""Module containing data models for interacting with the Diagral API.

The models include representations for login responses, API key creation and validation,
and other related data structures.
"""

# Minimum Python version: 3.10

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
import logging
import re
import types
from typing import TypeVar, Union, get_args, get_origin, get_type_hints

logger = logging.getLogger(__name__)


#######################################################
# Class for converting between camelCase and snake_case
#######################################################


class CamelCaseModel:
    """CamelCaseModel is a base class for models that need to convert between snake_case and camelCase keys.

    Methods:
        to_dict() -> dict:
            Convert the model instance to a dictionary with camelCase keys.
        _from_dict_recursive(cls, data: dict, target_cls: type[T]) -> T:
            Recursively create an instance of the target class from a dictionary.
        from_dict(cls: type[T], data: dict) -> T:
            Create an instance of the model from a dictionary.
        snake_to_camel(string: str) -> str:
            Convert a snake_case string to camelCase.
        camel_to_snake(string: str) -> str:
            Convert a camelCase string to snake_case.

    Examples:
        >>> @dataclass
        ... class ExampleModel(CamelCaseModel):
        ...     first_name: str
        ...     last_name: str
        ...
        >>> example = ExampleModel(first_name="Luke", last_name="Skywalker")
        >>> example_dict = example.to_dict()
        >>> print(example_dict)
        {'firstName': 'Luke', 'lastName': 'Skywalker'}
        >>> new_example = ExampleModel.from_dict(example_dict)
        >>> print(new_example)
        ExampleModel(first_name='Luke', last_name='Skywalker')

    """

    # Type variable for the class itself
    T = TypeVar("T", bound="CamelCaseModel")

    def to_dict(self) -> dict:
        """Convert the instance attributes to a dictionary, transforming attribute names.

        from snake_case to camelCase and handling nested CamelCaseModel instances.

        Returns:
            dict: A dictionary representation of the instance with camelCase keys.

        Example:
            >>> class ExampleModel(CamelCaseModel):
            ...     first_name: str
            ...     last_name: str
            ...
            >>> example = ExampleModel(first_name="Luke", last_name="Skywalker")
            >>> example.to_dict()
            {'firstName': 'Luke', 'lastName': 'Skywalker'}

        """

        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                if isinstance(v, CamelCaseModel):
                    v = v.to_dict()
                elif isinstance(v, list) and v and isinstance(v[0], CamelCaseModel):
                    v = [item.to_dict() for item in v]
                key = getattr(self.__class__, k).metadata.get(
                    "alias", self.snake_to_camel(k)
                )
                result[key] = v
        return result

    @classmethod
    def _from_dict_recursive(cls: type[T], data: dict, target_cls: type[T]) -> T:
        """Recursively converts a dictionary to an instance of the specified target class.

        This method handles nested dictionaries and lists, converting them to the appropriate
        types as specified by the target class's type hints. It also supports optional fields
        by handling `Union` types and removing `None` from the type hints.

        Args:
            cls (type[T]): The class that this method is a part of.
            data (dict): The dictionary to convert.
            target_cls (type[T]): The target class to convert the dictionary to.

        Returns:
            T: An instance of the target class populated with the data from the dictionary.

        Raises:
            TypeError: If the target class cannot be instantiated with the provided data.

        Notes:
            - The method assumes that the target class and its nested classes (if any) are
              annotated with type hints.
            - The method uses snake_case to camelCase conversion for dictionary keys to match
              the field names in the target class.
            - The method logs detailed debug information about the conversion process.

        """

        logger.debug("Converting data: %s to %s", data, target_cls)

        logger.debug("Extracted target_cls: %s", target_cls)
        if get_origin(target_cls) is Union:
            # Extract the real type by removing None
            target_cls = next(t for t in get_args(target_cls) if t is not type(None))
            logger.debug("Extracted target_cls: %s", target_cls)

        init_values = {}
        fields_dict = {field.name: field for field in fields(target_cls)}
        for field_name, field_type in get_type_hints(target_cls).items():
            field = fields_dict.get(field_name)
            logger.debug("Field Metadata: %s", field.metadata if field else {})
            # alias = cls.snake_to_camel(field_name) # Old version who don't support field with underscore and without alias
            alias = field.metadata.get("alias", field_name)
            logger.debug(
                "Processing field: %s (alias: %s, type: %s)",
                field_name,
                alias,
                field_type,
            )

            logger.debug("Extracted field_type: %s", field_type)
            if get_origin(field_type) is types.UnionType:
                # Extract the real type by removing None
                field_type = next(
                    t for t in get_args(field_type) if t is not type(None)
                )
                logger.debug("Extracted field_type: %s", field_type)

            logger.debug("Checking if alias %s is in data: %s", alias, data)
            if any(alias.lower() == key.lower() for key in data):
                alias = next(key for key in data if alias.lower() == key.lower())
                value = data[alias]
                logger.debug("Found value for %s: %s", alias, value)

                if (
                    isinstance(value, dict)
                    and isinstance(field_type, type)
                    and issubclass(field_type, CamelCaseModel)
                ):
                    logger.debug(
                        "Recursively converting nested dict for field: %s", field_name
                    )
                    init_values[field_name] = cls._from_dict_recursive(
                        value, field_type
                    )
                elif isinstance(value, list) and get_origin(field_type) is list:
                    item_type = get_args(field_type)[0]
                    logger.debug(
                        "Recursively converting list for field: %s with item type: %s",
                        field_name,
                        item_type,
                    )
                    init_values[field_name] = [
                        cls._from_dict_recursive(item, item_type)
                        if isinstance(item, dict)
                        else item
                        for item in value
                    ]
                else:
                    init_values[field_name] = value
            else:
                init_values[field_name] = None
                logger.debug("No value found for %s, setting to None", alias)

        logger.debug("Initialized values for %s: %s", target_cls, init_values)
        return target_cls(**init_values)

    @classmethod
    def from_dict(cls: type[T], data: dict) -> T:
        """Create an instance of the class from a dictionary.

        Args:
            cls (type[T]): The class type to instantiate.
            data (dict): The dictionary containing the data to populate the instance.

        Returns:
            T: An instance of the class populated with the data from the dictionary.

        Example:
            >>> data = {"diagral_id": 123, "user_id": 456, "access_token": "abc123"}
            >>> login_response = LoginResponse.from_dict(data)
            >>> login_response.diagral_id
            123
            >>> login_response.user_id
            456
            >>> login_response.access_token
            'abc123'

        """

        return cls._from_dict_recursive(data, cls)

    @staticmethod
    def snake_to_camel(string: str) -> str:
        """Convert a snake_case string to camelCase.

        Args:
            string (str): The snake_case string to be converted.

        Returns:
            str: The converted camelCase string.

        Example:
            >>> snake_to_camel("example_string")
            'exampleString'

        """

        components = string.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    @staticmethod
    def camel_to_snake(string: str) -> str:
        """Convert a CamelCase string to snake_case.

        Args:
            string (str): The CamelCase string to be converted.

        Returns:
            str: The converted snake_case string.

        Example:
            >>> camel_to_snake("CamelCaseString")
            'camel_case_string'

        """

        # Replace capital letters with _ followed by the lowercase letter
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", string)
        # Handle cases where multiple capitals are together
        s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.lower()


##############################################
# Data models for Diagral API Authentification
##############################################


@dataclass
class LoginResponse(CamelCaseModel):
    """LoginResponse model represents the response received after a successful login.

    Attributes:
        access_token (str): The access token provided for authentication.

    Example:
        >>> response = LoginResponse(
        ...     access_token="abc123",
        ... )
        >>> print(response.access_token)
        abc123

    """

    access_token: str


@dataclass
class ApiKeyWithSecret(CamelCaseModel):
    """ApiKeyWithSecret is a model that represents an API key and its corresponding secret key.

    Attributes:
        api_key (str): The API key, which must be a non-empty string.
        secret_key (str): The secret key associated with the API key, which must also be a non-empty string.

    Methods:
        __post_init__(): Post-initialization processing to validate the API key and secret key.

    Example:
        >>> api_key_with_secret = ApiKeyWithSecret(api_key="your_api_key", secret_key="your_secret_key")
        >>> print(api_key_with_secret.api_key)
        your_api_key
        >>> print(api_key_with_secret.secret_key)
        your_secret_key

    """

    api_key: str
    secret_key: str

    def __post_init__(self):
        """Post-initialization processing to validate API key and secret key."""
        if not self.api_key or not isinstance(self.api_key, str):
            raise ValueError("api_key must be a non-empty string")
        if not self.secret_key or not isinstance(self.secret_key, str):
            raise ValueError("secret_key must be a non-empty string")


@dataclass
class ApiKey(CamelCaseModel):
    """Represents an API key model.

    Attributes:
        api_key (str): The API key as a string.

    Example:
        >>> api_key = ApiKey(api_key="your_api_key")
        >>> print(api_key.api_key)
        your_api_key

    """

    api_key: str


@dataclass
class ApiKeys(CamelCaseModel):
    """ApiKeys model to represent a collection of API keys.

    Attributes:
        api_keys (list[ApiKey]): A list of ApiKey instances.

    Methods:
        from_dict(data: dict) -> ApiKeys:
            Class method to create an instance of ApiKeys from a dictionary.

    Example:
        >>> data = {"api_keys": [{"api_key": "key1"}, {"api_key": "key2"}]}
        >>> api_keys = ApiKeys.from_dict(data)
        >>> print(api_keys.api_keys)
        [ApiKey(api_key='key1'), ApiKey(api_key='key2')]

    """

    api_keys: list[ApiKey]

    @classmethod
    def from_dict(cls, data: dict) -> ApiKeys:
        """Create an instance of ApiKeys from a dictionary."""

        return cls(
            api_keys=[ApiKey(**key_info) for key_info in data.get("api_keys", [])]
        )


#####################################
# Data models for alarm configuration
#####################################


@dataclass
class FirmwareModel(CamelCaseModel):
    """FirmwareModel represents the firmware details of a device.

    Attributes:
        box (str | None): The firmware version of the box, aliased as "BOX".
        central (str | None): The firmware version of the central unit, aliased as "CENTRAL".
        centralradio (str | None): The firmware version of the central radio unit, aliased as "CENTRALRADIO".

    Example:
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> print(firmware.box)
        '1.0.0'
        >>> print(firmware.central)
        '2.0.0'
        >>> print(firmware.centralradio)
        '3.0.0'

    """

    box: str | None = field(default=None, metadata={"alias": "BOX"})
    central: str | None = field(default=None, metadata={"alias": "CENTRAL"})
    centralradio: str | None = field(default=None, metadata={"alias": "CENTRALRADIO"})


@dataclass
class CentralPlugModel(CamelCaseModel):
    """CentralPlugModel represents the central plug device.

    Attributes:
        name (str | None): The name of the central plug device.
        serial (str | None): The serial number of the central plug device.
        vendor (str | None): The vendor of the central plug device.
        firmwares (FirmwareModel | None): The firmware information of the central plug device.

    Example:
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> central_plug = CentralPlugModel(
        ...     name="Central Plug 1",
        ...     serial="123456789",
        ...     vendor="VendorName",
        ...     firmwares=firmware
        ... )
        >>> print(central_plug.name)
        Central Plug 1
        >>> print(central_plug.serial)
        123456789
        >>> print(central_plug.vendor)
        VendorName
        >>> print(central_plug.firmwares.box)
        1.0.0

    """

    name: str | None = None
    serial: str | None = None
    vendor: str | None = None
    firmwares: FirmwareModel | None = None


@dataclass
class Group(CamelCaseModel):
    """Represents a Group model.

    Attributes:
        name (str | None): The name of the group. Defaults to None.
        index (int | None): The index of the group. Defaults to None.
        input_delay (int | None): The input delay of the group, aliased as 'inputDelay'. Defaults to None.
        output_delay (int | None): The output delay of the group, aliased as 'outputDelay'. Defaults to None.

    Example:
        >>> group = Group(name="Group A", index=1, input_delay=10, output_delay=20)
        >>> print(group.name)
        Group A
        >>> print(group.index)
        1
        >>> print(group.input_delay)
        10
        >>> print(group.output_delay)
        20

    """

    name: str | None = None
    index: int | None = None
    input_delay: int | None = field(default=None, metadata={"alias": "inputDelay"})
    output_delay: int | None = field(default=None, metadata={"alias": "outputDelay"})


@dataclass
class ConfAnomaliesModel(CamelCaseModel):
    """ConfAnomaliesModel is a data model that represents various configuration anomalies in a system.

    Attributes:
        radio_alert (bool | None): Indicates if there is a radio alert. Alias: "radioAlert".
        power_supply_alert (bool | None): Indicates if there is a power supply alert. Alias: "powerSupplyAlert".
        autoprotection_mechanical_alert (bool | None): Indicates if there is an autoprotection mechanical alert. Alias: "autoprotectionMechanicalAlert".
        loop_alert (bool | None): Indicates if there is a loop alert. Alias: "loopAlert".
        mask_alert (bool | None): Indicates if there is a mask alert. Alias: "maskAlert".
        sensor_alert (bool | None): Indicates if there is a sensor alert. Alias: "sensorAlert".
        media_gsm_alert (bool | None): Indicates if there is a GSM media alert. Alias: "mediaGSMAlert".
        media_rtc_alert (bool | None): Indicates if there is an RTC media alert. Alias: "mediaRTCAlert".
        media_adsl_alert (bool | None): Indicates if there is an ADSL media alert. Alias: "mediaADSLAlert".
        out_of_order_alert (bool | None): Indicates if there is an out of order alert. Alias: "outOfOrderAlert".
        main_power_supply_alert (bool | None): Indicates if there is a main power supply alert. Alias: "mainPowerSupplyAlert".
        secondary_power_supply_alert (bool | None): Indicates if there is a secondary power supply alert. Alias: "secondaryPowerSupplyAlert".
        default_media_alert (bool | None): Indicates if there is a default media alert. Alias: "defaultMediaAlert".
        autoprotection_wired_alert (bool | None): Indicates if there is an autoprotection wired alert. Alias: "autoprotectionWiredAlert".

    Example:
        >>> anomalies = ConfAnomaliesModel(
        ...     radio_alert=True,
        ...     power_supply_alert=False,
        ...     autoprotection_mechanical_alert=True,
        ...     loop_alert=False,
        ...     mask_alert=True,
        ...     sensor_alert=False,
        ...     media_gsm_alert=True,
        ...     media_rtc_alert=False,
        ...     media_adsl_alert=True,
        ...     out_of_order_alert=False,
        ...     main_power_supply_alert=True,
        ...     secondary_power_supply_alert=False,
        ...     default_media_alert=True,
        ...     autoprotection_wired_alert=False
        ... )
        >>> print(anomalies.radio_alert)
        True
        >>> print(anomalies.power_supply_alert)
        False

    """

    radio_alert: bool | None = field(default=None, metadata={"alias": "radioAlert"})
    power_supply_alert: bool | None = field(
        default=None, metadata={"alias": "powerSupplyAlert"}
    )
    autoprotection_mechanical_alert: bool | None = field(
        default=None, metadata={"alias": "autoprotectionMechanicalAlert"}
    )
    loop_alert: bool | None = field(default=None, metadata={"alias": "loopAlert"})
    mask_alert: bool | None = field(default=None, metadata={"alias": "maskAlert"})
    sensor_alert: bool | None = field(default=None, metadata={"alias": "sensorAlert"})
    media_gsm_alert: bool | None = field(
        default=None, metadata={"alias": "mediaGSMAlert"}
    )
    media_rtc_alert: bool | None = field(
        default=None, metadata={"alias": "mediaRTCAlert"}
    )
    media_adsl_alert: bool | None = field(
        default=None, metadata={"alias": "mediaADSLAlert"}
    )
    out_of_order_alert: bool | None = field(
        default=None, metadata={"alias": "outOfOrderAlert"}
    )
    main_power_supply_alert: bool | None = field(
        default=None, metadata={"alias": "mainPowerSupplyAlert"}
    )
    secondary_power_supply_alert: bool | None = field(
        default=None, metadata={"alias": "secondaryPowerSupplyAlert"}
    )
    default_media_alert: bool | None = field(
        default=None, metadata={"alias": "defaultMediaAlert"}
    )
    autoprotection_wired_alert: bool | None = field(
        default=None, metadata={"alias": "autoprotectionWiredAlert"}
    )


@dataclass
class SensorModel(CamelCaseModel):
    """SensorModel represents the data structure for a sensor.

    Attributes:
        uid (str | None): Unique identifier for the sensor.
        type (int | None): Type of the sensor.
        gamme (int | None): Range or category of the sensor.
        group (int | None): Group to which the sensor belongs.
        index (int | None): Index of the sensor.
        label (str | None): Label or name of the sensor.
        serial (str | None): Serial number of the sensor.
        is_video (bool | None): Indicates if the sensor is a video sensor (alias: isVideo).
        ref_code (str | None): Reference code of the sensor (alias: refCode).
        subtype (int | None): Subtype of the sensor.
        anomalies (ConfAnomaliesModel | None): Configuration anomalies associated with the sensor.
        inhibited (bool | None): Indicates if the sensor is inhibited.
        can_inhibit (bool | None): Indicates if the sensor can be inhibited (alias: canInhibit).

    Example:
        >>> anomalies = ConfAnomaliesModel(radio_alert=True)
        >>> sensor = SensorModel(
        ...     uid="12345",
        ...     type=1,
        ...     gamme=2,
        ...     group=3,
        ...     index=4,
        ...     label="Sensor 1",
        ...     serial="SN12345",
        ...     is_video=True,
        ...     ref_code="RC123",
        ...     subtype=5,
        ...     anomalies=anomalies,
        ...     inhibited=False,
        ...     can_inhibit=True
        ... )
        >>> print(sensor.uid)
        12345

    """

    uid: str | None = None
    type: int | None = None
    gamme: int | None = None
    group: int | None = None
    index: int | None = None
    label: str | None = None
    serial: str | None = None
    is_video: bool | None = field(default=None, metadata={"alias": "isVideo"})
    ref_code: str | None = field(default=None, metadata={"alias": "refCode"})
    subtype: int | None = None
    anomalies: ConfAnomaliesModel | None = None
    inhibited: bool | None = None
    can_inhibit: bool | None = field(default=None, metadata={"alias": "canInhibit"})


@dataclass
class Cameras(SensorModel):
    """Cameras model representing a sensor with an installation date, inheriting from SensorModel.

    Attributes:
        installation_date (datetime | None): The date when the camera was installed.
            Defaults to None. This attribute is aliased as 'installationDate' in metadata.

    Example:
        >>> camera = Cameras(
        ...     uid="12345",
        ...     type=1,
        ...     gamme=2,
        ...     group=3,
        ...     index=4,
        ...     label="Camera 1",
        ...     serial="SN12345",
        ...     is_video=True,
        ...     ref_code="RC123",
        ...     subtype=5,
        ...     anomalies=None,
        ...     inhibited=False,
        ...     can_inhibit=True,
        ...     installation_date=datetime(2023, 10, 1)
        ... )
        >>> print(camera.installation_date)
        2023-10-01 00:00:00

    """

    installation_date: datetime | None = field(
        default=None, metadata={"alias": "installationDate"}
    )


@dataclass
class TransceiverModel(SensorModel):
    """TransceiverModel represents a model for a transceiver device, inheriting from SensorModel.

    Attributes:
        firmwares (FirmwareModel | None): An optional attribute that holds the firmware information associated with the transceiver.

    Example:
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> transceiver = TransceiverModel(
        ...     uid="12345",
        ...     type=1,
        ...     gamme=2,
        ...     group=3,
        ...     index=4,
        ...     label="Transceiver 1",
        ...     serial="SN12345",
        ...     is_video=True,
        ...     ref_code="RC123",
        ...     subtype=5,
        ...     anomalies=None,
        ...     inhibited=False,
        ...     can_inhibit=True,
        ...     firmwares=firmware
        ... )
        >>> print(transceiver.uid)
        12345

    """

    firmwares: FirmwareModel | None = None


@dataclass
class TransmitterModel(SensorModel):
    """TransmitterModel represents a model for a transmitter device, inheriting from SensorModel.

    Attributes:
        firmwares (FirmwareModel | None): The firmware associated with the transmitter, if any.
        is_plug (bool | None): Indicates whether the transmitter is a plug, with metadata alias "isPlug".

    Example:
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> transmitter = TransmitterModel(
        ...     uid="12345",
        ...     type=1,
        ...     gamme=2,
        ...     group=3,
        ...     index=4,
        ...     label="Transmitter 1",
        ...     serial="SN12345",
        ...     is_video=True,
        ...     ref_code="RC123",
        ...     subtype=5,
        ...     anomalies=None,
        ...     inhibited=False,
        ...     can_inhibit=True,
        ...     firmwares=firmware,
        ...     is_plug=True
        ... )
        >>> print(transmitter.uid)
        12345

    """

    firmwares: FirmwareModel | None = None
    is_plug: bool | None = field(default=None, metadata={"alias": "isPlug"})


@dataclass
class CentralInformation(CamelCaseModel):
    """CentralInformation model represents the central unit's configuration and status information.

    Attributes:
        has_plug (bool | None): Indicates if the central unit has a plug. Alias: "hasPlug".
        plug_gsm (bool | None): Indicates if the central unit has a GSM plug. Alias: "plugGSM".
        plug_rtc (bool | None): Indicates if the central unit has an RTC plug. Alias: "plugRTC".
        plug_adsl (bool | None): Indicates if the central unit has an ADSL plug. Alias: "plugADSL".
        anomalies (ConfAnomaliesModel | None): Represents the configuration anomalies of the central unit.
        firmwares (FirmwareModel | None): Represents the firmware information of the central unit.
        relay_card (bool | None): Indicates if the central unit has a relay card. Alias: "relayCard".
        can_inhibit (bool | None): Indicates if the central unit can be inhibited. Alias: "canInhibit".
        parameter_gsm_saved (bool | None): Indicates if the GSM parameters are saved. Alias: "parameterGsmSaved".

    Example:
        >>> anomalies = ConfAnomaliesModel(radio_alert=True)
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> central_info = CentralInformation(
        ...     has_plug=True,
        ...     plug_gsm=True,
        ...     plug_rtc=False,
        ...     plug_adsl=True,
        ...     anomalies=anomalies,
        ...     firmwares=firmware,
        ...     relay_card=True,
        ...     can_inhibit=True,
        ...     parameter_gsm_saved=False
        ... )
        >>> print(central_info.has_plug)
        True

    """

    has_plug: bool | None = field(default=None, metadata={"alias": "hasPlug"})
    plug_gsm: bool | None = field(default=None, metadata={"alias": "plugGSM"})
    plug_rtc: bool | None = field(default=None, metadata={"alias": "plugRTC"})
    plug_adsl: bool | None = field(default=None, metadata={"alias": "plugADSL"})
    anomalies: ConfAnomaliesModel | None = None
    firmwares: FirmwareModel | None = None
    relay_card: bool | None = field(default=None, metadata={"alias": "relayCard"})
    can_inhibit: bool | None = field(default=None, metadata={"alias": "canInhibit"})
    parameter_gsm_saved: bool | None = field(
        default=None, metadata={"alias": "parameterGsmSaved"}
    )


@dataclass
class BoxModel(CamelCaseModel):
    """BoxModel represents a model for a box with various attributes.

    Attributes:
        name (str | None): The name of the box. Defaults to None.
        serial (str | None): The serial number of the box. Defaults to None.
        vendor (str | None): The vendor of the box. Defaults to None.
        firmwares (FirmwareModel | None): The firmware model associated with the box. Defaults to None.

    Example:
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> box = BoxModel(name="Box 1", serial="123456789", vendor="VendorName", firmwares=firmware)
        >>> print(box.name)
        Box 1

    """

    name: str | None = None
    serial: str | None = None
    vendor: str | None = None
    firmwares: FirmwareModel | None = None


@dataclass
class AlarmModel(CamelCaseModel):
    """AlarmModel represents the configuration and state of an alarm system.

    Attributes:
        box (BoxModel | None): The box model associated with the alarm system.
        plug (CentralPlugModel | None): The central plug model for the alarm system.
        tls (bool | None): Indicates if TLS (Transport Layer Security) is enabled.
        name (str | None): The name of the alarm system.
        central (CentralPlugModel | None): The central plug model for the alarm system.
        force_push_config (bool | None): Indicates if the configuration should be forcefully pushed.
                                         This attribute is aliased as "forcePushConfig".

    Example:
        >>> box = BoxModel(name="Box 1", serial="123456789", vendor="VendorName")
        >>> plug = CentralPlugModel(name="Central Plug 1", serial="987654321", vendor="VendorName")
        >>> alarm = AlarmModel(box=box, plug=plug, tls=True, name="Home Alarm", central=plug, force_push_config=True)
        >>> print(alarm.name)
        Home Alarm

    """

    box: BoxModel | None = None
    plug: CentralPlugModel | None = None
    tls: bool | None = None
    name: str | None = None
    central: CentralPlugModel | None = None
    force_push_config: bool | None = field(
        default=None, metadata={"alias": "forcePushConfig"}
    )


@dataclass
class AlarmConfiguration(CamelCaseModel):
    """AlarmConfiguration model represents the configuration of an alarm system.

    Attributes:
        alarm (AlarmModel | None): The alarm model associated with the configuration.
        groups (list[Group] | None): A list of groups associated with the alarm configuration.
        sirens (list[SensorModel] | None): A list of siren sensor models.
        cameras (list[Cameras] | None): A list of camera models.
        sensors (list[SensorModel] | None): A list of sensor models.
        commands (list[SensorModel] | None): A list of command sensor models.
        reading_date (datetime | None): The date when the configuration was read, aliased as "readingDate".
        transceivers (list[TransceiverModel] | None): A list of transceiver models.
        transmitters (list[TransmitterModel] | None): A list of transmitter models.
        grp_marche_presence (list[int] | None): A list of group marche presence, aliased as "grpMarchePresence".
        installation_state (int | None): The state of the installation, aliased as "installationState".
        central_information (CentralInformation | None): Information about the central unit, aliased as "centralInformation".
        grp_marche_partielle1 (list[int] | None): A list of group marche partielle 1, aliased as "grpMarchePartielle1".
        grp_marche_partielle2 (list[int] | None): A list of group marche partielle 2, aliased as "grpMarchePartielle2".

    Example:
        >>> alarm_config = AlarmConfiguration(
        ...     alarm=AlarmModel(name="Home Alarm"),
        ...     groups=[Group(name="Group A", index=1)],
        ...     sirens=[SensorModel(uid="12345", type=1)],
        ...     cameras=[Cameras(uid="67890", type=2)],
        ...     sensors=[SensorModel(uid="54321", type=3)],
        ...     commands=[SensorModel(uid="98765", type=4)],
        ...     reading_date=datetime(2023, 10, 1),
        ...     transceivers=[TransceiverModel(uid="11223", type=5)],
        ...     transmitters=[TransmitterModel(uid="44556", type=6)],
        ...     grp_marche_presence=[1, 2, 3],
        ...     installation_state=1,
        ...     central_information=CentralInformation(has_plug=True),
        ...     grp_marche_partielle1=[4, 5, 6],
        ...     grp_marche_partielle2=[7, 8, 9]
        ... )
        >>> print(alarm_config.alarm.name)
        Home Alarm

    """

    alarm: AlarmModel | None = None
    # badges: list[] # Not yet implemented. No enough information in documentation
    groups: list[Group] | None = None
    sirens: list[SensorModel] | None = None
    cameras: list[Cameras] | None = None
    sensors: list[SensorModel] | None = None
    commands: list[SensorModel] | None = None
    reading_date: datetime | None = field(
        default=None, metadata={"alias": "readingDate"}
    )
    transceivers: list[TransceiverModel] | None = None
    transmitters: list[TransmitterModel] | None = None
    grp_marche_presence: list[int] | None = field(
        default=None, metadata={"alias": "grpMarchePresence"}
    )
    installation_state: int | None = field(
        default=None, metadata={"alias": "installationState"}
    )
    central_information: CentralInformation | None = field(
        default=None, metadata={"alias": "centralInformation"}
    )
    grp_marche_partielle1: list[int] | None = field(
        default=None, metadata={"alias": "grpMarchePartielle1"}
    )
    grp_marche_partielle2: list[int] | None = field(
        default=None, metadata={"alias": "grpMarchePartielle2"}
    )


############################
# Data model for device list
############################


@dataclass
class DeviceInfos(CamelCaseModel):
    """DeviceInfos model represents the information of a device.

    Attributes:
        index (int): The index of the device.
        label (str): The label or name of the device.

    Example:
        >>> device_info = DeviceInfos(index=1, label="Sensor 1")
        >>> print(device_info.index)
        1
        >>> print(device_info.label)
        Sensor 1

    """

    index: int
    label: str


@dataclass
class DeviceList(CamelCaseModel):
    """DeviceList model representing a collection of various device types.

    Attributes:
        cameras (list[DeviceInfos] | None): A list of camera devices or None if not available.
        commands (list[DeviceInfos] | None): A list of command devices or None if not available.
        sensors (list[DeviceInfos] | None): A list of sensor devices or None if not available.
        sirens (list[DeviceInfos] | None): A list of siren devices or None if not available.
        transmitters (list[DeviceInfos] | None): A list of transmitter devices or None if not available.

    Example:
        >>> device_list = DeviceList(
        ...     cameras=[DeviceInfos(index=1, label="Camera 1")],
        ...     commands=[DeviceInfos(index=2, label="Command 1")],
        ...     sensors=[DeviceInfos(index=3, label="Sensor 1")],
        ...     sirens=[DeviceInfos(index=4, label="Siren 1")],
        ...     transmitters=[DeviceInfos(index=5, label="Transmitter 1")]
        ... )
        >>> print(device_list.cameras[0].label)
        Camera 1

    """

    cameras: list[DeviceInfos] | None = None
    commands: list[DeviceInfos] | None = None
    sensors: list[DeviceInfos] | None = None
    sirens: list[DeviceInfos] | None = None
    transmitters: list[DeviceInfos] | None = None


###############################
# Data model for system details
###############################


@dataclass
class SystemDetails(CamelCaseModel):
    """SystemDetails model represents the details of a system with various attributes.

    Attributes:
        device_type (str): The type of the device.
        firmware_version (str): The firmware version of the device.
        ip_address (str): The IP address of the device.
        ipoda_version (str): The version of the IPODA.
        mode (str): The mode of the device.
        first_vocal_contact (str): The first vocal contact information.
        is_alarm_file_present (bool): Indicates if the alarm file is present.
        is_mjpeg_archive_video_supported (str): Indicates if MJPEG archive video is supported.
        is_mass_storage_present (str): Indicates if mass storage is present.
        is_remote_startup_shutdown_allowed (str): Indicates if remote startup/shutdown is allowed.
        is_video_password_protected (str): Indicates if the video is password protected.

    Example:
        >>> system_details = SystemDetails(
        ...     device_type="Camera",
        ...     firmware_version="1.0.0",
        ...     ip_address="192.168.1.1",
        ...     ipoda_version="2.0.0",
        ...     mode="Active",
        ...     first_vocal_contact="2023-10-01T12:00:00Z",
        ...     is_alarm_file_present=True,
        ...     is_mjpeg_archive_video_supported="Yes",
        ...     is_mass_storage_present="Yes",
        ...     is_remote_startup_shutdown_allowed="No",
        ...     is_video_password_protected="Yes"
        ... )
        >>> print(system_details.device_type)
        Camera

    """

    device_type: str = field(metadata={"alias": "DeviceType"})
    firmware_version: str = field(metadata={"alias": "FirmwareVersion"})
    ip_address: str = field(metadata={"alias": "IpAddress"})
    ipoda_version: str = field(metadata={"alias": "IpodaVersion"})
    mode: str = field(metadata={"alias": "Mode"})
    first_vocal_contact: str = field(metadata={"alias": "FirstVocalContact"})
    is_alarm_file_present: bool = field(metadata={"alias": "IsAlarmFilePresent"})
    is_mjpeg_archive_video_supported: str = field(
        metadata={"alias": "IsMJPEGArchiveVideoSupported"}
    )
    is_mass_storage_present: str = field(metadata={"alias": "IsMassStoragePresent"})
    is_remote_startup_shutdown_allowed: str = field(
        metadata={"alias": "IsRemoteStartupShutdownAllowed"}
    )
    is_video_password_protected: str = field(
        metadata={"alias": "IsVideoPasswordProtected"}
    )


##############################
# Data model for system status
##############################


@dataclass
class SystemStatus(CamelCaseModel):
    """SystemStatus represents the status of a system with various attributes.

    Attributes:
        status (str): The current status of the system.
        activated_groups (list[int]): A list of IDs representing the activated groups within the system.

    Example:
        >>> system_status = SystemStatus(status="Active", activated_groups=[1, 2, 3])
        >>> print(system_status.status)
        Active
        >>> print(system_status.activated_groups)
        [1, 2, 3]

    """

    status: str
    activated_groups: list[int]


#######################################
# Data model for anomalies informations
#######################################


@dataclass
class AnomalyName(CamelCaseModel):
    """AnomalyName model representing an anomaly with an identifier and a name.

    Attributes:
        id (int): The unique identifier for the anomaly.
        name (str): The name of the anomaly.

    Example:
        >>> anomaly = AnomalyName(id=1, name="Low Battery")
        >>> print(anomaly.id)
        1
        >>> print(anomaly.name)
        Low Battery

    """

    id: int
    name: str


@dataclass
class AnomalyDetail(CamelCaseModel):
    """AnomalyDetail represents detailed information about an anomaly.

    Attributes:
        anomaly_names (list[AnomalyName]): A list of anomaly names associated with this detail.
        serial (str | None): An optional serial number associated with the anomaly.
        index (int | None): An optional index value for the anomaly.
        group (int | None): An optional group identifier for the anomaly.
        label (str | None): An optional label describing the anomaly.

    Example:
        >>> anomaly_names = [AnomalyName(id=1, name="Low Battery")]
        >>> anomaly_detail = AnomalyDetail(
        ...     anomaly_names=anomaly_names,
        ...     serial="SN12345",
        ...     index=1,
        ...     group=2,
        ...     label="Sensor Anomaly"
        ... )
        >>> print(anomaly_detail.serial)
        SN12345

    """

    anomaly_names: list[AnomalyName]
    serial: str | None = None
    index: int | None = None
    group: int | None = None
    label: str | None = None


@dataclass
class Anomalies(CamelCaseModel):
    """A model representing anomalies detected in various devices.

    Attributes:
        created_at (datetime): The timestamp when the anomalies were created.
        sensors (list[AnomalyDetail] | None): A list of anomaly details for sensors, or None if no anomalies.
        badges (list[AnomalyDetail] | None): A list of anomaly details for badges, or None if no anomalies.
        sirens (list[AnomalyDetail] | None): A list of anomaly details for sirens, or None if no anomalies.
        cameras (list[AnomalyDetail] | None): A list of anomaly details for cameras, or None if no anomalies.
        commands (list[AnomalyDetail] | None): A list of anomaly details for commands, or None if no anomalies.
        transceivers (list[AnomalyDetail] | None): A list of anomaly details for transceivers, or None if no anomalies.
        transmitters (list[AnomalyDetail] | None): A list of anomaly details for transmitters, or None if no anomalies.
        central (list[AnomalyDetail] | None): A list of anomaly details for central devices, or None if no anomalies.

    Methods:
        from_dict(data: dict) -> Anomalies:
            Create an instance of Anomalies from a dictionary.

    Example:
        >>> data = {
        ...     "created_at": "2025-02-16T10:15:12.625165",
        ...     "sensors": [
        ...         {
        ...             "serial": "SN12345",
        ...             "index": 1,
        ...             "group": 2,
        ...             "label": "Sensor Anomaly",
        ...             "anomaly_names": [{"id": 1, "name": "Low Battery"}]
        ...         }
        ...     ]
        ... }
        >>> anomalies = Anomalies.from_dict(data)
        >>> print(anomalies.created_at)
        2025-02-16 10:15:12.625165+00:00
        >>> print(anomalies.sensors[0].serial)
        SN12345

    """

    created_at: datetime
    sensors: list[AnomalyDetail] | None = None
    badges: list[AnomalyDetail] | None = None
    sirens: list[AnomalyDetail] | None = None
    cameras: list[AnomalyDetail] | None = None
    commands: list[AnomalyDetail] | None = None
    transceivers: list[AnomalyDetail] | None = None
    transmitters: list[AnomalyDetail] | None = None
    central: list[AnomalyDetail] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Anomalies:
        """Create an instance of Anomalies from a dictionary."""

        def create_devices(device_data):
            return [
                AnomalyDetail(
                    serial=data.get("serial"),
                    index=data.get("index"),
                    group=data.get("group"),
                    label=data.get("label"),
                    anomaly_names=[AnomalyName(**a) for a in data.get("anomaly_names")],
                )
                for data in device_data
            ]

        # Convert the created_at field to a datetime object with UTC timezone
        created_at = datetime.fromisoformat(data["created_at"]).replace(
            tzinfo=timezone.utc
        )

        return cls(
            created_at=created_at,
            sensors=create_devices(data.get("sensors", [])),
            badges=create_devices(data.get("badges", [])),
            sirens=create_devices(data.get("sirens", [])),
            cameras=create_devices(data.get("cameras", [])),
            commands=create_devices(data.get("commands", [])),
            transceivers=create_devices(data.get("transceivers", [])),
            transmitters=create_devices(data.get("transmitters", [])),
            central=create_devices(data.get("central", [])),
        )


############################
# Data Model for webhooks
############################


@dataclass
class WebhookSubscription(CamelCaseModel):
    """Represents a subscription to webhook notifications.

    Attributes:
        anomaly (bool): Indicates whether anomaly notifications are enabled.
        alert (bool): Indicates whether alert notifications are enabled.
        state (bool): Indicates whether state notifications are enabled.

    Example:
        >>> subscription = WebhookSubscription(anomaly=True, alert=False, state=True)
        >>> print(subscription.anomaly)
        True

    """

    anomaly: bool
    alert: bool
    state: bool


@dataclass
class Webhook(CamelCaseModel):
    """Represents a Webhook model.

    Attributes:
        transmitter_id (str): The unique identifier for the transmitter.
        webhook_url (str): The URL to which the webhook will send data.
        subscriptions (WebhookSubscription): The subscription details for the webhook.

    Example:
        >>> subscription = WebhookSubscription(anomaly=True, alert=False, state=True)
        >>> webhook = Webhook(transmitter_id="12345", webhook_url="https://example.com/webhook", subscriptions=subscription)
        >>> print(webhook.transmitter_id)
        12345

    """

    transmitter_id: str
    webhook_url: str
    subscriptions: WebhookSubscription


@dataclass
class WebHookNotificationDetail(CamelCaseModel):
    """WebHookNotificationDetail model represents the details of a webhook notification.

    Attributes:
        device_type (str): The type of the device.
        device_index (str): The index of the device.
        device_label (str | None): The label of the device, which is optional.

    Example:
        >>> detail = WebHookNotificationDetail(device_type="Sensor", device_index="1", device_label="Front Door Sensor")
        >>> print(detail.device_type)
        Sensor
        >>> print(detail.device_index)
        1
        >>> print(detail.device_label)
        Front Door Sensor

    """

    device_type: str
    device_index: str
    device_label: str | None = None


@dataclass
class WebHookNotificationUser(CamelCaseModel):
    """WebHookNotificationUser represents a user who receives webhook notifications.

    Attributes:
        username (str): The username of the user.
        user_type (str): The type of the user.

    Example:
        >>> user = WebHookNotificationUser(username="Dark Vador", user_type="owner")
        >>> print(user.username)
        Dark Vador
        >>> print(detail.user_type)
        owner

    """

    username: str
    user_type: str


@dataclass
class WebHookNotification(CamelCaseModel):
    """A model representing a webhook notification.

    Attributes:
        transmitter_id (str): The ID of the transmitter sending the notification.
        alarm_type (str): The type of alarm, determined based on the alarm code.
        alarm_code (str): The code representing the specific alarm.
        alarm_description (str): A description of the alarm.
        group_index (str): The index of the group associated with the alarm.
        detail (WebHookNotificationDetail): Detailed information about the webhook notification.
            Only during anomaly/alert notification.
        user (WebHookNotificationUser): The user who trigger the notification.
            Only during change state notification.
        date_time (datetime): The date and time when the notification was generated.

    Methods:
        from_dict(data: dict) -> WebHookNotification:
            Create an instance of WebHookNotification from a dictionary.

    Example:
        >>> data = {
        ...     "transmitter_id": "12345",
        ...     "alarm_code": "1130",
        ...     "alarm_description": "Intrusion detected",
        ...     "group_index": "01",
        ...     "detail": {
        ...         "device_type": "Sensor",
        ...         "device_index": "1",
        ...         "device_label": "Front Door Sensor"
        ...     },
        ...     "date_time": "2023-10-01T12:00:00Z"
        ... }
        >>> notification = WebHookNotification.from_dict(data)
        >>> print(notification.transmitter_id)
        12345

    """

    transmitter_id: str
    alarm_type: str  # Not included in Diagral answer. Added with below function
    alarm_code: str
    alarm_description: str
    group_index: str
    detail: WebHookNotificationDetail
    user: WebHookNotificationUser
    date_time: datetime

    @classmethod
    def from_dict(cls, data: dict) -> WebHookNotification:
        """Create an instance of WebHookNotification from a dictionary."""

        def alarm_type(alarm_code):
            """Determine the type of alarm based on the alarm code."""
            ANOMALY_CODES = [
                1301,
                3301,
                1137,
                3137,
                1355,
                3355,
                1381,
                3381,
                1144,
                3144,
                1302,
                1384,
                1570,
                3570,
                1352,
                3352,
                1351,
                3351,
                1573,
            ]
            ALERT_CODES = [
                1130,
                1110,
                1111,
                1117,
                1158,
                1139,
                1344,
                1120,
                1122,
                1159,
                1152,
                1154,
                1150,
                1140,
                1141,
                1142,
                1143,
                3391,
                1391,
            ]
            STATUS_CODES = [1306, 3401, 3407, 1401, 1407]

            if int(alarm_code) in ANOMALY_CODES:
                return "ANOMALY"
            if int(alarm_code) in ALERT_CODES:
                return "ALERT"
            if int(alarm_code) in STATUS_CODES:
                return "STATUS"
            return "UNKNOWN"

        return cls(
            transmitter_id=data.get("transmitter_id"),
            alarm_type=alarm_type(data.get("alarm_code")),
            alarm_code=data.get("alarm_code"),
            alarm_description=data.get("alarm_description"),
            group_index=data.get("group_index"),
            detail=WebHookNotificationDetail(
                device_type=data.get("detail", {}).get("device_type", None),
                device_index=data.get("detail", {}).get("device_index", None),
                device_label=data.get("detail", {}).get("device_label", None),
            ),
            user=WebHookNotificationUser(
                username=data.get("user", {}).get("username", None),
                user_type=data.get("user", {}).get("user_type", None),
            ),
            date_time=datetime.fromisoformat(data["date_time"].replace("Z", "+00:00")),
        )


############################
# Data Model for automations
############################


@dataclass
class Rude(CamelCaseModel):
    """Rude model representing a device with a name, canal, and mode.

    Attributes:
        name (str): The name of the device.
        canal (str): The canal associated with the device.
        mode (str): The mode of operation for the device. Must be one of {"ON", "PULSE", "SWITCH", "TIMER"}.

    Methods:
        __post_init__(): Post-initialization processing to validate the mode attribute.

    Example:
        >>> rude = Rude(name="Device1", canal="Canal1", mode="ON")
        >>> print(rude.name)
        Device1

    """

    name: str
    canal: str
    mode: str

    def __post_init__(self):
        """Post-initialization processing to validate mode."""
        valid_modes = {"ON", "PULSE", "SWITCH", "TIMER"}
        if self.mode not in valid_modes:
            raise ValueError(f"mode must be one of {valid_modes}")


@dataclass
class Rudes(CamelCaseModel):
    """Rudes model representing a collection of Rude instances.

    Attributes:
        rudes (list[Rude]): A list of Rude objects.

    Example:
        >>> rude1 = Rude(name="Device1", canal="Canal1", mode="ON")
        >>> rude2 = Rude(name="Device2", canal="Canal2", mode="PULSE")
        >>> rudes = Rudes(rudes=[rude1, rude2])
        >>> print(rudes.rudes[0].name)
        Device1

    """

    rudes: list[Rude]


###########################
# Data Model for exceptions
###########################


@dataclass
class ValidationError(CamelCaseModel):
    """ValidationError model represents an error that occurs during validation.

    Attributes:
        loc (list[str] | None): The location of the error, typically indicating the field or attribute that caused the error.
        message (str | None): A human-readable message describing the error.
        type (str | None): The type or category of the error.
        input (str | None): The input value that caused the error.
        url (str | None): A URL providing more information about the error.

    Example:
        >>> error = ValidationError(
        ...     loc=["body", "username"],
        ...     message="Username is required",
        ...     type="value_error.missing",
        ...     input=None,
        ...     url="https://example.com/errors/username-required"
        ... )
        >>> print(error.message)
        Username is required

    """

    loc: list[str] | None = None
    message: str | None = None
    type: str | None = None
    input: str | None = None
    url: str | None = None


@dataclass
class HTTPValidationError(ValidationError):
    """HTTPValidationError is a subclass of ValidationError that represents an HTTP validation error.

    Attributes:
        detail (list[ValidationError] | None): A list of ValidationError instances or None, providing detailed information about the validation errors.

    Example:
        >>> error_detail = ValidationError(
        ...     loc=["body", "username"],
        ...     message="Username is required",
        ...     type="value_error.missing",
        ...     input=None,
        ...     url="https://example.com/errors/username-required"
        ... )
        >>> http_error = HTTPValidationError(detail=[error_detail])
        >>> print(http_error.detail[0].message)
        Username is required

    """

    detail: list[ValidationError] | None = None


@dataclass
class HTTPErrorResponse(CamelCaseModel):
    """HTTPErrorResponse is a model that represents an HTTP error response.

    Attributes:
        detail (str): A detailed message describing the error.

    Example:
        >>> error_response = HTTPErrorResponse(detail="Not Found")
        >>> print(error_response.detail)
        Not Found

    """

    detail: str
