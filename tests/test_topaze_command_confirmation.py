"""A Topaze acknowledgement alone cannot confirm an alarm command."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pydiagral.exceptions import ClientError, DiagralAPIError
from pydiagral.models import AlarmConfiguration, Group
from pydiagral.topaze_api import TopazeDiagralAPI


def make_api(responses) -> TopazeDiagralAPI:
    """Build an isolated command client with no network or credentials."""
    api = object.__new__(TopazeDiagralAPI)
    api.alarm_configuration = AlarmConfiguration(
        groups=[Group(index=1), Group(index=2)]
    )
    context = SimpleNamespace(
        token="test-token",
        ttm="test-ttm",
        config={"centralId": "test-central"},
        connected={"systemState": "off", "groups": []},
    )

    @asynccontextmanager
    async def session():
        yield context

    api._topaze_session = session  # noqa: SLF001
    api._topaze_call = AsyncMock(side_effect=responses)  # noqa: SLF001
    return api


@pytest.mark.parametrize(
    ("action", "state", "groups"),
    [
        ("start", "off", []),
        ("stop", "group", [1, 2]),
        ("presence", "off", []),
        ("presence", "group", [1, 2]),
    ],
    ids=["away-still-off", "disarm-still-armed", "home-still-off", "wrong-mode"],
)
async def test_acknowledged_command_requires_requested_state(
    action: str, state: str, groups: list[int]
) -> None:
    """Never report success merely because the command was accepted."""
    api = make_api(
        [
            {"commandStatus": "CMD_OK"},
            {"commandStatus": "CMD_OK", "systemState": state, "groups": groups},
        ]
    )
    with pytest.raises(DiagralAPIError, match="requested state"):
        await api._topaze_command(action)  # noqa: SLF001
    assert [call.args[1] for call in api._topaze_call.call_args_list] == [  # noqa: SLF001
        "action/stateCommand",
        "status/getSystemState",
    ]


@pytest.mark.parametrize(
    ("action", "state", "groups", "expected"),
    [
        ("start", "on", [1, 2], "group"),
        ("start", "tempogroup", [], "tempo_group"),
        ("stop", "off", [], "off"),
        ("presence", "presence", [1], "presence"),
    ],
    ids=["away", "away-exit-delay", "disarm", "home"],
)
async def test_confirmed_command_returns_observed_state(
    action: str, state: str, groups: list[int], expected: str
) -> None:
    """Accept exit delay without inventing armed groups or skipping the read."""
    api = make_api(
        [
            {"commandStatus": "CMD_OK"},
            {"commandStatus": "CMD_OK", "systemState": state, "groups": groups},
        ]
    )
    result = await api._topaze_command(action)  # noqa: SLF001
    assert result.status == expected
    assert result.activated_groups == groups
    assert api._topaze_call.await_count == 2  # noqa: SLF001


@pytest.mark.parametrize("failure_after_ack", [False, True], ids=["command", "read"])
async def test_ambiguous_failure_never_replays_command(failure_after_ack: bool) -> None:
    """Timeouts propagate for read-only reconciliation in the panel."""
    responses = [{"commandStatus": "CMD_OK"}] if failure_after_ack else []
    responses.append(ClientError("Simulated timeout"))
    api = make_api(responses)
    with pytest.raises(ClientError):
        await api._topaze_command("stop")  # noqa: SLF001
    sent = [
        call
        for call in api._topaze_call.call_args_list  # noqa: SLF001
        if call.args[1] == "action/stateCommand"
    ]
    assert len(sent) == 1
