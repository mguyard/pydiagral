"""Local alternative service: ownership, redaction and no command replay."""

import asyncio
from contextlib import asynccontextmanager
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pydiagral.api import DiagralAPI
from pydiagral.exceptions import (
    ClientError,
    ConfigurationError,
    DiagralAPIError,
    ValidationError,
)
from pydiagral.models import AlarmConfiguration, Group
from pydiagral.topaze_api import TopazeDiagralAPI


def client():
    """Create a client with synthetic secrets and a caller-owned session."""
    return TopazeDiagralAPI(
        username="test@example.com",
        password="test-password",
        serial_id="1234567890",
        pincode="1234",
        apikey="key",
        secret_key="secret",
        session=MagicMock(closed=False),
    )


def responses(*, connect=None):
    """Return a matching system and a session owned by this client."""
    return [
        {"sessionId": "own-login"},
        {"systems": [{"id": 1, "role": 1}]},
        {"id": 1, "role": 1, "transmitterId": "1234567890", "centralId": "CENTRAL"},
        connect if connect is not None else {"ttmSessionId": "own-ttm"},
        {"status": "OK"},
        {"status": "OK"},
    ]


class TestTopazeSession:
    """Never take over another client's session and always release ours."""

    async def test_cleanup_rejection_still_logs_out(self, caplog):
        """An HTTP 200 semantic error is reported without masking the main read."""
        api = client()
        answers = responses()
        answers[-2] = {"status": "ERROR", "message": "private-server-detail"}
        api._topaze_call = AsyncMock(side_effect=answers)  # noqa: SLF001
        async with api._topaze_session():  # noqa: SLF001
            pass
        assert api._topaze_call.call_args_list[-1].args[1] == "authenticate/logout"  # noqa: SLF001
        assert "Topaze session cleanup failed" in caplog.text
        assert "private-server-detail" not in caplog.text

    async def test_different_central_never_connects(self):
        """The registry identity guard stops replacement entities being created."""
        api = client()
        api.expected_central_serial = "ORIGINAL-CENTRAL"
        api._topaze_call = AsyncMock(side_effect=[*responses()[:3], {"status": "OK"}])  # noqa: SLF001
        with pytest.raises(DiagralAPIError):
            async with api._topaze_session():  # noqa: SLF001
                pytest.fail("wrong central")
        assert "authenticate/connect" not in [
            c.args[1]
            for c in api._topaze_call.call_args_list  # noqa: SLF001
        ]

    async def test_error_closes_only_owned_sessions(self):
        """A failed read releases only the two sessions opened by this call."""
        api = client()
        api._topaze_call = AsyncMock(side_effect=responses())  # noqa: SLF001
        with pytest.raises(ClientError):
            async with api._topaze_session():  # noqa: SLF001
                raise ClientError("read failed")
        calls = api._topaze_call.call_args_list  # noqa: SLF001
        assert [c.args[1] for c in calls][-2:] == [
            "authenticate/disconnect",
            "authenticate/logout",
        ]
        assert calls[-2].kwargs["payload"]["ttmSessionId"] == "own-ttm"
        assert all("getLastTtmSessionId" not in c.args[1] for c in calls)

    async def test_existing_session_is_not_disconnected(self):
        """A mobile connection never triggers takeover logic."""
        api = client()
        api._topaze_call = AsyncMock(  # noqa: SLF001
            side_effect=responses(
                connect={"message": "transmitter.connection.sessionalreadyopen"}
            )
        )
        with pytest.raises(DiagralAPIError):
            async with api._topaze_session():  # noqa: SLF001
                pytest.fail("must not take over")
        endpoints = [c.args[1] for c in api._topaze_call.call_args_list]  # noqa: SLF001
        assert "authenticate/disconnect" not in endpoints
        assert endpoints[-1] == "authenticate/logout"

    async def test_cancelled_read_still_cleans_up(self):
        """Cancellation is propagated after owned session cleanup."""
        api = client()
        api._topaze_call = AsyncMock(side_effect=responses())  # noqa: SLF001
        with pytest.raises(asyncio.CancelledError):
            async with api._topaze_session():  # noqa: SLF001
                raise asyncio.CancelledError
        assert api._topaze_call.call_args_list[-1].args[1] == "authenticate/logout"  # noqa: SLF001

    async def test_wrong_transmitter_never_connects(self):
        """Another system on the account cannot be selected accidentally."""
        api = client()
        data = responses()
        data[2]["transmitterId"] = "another-system"
        api._topaze_call = AsyncMock(side_effect=[*data[:3], {"status": "OK"}])  # noqa: SLF001
        with pytest.raises(DiagralAPIError):
            async with api._topaze_session():  # noqa: SLF001
                pytest.fail("wrong transmitter")
        assert "authenticate/connect" not in [
            c.args[1]
            for c in api._topaze_call.call_args_list  # noqa: SLF001
        ]


