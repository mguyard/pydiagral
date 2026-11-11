"""Automatic failover publishes one complete snapshot and never replays commands."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pydiagral import CoreSnapshot, FailoverDiagralAPI
from pydiagral.exceptions import (
    AuthenticationError,
    ClientError,
    ConfigurationError,
    PinCodeError,
    ServerError,
    ValidationError,
)
from pydiagral.models import (
    AlarmConfiguration,
    AlarmModel,
    Cameras,
    CentralPlugModel,
    DeviceList,
    Group,
    SensorModel,
    SystemStatus,
)


def config(serial="CENTRAL", name="primary"):
    """Create synthetic metadata with an explicit identity and topology."""
    return AlarmConfiguration(
        alarm=AlarmModel(name=name, central=CentralPlugModel(serial=serial)),
        groups=[Group(index=1, name="Doors")],
    )


def client():
    """Keep HTTP mocked while exercising the real selection logic."""
    api = FailoverDiagralAPI(
        username="test@example.com",
        password="test-password",
        serial_id="TRANSMITTER",
        pincode="1234",
        apikey="test-key",
        secret_key="test-secret",
        session=MagicMock(closed=False),
    )
    api.expected_central_serial = "CENTRAL"
    primary, fallback = api._primary, api._fallback  # noqa: SLF001
    primary.get_configuration = AsyncMock(return_value=config())
    primary.get_system_status = AsyncMock(return_value=SystemStatus("off", []))
    fallback.get_configuration = AsyncMock(return_value=config(name="fallback"))
    fallback.get_devices_info = AsyncMock(return_value=DeviceList())
    fallback.get_system_status = AsyncMock(return_value=SystemStatus("group", [1]))
    return api, primary, fallback


async def test_healthy_primary_does_not_open_topaze_and_preserves_session():
    """A primary snapshot needs no alternate session and respects HTTP ownership."""
    api, primary, fallback = client()
    session = api.session
    assert api.fallback_api_connected is None
    assert api.primary_api_connected is None
    assert api.primary_error is None
    async with api:
        snapshot = await api.get_core_snapshot()
        assert isinstance(snapshot, CoreSnapshot)
        assert snapshot.system_status.status == "off"
        assert api.alarm_configuration is snapshot.alarm_config
        assert api.active_api == "emerald"
        assert api.uses_topaze is False
        assert api.fallback_api_connected is False
        assert api.primary_api_connected is True
        assert api.primary_error is None
        assert primary.session is session
        assert fallback.session is session
    fallback.get_configuration.assert_not_awaited()
    session.close.assert_not_called()


@pytest.mark.parametrize(
    "failure", [ClientError("network"), ServerError("server", 500), TimeoutError()]
)
async def test_transient_primary_failure_uses_complete_fallback_snapshot(failure):
    """Transport errors switch only the complete core read, not individual fields."""
    api, primary, fallback = client()
    primary.get_configuration.side_effect = failure
    snapshot = await api.get_core_snapshot()
    assert snapshot.alarm_config.alarm.name == "fallback"
    assert snapshot.system_status.status == "group"
    assert api.uses_topaze is True
    assert api.fallback_api_connected is True
    assert api.primary_api_connected is False
    assert api.primary_error == type(failure).__name__
    assert fallback.expected_central_serial == "CENTRAL"
    primary.get_system_status.assert_not_awaited()


async def test_status_failure_does_not_publish_partial_primary_metadata():
    """A successful config response cannot commit data before status succeeds."""
    api, primary, fallback = client()
    original = await api.get_core_snapshot()
    primary.get_configuration.return_value = config(name="unpublished")
    primary.get_system_status.side_effect = ClientError("state unavailable")
    fallback.get_configuration.side_effect = ClientError("also unavailable")
    with pytest.raises(ClientError, match="also unavailable"):
        await api.get_core_snapshot()
    assert api.alarm_configuration is original.alarm_config
    assert api.fallback_api_connected is False
    assert api.active_api == "topaze"
    assert api.primary_api_connected is False
    assert api.primary_error == "ClientError"


async def test_primary_deadline_switches_to_fallback(monkeypatch):
    """A stalled primary read cannot prevent alternate reads indefinitely."""
    api, primary, _ = client()
    monkeypatch.setattr("pydiagral.failover_api.FAILOVER_PRIMARY_TIMEOUT", 0.01)

    async def blocked():
        await asyncio.Event().wait()

    primary.get_configuration.side_effect = blocked
    await api.get_core_snapshot()
    assert api.uses_topaze is True


async def test_fallback_deadline_raises_sdk_error(monkeypatch):
    """A stalled alternate service exposes a library error and disconnected state."""
    api, primary, fallback = client()
    primary.get_configuration.side_effect = ClientError("primary down")
    monkeypatch.setattr("pydiagral.failover_api.FAILOVER_TOPAZE_TIMEOUT", 0.01)

    async def blocked():
        await asyncio.Event().wait()

    fallback.get_configuration.side_effect = blocked
    with pytest.raises(ClientError, match="snapshot timed out"):
        await api.get_core_snapshot()
    assert api.fallback_api_connected is False


@pytest.mark.parametrize(
    "failure",
    [
        AuthenticationError("auth"),
        PinCodeError("pin"),
        ConfigurationError("configuration"),
        ValidationError("invalid"),
    ],
)
async def test_nontransient_primary_failure_never_uses_fallback(failure):
    """Invalid credentials and malformed results need attention, not silent masking."""
    api, primary, fallback = client()
    primary.get_configuration.side_effect = failure
    with pytest.raises(type(failure)):
        await api.get_core_snapshot()
    assert api.primary_api_connected is False
    assert api.primary_error == type(failure).__name__
    fallback.get_configuration.assert_not_awaited()


async def test_recovery_requires_new_valid_primary_snapshot_and_stops_topaze():
    """Recovery is proved by fresh primary state, with no further Topaze operations."""
    api, primary, fallback = client()
    primary.get_system_status.side_effect = ClientError("primary down")
    await api.get_core_snapshot()
    assert api.uses_topaze is True
    fallback.get_configuration.reset_mock()
    fallback.get_system_status.reset_mock()
    primary.get_system_status.side_effect = None
    primary.get_system_status.return_value = SystemStatus("presence", [1])
    primary.get_configuration.return_value = config(name="recovered")
    snapshot = await api.get_core_snapshot()
    assert snapshot.alarm_config.alarm.name == "recovered"
    assert snapshot.system_status.status == "presence"
    assert api.active_api == "emerald"
    assert api.fallback_api_connected is False
    assert api.primary_api_connected is True
    assert api.primary_error is None
    fallback.get_configuration.assert_not_awaited()
    fallback.get_system_status.assert_not_awaited()


@pytest.mark.parametrize("method", ["start_system", "stop_system", "presence"])
@pytest.mark.parametrize("backend", ["emerald", "topaze"])
async def test_ambiguous_command_is_sent_once_and_never_replayed(method, backend):
    """A lost POST response cannot trigger another POST on either service."""
    api, primary, fallback = client()
    if backend == "topaze":
        primary.get_configuration.side_effect = ServerError("primary down", 503)
    primary_command = AsyncMock(side_effect=ClientError("lost response"))
    fallback_command = AsyncMock(side_effect=ClientError("lost response"))
    setattr(primary, method, primary_command)
    setattr(fallback, method, fallback_command)
    with pytest.raises(ClientError, match="lost response"):
        await getattr(api, method)()
    assert primary_command.await_count + fallback_command.await_count == 1
    assert api.active_api == backend
    assert api.fallback_api_connected is False


async def test_command_and_recovery_cannot_overlap():
    """A pending command keeps its selected backend until it completes."""
    api, primary, fallback = client()
    primary.get_configuration.side_effect = ClientError("primary down")
    command_started, command_done = asyncio.Event(), asyncio.Event()

    async def command():
        command_started.set()
        await command_done.wait()
        return SystemStatus("off", [])

    fallback.stop_system = AsyncMock(side_effect=command)
    command_task = asyncio.create_task(api.stop_system())
    await command_started.wait()
    primary.get_configuration.side_effect = None
    poll_task = asyncio.create_task(api.get_core_snapshot())
    await asyncio.sleep(0)
    assert not poll_task.done()
    assert api.active_api == "topaze"
    command_done.set()
    await command_task
    await poll_task
    assert api.active_api == "emerald"
    fallback.stop_system.assert_awaited_once()


async def test_cancelled_fallback_does_not_lock_future_recovery():
    """Cancellation leaves no selected operation holding the failover lock."""
    api, primary, fallback = client()
    primary.get_configuration.side_effect = ClientError("primary down")
    started = asyncio.Event()

    async def blocked():
        started.set()
        await asyncio.Event().wait()

    fallback.get_system_status.side_effect = blocked
    task = asyncio.create_task(api.get_core_snapshot())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert api.fallback_api_connected is False
    primary.get_configuration.side_effect = None
    await api.get_core_snapshot()
    assert api.active_api == "emerald"


async def test_compatibility_read_methods_and_shapes():
    """Existing consumers can read configuration, labels and fresh status normally."""
    api, primary, _ = client()
    first_devices = await api.get_devices_info()
    assert await api.get_devices_info() is first_devices
    await api.get_configuration()
    await api.get_system_status()
    assert primary.get_configuration.await_count == 3
    assert api.response_shapes() == {}


async def test_snapshot_labels_and_model_serialization():
    """Camera names and sensor labels survive a typed snapshot round trip."""
    api, primary, _ = client()
    configuration = config()
    configuration.sensors = [SensorModel(index=1, label="Window")]
    configuration.cameras = [Cameras(index=2, name="Camera")]
    primary.get_configuration.return_value = configuration
    snapshot = await api.get_core_snapshot()
    restored = CoreSnapshot.from_dict(snapshot.to_dict())
    assert restored.alarm_config.alarm.central.serial == "CENTRAL"
    assert restored.devices_infos.cameras[0].label == "Camera"
    assert restored.devices_infos.sensors[0].label == "Window"
    assert restored.system_status.status == "off"


@pytest.mark.parametrize(
    ("configuration", "status", "error"),
    [
        (AlarmConfiguration(), SystemStatus("off", []), ValidationError),
        (config(serial="OTHER"), SystemStatus("off", []), ConfigurationError),
        (
            AlarmConfiguration(alarm=config().alarm, groups=[]),
            SystemStatus("off", []),
            ValidationError,
        ),
        (
            AlarmConfiguration(
                alarm=config().alarm, groups=[Group(index=1), Group(index=1)]
            ),
            SystemStatus("off", []),
            ValidationError,
        ),
        (config(), SystemStatus("unknown", []), ValidationError),
        (config(), SystemStatus("off", [1]), ValidationError),
        (config(), SystemStatus("group", []), ValidationError),
        (config(), SystemStatus("group", [2]), ValidationError),
    ],
)
async def test_invalid_primary_snapshot_never_commits_or_fails_over(
    configuration, status, error
):
    """Recovery cannot validate the wrong central or inconsistent state."""
    api, primary, fallback = client()
    primary.get_configuration.return_value = configuration
    primary.get_system_status.return_value = status
    with pytest.raises(error):
        await api.get_core_snapshot()
    assert api.alarm_configuration is None
    fallback.get_configuration.assert_not_awaited()
