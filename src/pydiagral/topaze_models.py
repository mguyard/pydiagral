"""Translate verified Topaze read fields into the existing SDK models."""

from typing import Any

from pydiagral.exceptions import ModelValidationError
from pydiagral.models import (
    AlarmConfiguration,
    AlarmModel,
    BoxModel,
    Cameras,
    CentralInformation,
    CentralPlugModel,
    FirmwareModel,
    Group,
    SensorModel,
    SystemStatus,
    TransceiverModel,
    TransmitterModel,
)

from .constants import STATUS_GROUP, STATUS_OFF, STATUS_PRESENCE, STATUS_TEMPO_GROUP

_STATUS_MAP = {
    "off": STATUS_OFF,
    "on": STATUS_GROUP,
    "group": STATUS_GROUP,
    "tempogroup": STATUS_TEMPO_GROUP,
    "tempo_group": STATUS_TEMPO_GROUP,
    "presence": STATUS_PRESENCE,
}


def _object(value: Any) -> dict[str, Any]:
    """Reject unexpected containers without including their content in errors."""
    if not isinstance(value, dict):
        raise ModelValidationError("Invalid Topaze object")
    return value


def _text(value: Any, *, required: bool = False) -> str | None:
    """Preserve identifiers exactly, including their leading zeros."""
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value):
        raise ModelValidationError("Invalid Topaze text field")
    return value


def _integer(value: Any, *, required: bool = False) -> int | None:
    """Reject booleans and negative values where the protocol names an index."""
    if value is None and not required:
        return None
    if type(value) is not int or value < 0:
        raise ModelValidationError("Invalid Topaze integer field")
    return value


def _entries(value: Any) -> list[dict[str, Any]]:
    """Validate indexes before devices can be associated with anomaly details."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ModelValidationError("Invalid Topaze device list")
    indexes = set()
    for raw_item in value:
        item = _object(raw_item)
        index = _integer(item.get("index"), required=True)
        if index in indexes:
            raise ModelValidationError("Duplicate Topaze device index")
        indexes.add(index)
    return value


def _device_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Copy descriptive fields only; fault and inhibition semantics are separate."""
    return {
        "index": _integer(item.get("index"), required=True),
        "label": _text(item.get("customLabel")),
        "serial": _text(item.get("radioId")),
        "ref_code": _text(item.get("refCode")),
        "group": _integer(item.get("affectedToZone")),
        "type": _integer(item.get("type")),
        "gamme": _integer(item.get("gamme")),
        "subtype": _integer(item.get("subType")),
    }


def _group_selection(value: Any, group_ids: set[int]) -> list[int] | None:
    """Keep missing settings unknown and reject selected nonexistent groups."""
    if value is None:
        return None
    selected = []
    for key, enabled in _object(value).items():
        if not isinstance(key, str) or not key.isdecimal() or type(enabled) is not bool:
            raise ModelValidationError("Invalid Topaze group selection")
        index = int(key)
        if enabled:
            if index not in group_ids:
                raise ModelValidationError("Unknown Topaze selected group")
            selected.append(index)
    if len(set(selected)) != len(selected):
        raise ModelValidationError("Duplicate Topaze selected group")
    return sorted(selected)


def build_configuration(
    inventory: dict[str, Any],
    system_config: dict[str, Any],
    connected: dict[str, Any],
) -> AlarmConfiguration:
    """Preserve the account's central identity and the inventory's group settings."""
    inventory = _object(inventory)
    system_config = _object(system_config)
    learning = _object(inventory.get("centralLearningZone"))
    settings = _object(inventory.get("centralSettingsZone"))
    central_id = _text(system_config.get("centralId"), required=True)
    transmitter_id = _text(system_config.get("transmitterId"), required=True)
    # centralInformation.radioId is a different identifier on real installations.
    central = _object(learning.get("centralInformation"))
    group_names = _object(learning.get("groupNames"))
    group_count = _integer(settings.get("nbGroups"), required=True)
    if not group_count:
        raise ModelValidationError("Missing Topaze group topology")
    group_ids = set(range(1, group_count + 1))
    input_delays = _object(settings.get("inputDelays", {}))
    output_delays = _object(settings.get("outputDelays", {}))
    groups = []
    for index in sorted(group_ids):
        key = str(index)
        if key not in group_names:
            raise ModelValidationError("Missing Topaze configured group")
        groups.append(
            Group(
                index=index,
                name=_text(group_names[key], required=True),
                input_delay=_integer(input_delays.get(key)),
                output_delay=_integer(output_delays.get(key)),
            )
        )

    versions = _object(_object(connected).get("versions", {})).copy()
    versions.update(
        _object(_object(inventory.get("factoryZone", {})).get("versions", {}))
    )
    firmwares = FirmwareModel(
        box=_text(versions.get("box")),
        boxradio=_text(versions.get("boxRadio")),
        central=_text(versions.get("central")),
        centralradio=_text(versions.get("centralRadio")),
        plugknx=_text(versions.get("plugKnx")),
        plug=_text(versions.get("plug")),
    )
    video = _object(inventory.get("boxVideoZone", {}))
    return AlarmConfiguration(
        alarm=AlarmModel(
            name=_text(system_config.get("name")),
            central=CentralPlugModel(
                name=_text(central.get("customLabel")),
                serial=central_id,
                firmwares=firmwares,
            ),
            box=BoxModel(serial=transmitter_id, firmwares=firmwares),
        ),
        groups=groups,
        sensors=[
            SensorModel(**_device_fields(item))
            for item in _entries(learning.get("sensors"))
        ],
        commands=[
            SensorModel(**_device_fields(item))
            for item in _entries(learning.get("commands"))
        ],
        sirens=[
            SensorModel(**_device_fields(item))
            for item in _entries(learning.get("alarms"))
        ],
        transmitters=[
            TransmitterModel(**_device_fields(item))
            for item in _entries(learning.get("transmitters"))
        ],
        transceivers=[
            TransceiverModel(**_device_fields(item))
            for item in _entries(learning.get("transceivers"))
        ],
        cameras=[
            Cameras(
                index=_integer(item.get("index"), required=True),
                name=_text(item.get("name")),
            )
            for item in _entries(video.get("cameras"))
        ],
        presence_group=_group_selection(
            settings.get("groupesMarchePresence"), group_ids
        ),
        partial_group1=_group_selection(
            settings.get("groupesMarchePartielle1"), group_ids
        ),
        partial_group2=_group_selection(
            settings.get("groupesMarchePartielle2"), group_ids
        ),
        central_information=CentralInformation(firmwares=firmwares),
    )


def normalize_status(
    payload: dict[str, Any], config: AlarmConfiguration
) -> SystemStatus:
    """Return a validated live state without inferring missing armed groups."""
    payload = _object(payload)
    state = payload.get("systemState")
    if not isinstance(state, str) or state not in _STATUS_MAP:
        raise ModelValidationError("Unknown Topaze system state")
    if payload.get("commandStatus") not in (None, "CMD_OK"):
        raise ModelValidationError("Topaze status read failed")
    groups = payload.get("groups")
    if not isinstance(groups, list) or any(type(item) is not int for item in groups):
        raise ModelValidationError("Invalid Topaze active groups")
    configured = {group.index for group in config.groups or []}
    if len(set(groups)) != len(groups) or not set(groups) <= configured:
        raise ModelValidationError("Unknown or duplicate Topaze active groups")
    if (state in ("on", "group") and not groups) or (state == "off" and groups):
        raise ModelValidationError("Inconsistent Topaze system state")
    return SystemStatus(status=_STATUS_MAP[state], activated_groups=list(groups))
