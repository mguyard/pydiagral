"""Module containing data models for interacting with the Diagral API.

The models include representations for login responses, API key creation and validation,
and other related data structures.
"""

# Minimum Python version: 3.11

from __future__ import annotations

from dataclasses import MISSING, Field, dataclass, field, fields
from datetime import UTC, datetime
import logging
import types
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    NamedTuple,
    Self,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .constants import ISSUES_URL
from .exceptions import ModelValidationError
from .utils import Redacted

logger: logging.Logger = logging.getLogger(__name__)


#######################################################
# Class for converting between camelCase and snake_case
#######################################################


_ModelT = TypeVar("_ModelT", bound="CamelCaseModel")

# What a payload of the wrong shape makes the parsers raise.
_PARSE_ERRORS = (AttributeError, KeyError, TypeError, ValueError)

# Model fields a payload broke expectations on, so each is reported only once.
_REPORTED_FIELDS: set[tuple[str, str]] = set()


class _FieldSpec(NamedTuple):
    """How `_from_dict_recursive` reads one model field."""

    name: str
    alias: str
    type: Any
    required: bool


# Resolved once per model: evaluating annotations dominated parsing time.
_FIELD_SPECS: dict[type, tuple[_FieldSpec, ...]] = {}


def _field_specs(model: type) -> tuple[_FieldSpec, ...]:
    """Return how to read each field of a model, resolving it on first use."""
    if model in _FIELD_SPECS:
        return _FIELD_SPECS[model]
    model_fields = {model_field.name: model_field for model_field in fields(model)}
    specs = []
    for name, hint in get_type_hints(model).items():
        model_field = model_fields.get(name)
        if model_field is None:
            continue
        args = get_args(hint)
        optional = get_origin(hint) in (Union, types.UnionType) and type(None) in args
        if optional:
            hint = next(t for t in args if t is not type(None))
        has_default = (
            model_field.default is not MISSING
            or model_field.default_factory is not MISSING
        )
        specs.append(
            _FieldSpec(
                name=name,
                alias=model_field.metadata.get("alias", name).lower(),
                type=hint,
                required=not (optional or has_default),
            )
        )
    _FIELD_SPECS[model] = tuple(specs)
    return _FIELD_SPECS[model]


def _report_unexpected_field(model: type, name: str, problem: str) -> None:
    """Warn once that a payload does not fit a model, without quoting the payload."""
    if (model.__name__, name) in _REPORTED_FIELDS:
        return
    _REPORTED_FIELDS.add((model.__name__, name))
    logger.warning(
        "Diagral sent %s data whose %s field %s. Please report it at %s, with your "
        "pydiagral version, so the model can be fixed",
        model.__name__,
        name,
        problem,
        ISSUES_URL,
    )