class TestTopazeTransport:
    """Keep secrets out of the SDK's JSON debug logger."""

    def test_unverified_vendor_is_rejected(self):
        """A fixed Diagral header must never be used with another brand's account."""
        with pytest.raises(ConfigurationError, match="Diagral vendor only"):
            TopazeDiagralAPI(
                username="test@example.com",
                password="test-password",
                vendor="DAITEM",
            )

    def test_optional_pin_is_not_required_for_account_management(self):
        """Removing an entry still constructs the SDK client without a PIN."""
        api = TopazeDiagralAPI(
            username="test@example.com",
            password="test-password",
            session=MagicMock(closed=False),
        )
        assert api.serial_id is None

    async def test_actual_sdk_debug_logs_never_contain_session_secrets(self, caplog):
        """Exercise the real SDK logger, with only the HTTP response mocked."""
        api = client()
        response = MagicMock(status=200)
        response.json = AsyncMock(return_value={})
        api.session.request.return_value.__aenter__.return_value = response
        secrets = {
            "masterCode": "private-pin-value",
            "ttmSessionId": "private-ttm-value",
        }
        with caplog.at_level(logging.DEBUG, logger="pydiagral.api"):
            await api._topaze_call(  # noqa: SLF001
                "POST",
                "authenticate/connect",
                payload=secrets,
                token="private-token-value",
            )
        assert "Sending POST request" in caplog.text
        assert all(
            value not in caplog.text
            for value in (*secrets.values(), "private-token-value")
        )

    async def test_request_uses_dedicated_service_and_redacted_json(self):
        """Topaze URLs need no traversal and their secret fields are redacted."""
        api = client()
        payload = {"masterCode": "1234", "ttmSessionId": "own-session"}
        with patch.object(
            DiagralAPI, "_request", AsyncMock(return_value=({}, 200))
        ) as request:
            await api._topaze_call(  # noqa: SLF001
                "POST", "authenticate/connect", payload=payload, token="login-token"
            )
        args = request.call_args
        assert args.args == ("POST", "authenticate/connect")
        assert args.kwargs["base_url"] == "https://appv3.tt-monitor.com/topaze"
        assert args.kwargs["versioned"] is False
        assert args.kwargs["json"] == payload
        assert args.kwargs["headers"]["Authorization"] == "Bearer login-token"

    async def test_inventory_allows_only_empty_success_ack(self):
        """An empty acknowledgement still requires a completed valid inventory."""
        api = client()
        context = SimpleNamespace(
            token="login",
            ttm="ttm",
            config={"id": 1, "centralId": "c", "transmitterId": "t"},
            connected={"versions": {"box": "1.0"}},
        )
        api._topaze_call = AsyncMock(  # noqa: SLF001
            side_effect=[
                ValidationError("empty", status_code=200),
                {
                    "status": "request_status_done",
                    "response": '{"centralLearningZone":{}}',
                },
            ]
        )
        with patch("pydiagral.topaze_api.asyncio.sleep", AsyncMock()):
            result = await api._read_inventory(context)  # noqa: SLF001
        assert result == {"centralLearningZone": {}}
        assert [c.args[0] for c in api._topaze_call.call_args_list] == ["POST", "GET"]  # noqa: SLF001

    async def test_inventory_does_not_mask_auth_error(self):
        """A failed kickoff cannot be treated as an accepted job."""
        api = client()
        context = SimpleNamespace(
            token="login",
            ttm="ttm",
            config={"id": 1, "centralId": "c", "transmitterId": "t"},
            connected={"versions": {"box": "1.0"}},
        )
        api._topaze_call = AsyncMock(  # noqa: SLF001
            side_effect=DiagralAPIError("forbidden", status_code=403)
        )
        with pytest.raises(DiagralAPIError):
            await api._read_inventory(context)  # noqa: SLF001
        assert api._topaze_call.await_count == 1  # noqa: SLF001


class TestTopazeCommands:
    """An ambiguous command is never sent twice or sent to another backend."""

    @pytest.mark.parametrize("method", ["start_system", "stop_system", "presence"])
    async def test_lost_response_is_not_replayed(self, method):
        """Lost responses cannot dispatch twice or switch command backends."""
        api = client()
        api.alarm_configuration = AlarmConfiguration(groups=[Group(index=1)])
        ctx = SimpleNamespace(
            token="login",
            ttm="ttm",
            config={},
            connected={"systemState": "off", "groups": []},
        )

        @asynccontextmanager
        async def session():
            yield ctx

        api._topaze_session = session  # noqa: SLF001
        api._topaze_call = AsyncMock(side_effect=ClientError("lost response"))  # noqa: SLF001
        with pytest.raises(ClientError):
            await getattr(api, method)()
        assert api._topaze_call.await_count == 1  # noqa: SLF001
        assert api._topaze_call.call_args.args[1] == "action/stateCommand"  # noqa: SLF001

    def test_group_commands_keep_existing_sdk_behavior(self):
        """Unverified group transition semantics stay on the official SDK path."""
        assert TopazeDiagralAPI.activate_group is DiagralAPI.activate_group
        assert TopazeDiagralAPI.disable_group is DiagralAPI.disable_group


