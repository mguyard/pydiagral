"""Safety boundaries for the local whole-system Topaze command planner."""

from copy import deepcopy

import pytest

from pydiagral.exceptions import ConfigurationError
from pydiagral.models import AlarmConfiguration, Group, SystemStatus
from pydiagral.topaze_commands import plan_command


@pytest.mark.parametrize(
    ("action", "expected_state"),
    [("start", "on"), ("stop", "off"), ("presence", "presence")],
    ids=["arm-away", "disarm", "arm-home"],
)
def test_whole_system_payload(action: str, expected_state: str) -> None:
    """Use the verified protocol and actual group count without session secrets."""
    config = AlarmConfiguration(groups=[Group(index=n) for n in range(1, 9)])
    status = SystemStatus(status="group", activated_groups=[2, 5])
    before = deepcopy((config, status))

    assert plan_command(action, config, status) == {
        "systemState": expected_state,
        "group": [],
        "currentGroup": [],
        "nbGroups": "8",
    }
    assert (config, status) == before


@pytest.mark.parametrize(
    "action",
    ["activate_group", "disable_group", "partial_start_1", "unknown"],
    ids=["group-arm", "group-disarm", "partial-arm", "unknown-action"],
)
def test_unverified_actions_are_rejected(action: str) -> None:
    """Never silently replace a partial command with a whole-system command."""
    config = AlarmConfiguration(groups=[Group(index=1)])
    with pytest.raises(ConfigurationError, match="Unsupported Topaze action"):
        plan_command(action, config, SystemStatus("off", []), [1])


@pytest.mark.parametrize("groups", [[], [1], [True]], ids=["empty", "one", "bool"])
def test_group_argument_is_never_ignored(groups: list[int]) -> None:
    """A caller requesting groups cannot accidentally arm or disarm everything."""
    config = AlarmConfiguration(groups=[Group(index=1)])
    with pytest.raises(ConfigurationError, match="whole-system"):
        plan_command("stop", config, SystemStatus("group", [1]), groups)


@pytest.mark.parametrize(
    "indexes",
    [None, [], [True], [0], [1, 1], [1, 3], ["1"]],
    ids=["missing", "empty", "bool", "zero", "duplicate", "gap", "text"],
)
def test_invalid_group_metadata_blocks_dispatch(indexes) -> None:
    """A guessed or incomplete group count must never reach the alarm."""
    config = AlarmConfiguration(
        groups=None if indexes is None else [Group(index=n) for n in indexes]
    )
    with pytest.raises(ConfigurationError, match="group configuration"):
        plan_command("start", config, SystemStatus("off", []))
