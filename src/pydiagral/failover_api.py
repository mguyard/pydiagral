"""Recover core reads automatically through Topaze during Emerald outages."""

import asyncio
from typing import Any, Self

from .api import DiagralAPI
from .constants import (
    API_EMERALD,
    API_TOPAZE,
    FAILOVER_PRIMARY_TIMEOUT,
    FAILOVER_TOPAZE_TIMEOUT,
    STATUS_GROUP,
    STATUS_OFF,
    STATUS_PRESENCE,
    STATUS_TEMPO_GROUP,
)
from .exceptions import (
    ClientError,
    ConfigurationError,
    DiagralAPIError,
    ServerError,
    ValidationError,
)
from .models import (
    AlarmConfiguration,
    CoreSnapshot,
    DeviceInfos,
    DeviceList,
    SystemStatus,
)
from .topaze_api import TopazeDiagralAPI


class FailoverDiagralAPI(DiagralAPI):
    """Prefer Emerald and use Topaze only after transient core-read failures.

    Every snapshot tests authenticated Emerald configuration and live state again.
    Recovery requires a complete matching snapshot, never just a successful ping.
    Authentication and validation failures are not hidden by switching services.
    Whole-system commands are sent once to the backend selected by a read-only
    preflight. An uncertain command response never causes a replay.

    Attributes:
        active_api (str): Backend selected for core reads, ``emerald`` or ``topaze``.
        fallback_api_connected (bool | None): True after a successful Topaze read,
            False when idle or failed, None before any core read.
        primary_api_connected (bool | None): True only after a valid authenticated
            primary snapshot, False after failure, None before any core read.
        primary_error (str | None): Exception category of the latest failed primary
            probe, without a server message or credential; cleared on recovery.
        expected_central_serial (str | None): Optional existing central identity.

    """

    supports_failover = True

    def __init__(self, **kwargs: Any) -> None:
        """Accept the keyword arguments of `DiagralAPI`; share its HTTP session."""
        super().__init__(**kwargs)
        self._primary = DiagralAPI(**kwargs)
        self._fallback = TopazeDiagralAPI(**kwargs)
        self._selection_lock = asyncio.Lock()
        self._snapshot: CoreSnapshot | None = None
        self._central_serial: str | None = None
        self.expected_central_serial: str | None = None
        self.active_api = API_EMERALD
        self.fallback_api_connected: bool | None = None
        self.primary_api_connected: bool | None = None
        self.primary_error: str | None = None

    async def __aenter__(self) -> Self:
        """Open one HTTP session and lend it to both protocol clients."""
        await super().__aenter__()
        self._share_session()
        return self

    @property
    def uses_topaze(self) -> bool:
        """Whether core operations currently select the alternate service."""
        return self.active_api == API_TOPAZE

    def response_shapes(self) -> dict[str, Any]:
        """Keep primary read shapes alongside inherited secondary diagnostics."""
        return super().response_shapes() | self._primary.response_shapes()

    def _share_session(self) -> None:
        """Child clients borrow one session; only the parent may own its lifetime."""
        self._primary.session = self.session
        self._fallback.session = self.session

    @staticmethod
    def _devices(config: AlarmConfiguration) -> DeviceList:
        """Read device labels without changing either protocol client's cache."""
        values = {}
        for category in ("cameras", "commands", "sensors", "sirens", "transmitters"):
            values[category] = [
                DeviceInfos(
                    index=item.index,
                    label=getattr(item, "label", None)
                    or getattr(item, "name", None)
                    or "",
                )
                for item in getattr(config, category) or []
            ]
        return DeviceList(**values)

    def _validate(self, snapshot: CoreSnapshot) -> str:
        """Validate identity and live groups before publishing or choosing a backend."""
        config, status = snapshot.alarm_config, snapshot.system_status
        central = config.alarm.central if config.alarm else None
        serial = central.serial if central else None
        if not isinstance(serial, str) or not serial:
            raise ValidationError("Core configuration did not identify the central")
        if any(
            expected and serial != expected
            for expected in (self.expected_central_serial, self._central_serial)
        ):
            raise ConfigurationError(
                "Core configuration differs from the expected central"
            )
        groups = [group.index for group in config.groups or []]
        if not groups or any(type(group) is not int or group < 1 for group in groups):
            raise ValidationError("Core configuration did not provide valid groups")
        if len(set(groups)) != len(groups):
            raise ValidationError("Core configuration contains duplicate groups")
        state = status.status.lower() if isinstance(status.status, str) else None
        if state not in (STATUS_OFF, STATUS_GROUP, STATUS_TEMPO_GROUP, STATUS_PRESENCE):
            raise ValidationError("Core status is not a supported alarm state")
        active = status.activated_groups
        if (
            not isinstance(active, list)
            or any(type(group) is not int for group in active)
            or len(set(active)) != len(active)
            or not set(active) <= set(groups)
            or (state == STATUS_OFF and active)
            or (state == STATUS_GROUP and not active)
        ):
            raise ValidationError("Core status contains inconsistent active groups")
        return serial

    async def _primary_snapshot(self) -> CoreSnapshot:
        """Read one complete primary snapshot without modifying published metadata."""
        try:
            async with asyncio.timeout(FAILOVER_PRIMARY_TIMEOUT):
                config = await self._primary.get_configuration()
                status = await self._primary.get_system_status()
                snapshot = CoreSnapshot(config, self._devices(config), status)
                self._validate(snapshot)
        except (DiagralAPIError, TimeoutError, asyncio.CancelledError) as err:
            self.primary_api_connected = False
            self.primary_error = type(err).__name__
            raise
        self.primary_api_connected = True
        self.primary_error = None
        return snapshot

    async def _fallback_snapshot(self) -> CoreSnapshot:
        """Read validated alternate metadata and fresh status under a total deadline."""
        self._fallback.expected_central_serial = (
            self.expected_central_serial or self._central_serial
        )
        try:
            async with asyncio.timeout(FAILOVER_TOPAZE_TIMEOUT):
                config = await self._fallback.get_configuration()
                devices = await self._fallback.get_devices_info()
                status = await self._fallback.get_system_status()
                snapshot = CoreSnapshot(config, devices, status)
                self._validate(snapshot)
                return snapshot
        except TimeoutError:
            raise ClientError("Topaze core snapshot timed out") from None

    async def _select_snapshot(self) -> CoreSnapshot:
        """Publish exactly one complete backend snapshot, keeping failed reads private."""
        self._share_session()
        self.fallback_api_connected = False
        try:
            snapshot = await self._primary_snapshot()
        except (ClientError, ServerError, TimeoutError):
            self.active_api = API_TOPAZE
            snapshot = await self._fallback_snapshot()
            self.fallback_api_connected = True
        else:
            self.active_api = API_EMERALD
        self._central_serial = self._validate(snapshot)
        self._snapshot = snapshot
        self.alarm_configuration = snapshot.alarm_config
        return snapshot

    async def get_core_snapshot(self) -> CoreSnapshot:
        """Read fresh core data, automatically failing over and recovering.

        Returns:
            CoreSnapshot: A complete snapshot from the selected backend.

        Raises:
            DiagralAPIError: If authentication, validation, or both services fail.

        """
        async with self._selection_lock:
            return await self._select_snapshot()

    async def get_configuration(self) -> AlarmConfiguration:
        """Refresh the selected backend and return its validated configuration."""
        return (await self.get_core_snapshot()).alarm_config

    async def get_devices_info(self) -> DeviceList:
        """Return names from the most recent validated configuration."""
        snapshot = self._snapshot or await self.get_core_snapshot()
        return snapshot.devices_infos

    async def get_system_status(self) -> SystemStatus:
        """Read fresh status, including read-only verification after an uncertain command."""
        return (await self.get_core_snapshot()).system_status

    async def _command(self, method: str) -> SystemStatus:
        """Select with reads, then send exactly one command to that backend."""
        async with self._selection_lock:
            await self._select_snapshot()
            backend = self._fallback if self.uses_topaze else self._primary
            try:
                return await getattr(backend, method)()
            except (DiagralAPIError, asyncio.CancelledError):
                if self.uses_topaze:
                    self.fallback_api_connected = False
                raise

    async def start_system(self) -> SystemStatus:
        """Arm once on the backend chosen by a read-only preflight."""
        return await self._command("start_system")

    async def stop_system(self) -> SystemStatus:
        """Disarm once on the backend chosen by a read-only preflight."""
        return await self._command("stop_system")

    async def presence(self) -> SystemStatus:
        """Arm presence mode once on the backend chosen by a read-only preflight."""
        return await self._command("presence")