def _parse_datetime(model: type, name: str, value: str) -> datetime | None:
    """Parse an ISO date; an unknown format is reported and read as None."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        _report_unexpected_field(model, name, "is not an ISO date")
        return None


# Some endpoints send booleans as "True" / "False" strings.
_BOOLEAN_STRINGS = {"true": True, "false": False}


def _parse_boolean(model: type, name: str, value: str) -> bool | None:
    """Parse a boolean string; any other string is reported and read as None."""
    parsed = _BOOLEAN_STRINGS.get(value.lower())
    if parsed is None:
        _report_unexpected_field(model, name, "is not a boolean")
    return parsed


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

    Examples:
        >>> @dataclass
        ... class ExampleModel(CamelCaseModel):
        ...     first_name: str
        ...     last_name: str
        ...
        >>> example = ExampleModel(first_name="Luke", last_name="Skywalker")
        >>> example.to_dict()
        {'firstName': 'Luke', 'lastName': 'Skywalker'}
        >>> ExampleModel.from_dict({"first_name": "Luke", "last_name": "Skywalker"})
        ExampleModel(first_name='Luke', last_name='Skywalker')

    """

    if TYPE_CHECKING:
        # Every subclass is a dataclass; this lets `fields()` accept the base type.
        __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

    def to_dict(self) -> dict:
        """Convert the instance to a dictionary with camelCase keys.

        A field's `alias` is used as its key when it has one. Nested models, including
        those in lists, are converted too, and None values are left out.

        Returns:
            dict: A dictionary representation of the instance with camelCase keys.

        Examples:
            >>> @dataclass
            ... class ExampleModel(CamelCaseModel):
            ...     first_name: str
            ...     last_name: str
            ...
            >>> ExampleModel(first_name="Luke", last_name="Skywalker").to_dict()
            {'firstName': 'Luke', 'lastName': 'Skywalker'}

        """

        result = {}
        for model_field in fields(self):
            value = getattr(self, model_field.name)
            if value is None:
                continue
            if isinstance(value, CamelCaseModel):
                value = value.to_dict()
            elif isinstance(value, list):
                value = [
                    item.to_dict() if isinstance(item, CamelCaseModel) else item
                    for item in value
                ]
            key = model_field.metadata.get(
                "alias", self.snake_to_camel(model_field.name)
            )
            result[key] = value
        return result

    @classmethod
    def _from_dict_recursive(cls, data: dict, target_cls: type[_ModelT]) -> _ModelT:
        """Recursively converts a dictionary to an instance of the specified target class.

        Each field is matched, case-insensitively, against its `alias` or its name; keys
        are not converted from camelCase. Nested dictionaries and lists of dictionaries
        become the annotated models, ISO strings become `datetime` objects, and "True" /
        "False" strings in any case become booleans. A missing field is set to None.

        Args:
            cls (type[Self]): The class that this method is a part of.
            data (dict): The dictionary to convert.
            target_cls (type[_ModelT]): The target class to convert the dictionary to.

        Returns:
            An instance of the target class populated with the data from the dictionary.

        Raises:
            TypeError: If the target class cannot be instantiated with the provided data.

        """

        if get_origin(target_cls) is Union:
            target_cls = next(t for t in get_args(target_cls) if t is not type(None))

        keys: dict[str, str] = {}
        for key in data:
            keys.setdefault(key.lower(), key)

        init_values: dict[str, Any] = {}
        for spec in _field_specs(target_cls):
            key = keys.get(spec.alias)
            value = data[key] if key is not None else None
            if value is None:
                if spec.required:
                    _report_unexpected_field(target_cls, spec.name, "is missing")
                init_values[spec.name] = None
            elif (
                isinstance(value, dict)
                and isinstance(spec.type, type)
                and issubclass(spec.type, CamelCaseModel)
            ):
                init_values[spec.name] = cls._from_dict_recursive(value, spec.type)
            elif isinstance(value, list) and get_origin(spec.type) is list:
                item_type = get_args(spec.type)[0]
                init_values[spec.name] = [
                    cls._from_dict_recursive(item, item_type)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            elif spec.type is datetime and isinstance(value, str):
                init_values[spec.name] = _parse_datetime(target_cls, spec.name, value)
            elif spec.type is bool and isinstance(value, str):
                init_values[spec.name] = _parse_boolean(target_cls, spec.name, value)
            else:
                init_values[spec.name] = value

        return target_cls(**init_values)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create an instance of the class from a dictionary.

        Args:
            cls (type[Self]): The class type to instantiate.
            data (dict): The dictionary containing the data to populate the instance.

        Returns:
            An instance of the class populated with the data from the dictionary.

        Raises:
            ModelValidationError: If the data is not an object or does not fit the model.

        Examples:
            >>> login_response = LoginResponse.from_dict({"access_token": "abc123"})
            >>> login_response.access_token
            'abc123'

        """

        if not isinstance(data, dict):
            raise ModelValidationError(f"Invalid {cls.__name__} payload")
        logger.debug("Parsing %s from %s", cls.__name__, Redacted(data))
        try:
            return cls._from_dict_recursive(data, cls)
        except ModelValidationError:
            raise
        except _PARSE_ERRORS:
            # Unchained: the parser's message can quote payload values.
            raise ModelValidationError(f"Invalid {cls.__name__} payload") from None

    @staticmethod
    def snake_to_camel(string: str) -> str:
        """Convert a snake_case string to camelCase.

        Args:
            string (str): The snake_case string to be converted.

        Returns:
            str: The converted camelCase string.

        Examples:
            >>> CamelCaseModel.snake_to_camel("example_string")
            'exampleString'

        """

        components = string.split("_")
        return components[0] + "".join(x.title() for x in components[1:])


##############################################
# Data models for Diagral API Authentification
##############################################


@dataclass
class LoginResponse(CamelCaseModel):
    """LoginResponse model represents the response received after a successful login.

    Attributes:
        access_token (str): The access token provided for authentication.

    Examples:
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

    Examples:
        >>> api_key_with_secret = ApiKeyWithSecret(api_key="your_api_key", secret_key="your_secret_key")
        >>> print(api_key_with_secret.api_key)
        your_api_key
        >>> print(api_key_with_secret.secret_key)
        your_secret_key

    """

    api_key: str
    secret_key: str

    def __post_init__(self):
        """Post-initialization processing to validate API key and secret key.

        Raises:
            ModelValidationError: If the API key or the secret key is empty or not a string.

        """
        if not self.api_key or not isinstance(self.api_key, str):
            raise ModelValidationError("api_key must be a non-empty string")
        if not self.secret_key or not isinstance(self.secret_key, str):
            raise ModelValidationError("secret_key must be a non-empty string")


@dataclass
class ApiKey(CamelCaseModel):
    """Represents an API key model.

    Attributes:
        api_key (str): The API key as a string.

    Examples:
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

    Examples:
        >>> data = {"api_keys": [{"api_key": "key1"}, {"api_key": "key2"}]}
        >>> api_keys = ApiKeys.from_dict(data)
        >>> print(api_keys.api_keys)
        [ApiKey(api_key='key1'), ApiKey(api_key='key2')]

    """

    api_keys: list[ApiKey]

    @classmethod
    def from_dict(cls, data: dict) -> ApiKeys:
        """Create an instance of ApiKeys from a dictionary.

        Raises:
            ModelValidationError: If the data is not an object or a key is malformed.

        """

        if not isinstance(data, dict):
            raise ModelValidationError(f"Invalid {cls.__name__} payload")
        try:
            return cls(
                api_keys=[ApiKey.from_dict(key) for key in data.get("api_keys") or []]
            )
        except ModelValidationError:
            raise
        except _PARSE_ERRORS:
            raise ModelValidationError(f"Invalid {cls.__name__} payload") from None


@dataclass
class SystemApiKeys(CamelCaseModel):
    """A system of the account, with the API keys created for it.

    Attributes:
        serial_id (str): The serial ID of the system.
        api_keys (list[str]): The API keys created for the system. They are secrets.

    Examples:
        >>> system = SystemApiKeys.from_dict({"serial_id": "123456", "api_keys": ["key1"]})
        >>> print(system.serial_id)
        123456

    """

    serial_id: str
    api_keys: list[str]


@dataclass
class TryConnectResult(CamelCaseModel):
    """A class representing the result of an API connection attempt.

    This class is used to store the result of an API connection attempt
    and the associated API keys if the connection was successful.

    Attributes:
        result (bool | None): Whether the connection attempt was successful. Defaults to False.
        keys (ApiKeyWithSecret | None): The API keys associated with the successful connection. Defaults to None.

    Examples:
        >>> keys = ApiKeyWithSecret(api_key="abc123", secret_key="xyz789")
        >>> result = TryConnectResult(result=True, keys=keys)
        >>> print(result.result)
        True
        >>> print(result.keys)
        ApiKeyWithSecret(api_key='abc123', secret_key='xyz789')

    """

    result: bool | None = False
    keys: ApiKeyWithSecret | None = None


@dataclass
class Ping(CamelCaseModel):
    """Answer of the Diagral cloud health check.

    Attributes:
        status (str): The status the cloud reports, such as "we're alive".

    Examples:
        >>> ping = Ping(status="we're alive")
        >>> print(ping.status)
        we're alive

    """

    status: str


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
        plugknx (str | None): The firmware version of the KNX plug, aliased as "PLUGKNX".
        boxradio (str | None): The firmware version of the box radio unit, aliased as "BOXRADIO".
        plug (str | None): The firmware version of the plug, aliased as "PLUG".

    Examples:
        >>> firmware = FirmwareModel(box="1.0.0", central="2.0.0", centralradio="3.0.0")
        >>> print(firmware.box)
        1.0.0
        >>> print(firmware.central)
        2.0.0
        >>> print(firmware.centralradio)
        3.0.0

    """

    box: str | None = field(default=None, metadata={"alias": "BOX"})
    central: str | None = field(default=None, metadata={"alias": "CENTRAL"})
    centralradio: str | None = field(default=None, metadata={"alias": "CENTRALRADIO"})
    plugknx: str | None = field(default=None, metadata={"alias": "PLUGKNX"})
    boxradio: str | None = field(default=None, metadata={"alias": "BOXRADIO"})
    plug: str | None = field(default=None, metadata={"alias": "PLUG"})


@dataclass
class CentralPlugModel(CamelCaseModel):
    """CentralPlugModel represents the central plug device.

    Attributes:
        name (str | None): The name of the central plug device.
        serial (str | None): The serial number of the central plug device.
        vendor (str | None): The vendor of the central plug device.
        firmwares (FirmwareModel | None): The firmware information of the central plug device.

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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
        presence_group (list[int] | None): A list of group marche presence, aliased as "presenceGroup".
        installation_state (int | None): The state of the installation, aliased as "installationState".
        central_information (CentralInformation | None): Information about the central unit, aliased as "centralInformation".
        partial_group1 (list[int] | None): A list of group marche partielle 1, aliased as "partialGroup1".
        partial_group2 (list[int] | None): A list of group marche partielle 2, aliased as "partialGroup2".

    Examples:
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
        ...     presence_group=[1, 2, 3],
        ...     installation_state=1,
        ...     central_information=CentralInformation(has_plug=True),
        ...     partial_group1=[4, 5, 6],
        ...     partial_group2=[7, 8, 9]
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
    presence_group: list[int] | None = field(
        default=None, metadata={"alias": "presenceGroup"}
    )
    installation_state: int | None = field(
        default=None, metadata={"alias": "installationState"}
    )
    central_information: CentralInformation | None = field(
        default=None, metadata={"alias": "centralInformation"}
    )
    partial_group1: list[int] | None = field(
        default=None, metadata={"alias": "partialGroup1"}
    )
    partial_group2: list[int] | None = field(
        default=None, metadata={"alias": "partialGroup2"}
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

    Examples:
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

    Examples:
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
        is_mjpeg_archive_video_supported (bool): Indicates if MJPEG archive video is supported.
        is_mass_storage_present (bool): Indicates if mass storage is present.
        is_remote_startup_shutdown_allowed (bool): Indicates if remote startup/shutdown is allowed.
        is_video_password_protected (bool): Indicates if the video is password protected.

    The API sends the five `Is*` fields as "True" / "False" strings; they are parsed
    into booleans.

    Examples:
        >>> system_details = SystemDetails(
        ...     device_type="PLUG_IP~DIAGRAL",
        ...     firmware_version="1.0.0",
        ...     ip_address="192.168.1.1",
        ...     ipoda_version="2.0.0",
        ...     mode="900",
        ...     first_vocal_contact="2023-10-01T12:00:00Z",
        ...     is_alarm_file_present=True,
        ...     is_mjpeg_archive_video_supported=True,
        ...     is_mass_storage_present=True,
        ...     is_remote_startup_shutdown_allowed=False,
        ...     is_video_password_protected=True
        ... )
        >>> print(system_details.device_type)
        PLUG_IP~DIAGRAL

    """

    device_type: str = field(metadata={"alias": "DeviceType"})
    firmware_version: str = field(metadata={"alias": "FirmwareVersion"})
    ip_address: str = field(metadata={"alias": "IpAddress"})
    ipoda_version: str = field(metadata={"alias": "IpodaVersion"})
    mode: str = field(metadata={"alias": "Mode"})
    first_vocal_contact: str = field(metadata={"alias": "FirstVocalContact"})
    is_alarm_file_present: bool = field(metadata={"alias": "IsAlarmFilePresent"})
    is_mjpeg_archive_video_supported: bool = field(
        metadata={"alias": "IsMJPEGArchiveVideoSupported"}
    )
    is_mass_storage_present: bool = field(metadata={"alias": "IsMassStoragePresent"})
    is_remote_startup_shutdown_allowed: bool = field(
        metadata={"alias": "IsRemoteStartupShutdownAllowed"}
    )
    is_video_password_protected: bool = field(
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

    Examples:
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

    Examples:
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

    Examples:
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

    Examples:
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
        """Create an instance of Anomalies from a dictionary.

        A `created_at` without an offset is taken as UTC; one with an offset is
        converted to UTC.

        Raises:
            ModelValidationError: If the data is not an object, `created_at` is missing
                or not an ISO date, or a device entry is malformed.

        """

        def create_devices(device_data: list[dict] | None) -> list[AnomalyDetail]:
            return [
                AnomalyDetail(
                    serial=device.get("serial"),
                    index=device.get("index"),
                    group=device.get("group"),
                    label=device.get("label"),
                    anomaly_names=[
                        AnomalyName.from_dict(name)
                        for name in device.get("anomaly_names") or []
                    ],
                )
                for device in device_data or []
            ]

        if not isinstance(data, dict):
            raise ModelValidationError(f"Invalid {cls.__name__} payload")
        try:
            created_at = datetime.fromisoformat(data["created_at"])
            created_at = (
                created_at.replace(tzinfo=UTC)
                if created_at.tzinfo is None
                else created_at.astimezone(UTC)
            )
            return cls(
                created_at=created_at,
                sensors=create_devices(data.get("sensors")),
                badges=create_devices(data.get("badges")),
                sirens=create_devices(data.get("sirens")),
                cameras=create_devices(data.get("cameras")),
                commands=create_devices(data.get("commands")),
                transceivers=create_devices(data.get("transceivers")),
                transmitters=create_devices(data.get("transmitters")),
                central=create_devices(data.get("central")),
            )
        except ModelValidationError:
            raise
        except _PARSE_ERRORS:
            raise ModelValidationError(f"Invalid {cls.__name__} payload") from None


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

    Examples:
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

    Examples:
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
        device_type (str | None): The type of the device, when provided.
        device_index (str | None): The index of the device, when provided.
        device_label (str | None): The label of the device, which is optional.

    Examples:
        >>> detail = WebHookNotificationDetail(device_type="Sensor", device_index="1", device_label="Front Door Sensor")
        >>> print(detail.device_type)
        Sensor
        >>> print(detail.device_index)
        1
        >>> print(detail.device_label)
        Front Door Sensor

    """

    device_type: str | None = None
    device_index: str | None = None
    device_label: str | None = None


@dataclass
class WebHookNotificationUser(CamelCaseModel):
    """WebHookNotificationUser represents a user who receives webhook notifications.

    Attributes:
        username (str | None): The username of the user.
        user_type (str | None): The type of the user.

    Examples:
        >>> user = WebHookNotificationUser(username="Dark Vador", user_type="owner")
        >>> print(user.username)
        Dark Vador
        >>> print(user.user_type)
        owner

    """

    username: str | None = None
    user_type: str | None = None


@dataclass
class WebHookNotification(CamelCaseModel):
    """A model representing a webhook notification.

    Attributes:
        transmitter_id (str): The ID of the transmitter sending the notification.
        alarm_type (str): The type of alarm, determined based on the alarm code.
        alarm_code (str): The code representing the specific alarm.
        alarm_description (str | None): A description of the alarm, when provided.
        group_index (str | None): The index of the group associated with the alarm.
        detail (WebHookNotificationDetail): Detailed information about the webhook notification.
            Only during anomaly/alert notification.
        user (WebHookNotificationUser | None): The user who triggered the notification.
            Only during change state notification.
        date_time (datetime): The date and time when the notification was generated.

    Methods:
        from_dict(data: dict) -> WebHookNotification:
            Create an instance of WebHookNotification from a dictionary.

    Examples:
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
    alarm_description: str | None
    group_index: str | None
    detail: WebHookNotificationDetail
    user: WebHookNotificationUser | None
    date_time: datetime

    @classmethod
    def from_dict(cls, data: dict) -> WebHookNotification:
        """Create an instance of WebHookNotification from a dictionary.

        Missing or null optional fields are accepted. Numeric event codes and
        device/group indexes are normalized to strings.

        Raises:
            ModelValidationError: If a required field is missing or the payload is malformed.

        """

        if not isinstance(data, dict):
            raise ModelValidationError("Webhook notification must be an object")
        transmitter_id = data.get("transmitter_id")
        if not isinstance(transmitter_id, str) or not transmitter_id.strip():
            raise ModelValidationError(
                "Webhook transmitter_id must be a non-empty string"
            )
        code = data.get("alarm_code")
        if isinstance(code, bool) or not isinstance(code, (str, int)):
            raise ModelValidationError("Webhook alarm_code must contain digits")
        try:
            code_text = str(code)
            numeric_code = int(code_text)
        except ValueError:
            raise ModelValidationError(
                "Webhook alarm_code must contain digits"
            ) from None
        if not code_text.isdigit():
            raise ModelValidationError("Webhook alarm_code must contain digits")
        date_time = data.get("date_time")
        if not isinstance(date_time, str) or not date_time:
            raise ModelValidationError("Webhook date_time must be an ISO date string")
        try:
            parsed_date = datetime.fromisoformat(date_time)
        except ValueError:
            raise ModelValidationError(
                "Webhook date_time must be an ISO date string"
            ) from None

        def optional_text(
            value: object, name: str, *, allow_index: bool = False
        ) -> str | None:
            """Normalize an optional field or reject an invalid payload value."""
            if value is None or isinstance(value, str):
                return value
            if allow_index and isinstance(value, int) and not isinstance(value, bool):
                return str(value)
            raise ModelValidationError(f"Webhook {name} has an invalid type")

        detail_data = data.get("detail")
        if detail_data is None:
            detail_data = {}
        if not isinstance(detail_data, dict):
            raise ModelValidationError("Webhook detail must be an object or null")
        user_data = data.get("user")
        if user_data is not None and not isinstance(user_data, dict):
            raise ModelValidationError("Webhook user must be an object or null")

        def alarm_type(alarm_code: int) -> str:
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

            if alarm_code in ANOMALY_CODES:
                return "ANOMALY"
            if alarm_code in ALERT_CODES:
                return "ALERT"
            if alarm_code in STATUS_CODES:
                return "STATUS"
            return "UNKNOWN"

        # Create user object only if user data exists
        user: WebHookNotificationUser | None = (
            WebHookNotificationUser(
                username=optional_text(user_data.get("username"), "user.username"),
                user_type=optional_text(user_data.get("user_type"), "user.user_type"),
            )
            if user_data
            else None
        )

        return cls(
            transmitter_id=transmitter_id,
            alarm_type=alarm_type(numeric_code),
            alarm_code=code_text,
            alarm_description=optional_text(
                data.get("alarm_description"), "alarm_description"
            ),
            group_index=optional_text(
                data.get("group_index"), "group_index", allow_index=True
            ),
            detail=WebHookNotificationDetail(
                device_type=optional_text(
                    detail_data.get("device_type"), "detail.device_type"
                ),
                device_index=optional_text(
                    detail_data.get("device_index"),
                    "detail.device_index",
                    allow_index=True,
                ),
                device_label=optional_text(
                    detail_data.get("device_label"), "detail.device_label"
                ),
            ),
            user=user,
            date_time=parsed_date,
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

    Examples:
        >>> rude = Rude(name="Device1", canal="Canal1", mode="ON")
        >>> print(rude.name)
        Device1

    """

    name: str
    canal: str
    mode: str

    def __post_init__(self):
        """Post-initialization processing to validate mode.

        Raises:
            ModelValidationError: If mode is not one of ON, PULSE, SWITCH or TIMER.

        """
        valid_modes = {"ON", "PULSE", "SWITCH", "TIMER"}
        if self.mode not in valid_modes:
            raise ModelValidationError(f"mode must be one of {valid_modes}")


@dataclass
class Rudes(CamelCaseModel):
    """Rudes model representing a collection of Rude instances.

    Attributes:
        rudes (list[Rude]): A list of Rude objects.

    Examples:
        >>> rude1 = Rude(name="Device1", canal="Canal1", mode="ON")
        >>> rude2 = Rude(name="Device2", canal="Canal2", mode="PULSE")
        >>> rudes = Rudes(rudes=[rude1, rude2])
        >>> print(rudes.rudes[0].name)
        Device1

    """

    rudes: list[Rude]