@pytest.mark.parametrize("failure", [ClientError("network"), TimeoutError()])
async def test_configuration_refresh_retains_validated_cache(failure):
    """Transient inventory failures cannot block a fresh status read."""
    api = client()
    config = AlarmConfiguration(groups=[Group(index=1)])
    api.alarm_configuration = config
    api._configuration_read_at = -float("inf")  # noqa: SLF001
    api._topaze_call = AsyncMock(side_effect=responses())  # noqa: SLF001
    api._read_inventory = AsyncMock(side_effect=failure)  # noqa: SLF001
    assert await api.get_configuration() is config


async def test_configuration_refresh_does_not_hide_identity_change():
    """A stale cache must never hide selection of another central."""
    api = client()
    api.alarm_configuration = AlarmConfiguration(groups=[Group(index=1)])
    api._configuration_read_at = -float("inf")  # noqa: SLF001
    api.expected_central_serial = "ORIGINAL-CENTRAL"
    api._topaze_call = AsyncMock(side_effect=[*responses()[:3], {"status": "OK"}])  # noqa: SLF001
    with pytest.raises(ConfigurationError, match="central differs"):
        await api.get_configuration()


async def test_configuration_refresh_does_not_hide_invalid_inventory():
    """A malformed successful response stays an error even with cached metadata."""
    api = client()
    api.alarm_configuration = AlarmConfiguration(groups=[Group(index=1)])
    api._configuration_read_at = -float("inf")  # noqa: SLF001
    api._topaze_call = AsyncMock(side_effect=responses())  # noqa: SLF001
    api._read_inventory = AsyncMock(return_value={})  # noqa: SLF001
    with pytest.raises(ValidationError):
        await api.get_configuration()


async def test_initial_inventory_failure_is_not_hidden():
    """Without a validated inventory there is no safe cache to use."""
    api = client()
    api._topaze_call = AsyncMock(side_effect=responses())  # noqa: SLF001
    api._read_inventory = AsyncMock(side_effect=ClientError("network"))  # noqa: SLF001
    with pytest.raises(ClientError):
        await api.get_configuration()


@pytest.mark.parametrize("versions", [None, {}, {"box": None}, {"box": ""}])
async def test_missing_box_version_is_validation_error(versions):
    """Malformed connect metadata raises only a documented SDK exception."""
    api = client()
    api._topaze_call = AsyncMock(  # noqa: SLF001
        side_effect=responses(connect={"ttmSessionId": "own-ttm", "versions": versions})
    )
    with pytest.raises(ValidationError, match="box version"):
        await api.get_configuration()
    assert api._topaze_call.call_args_list[-2].args[1] == "authenticate/disconnect"  # noqa: SLF001
    assert api._topaze_call.call_args_list[-1].args[1] == "authenticate/logout"  # noqa: SLF001


async def test_inventory_timeout_uses_sdk_error_hierarchy():
    """An inventory deadline does not leak a bare asyncio timeout to consumers."""
    api = client()
    api._poll_inventory = AsyncMock(side_effect=TimeoutError)  # noqa: SLF001
    with pytest.raises(ClientError, match="inventory read timed out"):
        await api._read_inventory(SimpleNamespace())  # noqa: SLF001


async def test_configuration_cache_and_live_status_are_separate():
    """Metadata is reused, while every live status read owns a new session."""
    api = client()
    inventory = {
        "centralLearningZone": {
            "centralInformation": {},
            "groupNames": {"1": "Doors"},
            "sensors": [{"index": 1, "customLabel": "Window"}],
        },
        "centralSettingsZone": {"nbGroups": 1},
    }
    api._read_inventory = AsyncMock(return_value=inventory)  # noqa: SLF001
    answers = responses()
    api._topaze_call = AsyncMock(side_effect=answers)  # noqa: SLF001
    config = await api.get_configuration()
    assert config.alarm.central.serial == "CENTRAL"
    assert await api.get_configuration() is config
    assert api._read_inventory.await_count == 1  # noqa: SLF001
    devices = await api.get_devices_info()
    assert devices.sensors[0].label == "Window"
    api._topaze_call = AsyncMock(  # noqa: SLF001
        side_effect=[*answers[:4], {"systemState": "off", "groups": []}, *answers[-2:]]
    )
    status = await api.get_system_status()
    assert status.status == "off"
    assert api._topaze_call.call_args_list[0].args[1] == "authenticate/login"  # noqa: SLF001
