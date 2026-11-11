"""Plan the verified whole-system Topaze commands without sending them."""

from typing import Any

from pydiagral.exceptions import ConfigurationError
from pydiagral.models import AlarmConfiguration, SystemStatus

_WHOLE_SYSTEM_STATES = {"start": "on", "stop": "off", "presence": "presence"}


def plan_command(
    action: str,
    config: AlarmConfiguration,
    status: SystemStatus,
    groups: list[int] | None = None,
) -> dict[str, Any]:
    """Build one command payload, without session credentials or network I/O.

    Whole-system operations do not depend on the previous state. Group actions
    stay on Emerald until their transition semantics are verified for Topaze.
    """
    if action not in _WHOLE_SYSTEM_STATES:
        raise ConfigurationError("Unsupported Topaze action")
    if groups is not None:
        raise ConfigurationError("Topaze supports whole-system commands only")
    indexes: list[int] = []
    for group in config.groups or []:
        index = group.index
        if type(index) is not int:
            raise ConfigurationError("Incomplete Topaze group configuration")
        indexes.append(index)
    if not indexes or sorted(indexes) != list(range(1, len(indexes) + 1)):
        raise ConfigurationError("Incomplete Topaze group configuration")
    return {
        "systemState": _WHOLE_SYSTEM_STATES[action],
        "group": [],
        "currentGroup": [],
        "nbGroups": str(len(indexes)),
    }
