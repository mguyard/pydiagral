"""Optional emergency client using Topaze for core reads and system commands."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
import json
import logging
import time
from typing import Any
from uuid import uuid4

from pydiagral.api import DiagralAPI
from pydiagral.exceptions import (
    AuthenticationError,
    ClientError,
    ConfigurationError,
    DiagralAPIError,
    ServerError,
    ValidationError,
)
from pydiagral.models import AlarmConfiguration, DeviceInfos, DeviceList, SystemStatus

from .constants import (
    STATUS_GROUP,
    STATUS_OFF,
    STATUS_PRESENCE,
    STATUS_TEMPO_GROUP,
    TOPAZE_BASE_URL,
    TOPAZE_CLEANUP_TIMEOUT,
    TOPAZE_CONFIGURATION_TTL,
    TOPAZE_HEADERS,
    TOPAZE_INVENTORY_POLL_INTERVAL,
    TOPAZE_INVENTORY_TIMEOUT,
    TOPAZE_REQUEST_TIMEOUT,
)
from .topaze_commands import plan_command
from .topaze_models import build_configuration, normalize_status

_LOGGER = logging.getLogger(__name__)


@dataclass
class _Session:
    """Credentials remain inside one owned connection's lifetime."""

    token: str
    ttm: str
    config: dict[str, Any]
    connected: dict[str, Any]


class TopazeDiagralAPI(DiagralAPI):
    """Opt in to the Topaze service without replacing a caller-owned HTTP session.

    Anomalies, webhooks and group commands retain the SDK's Emerald behavior.
    Whole-system commands are dispatched once to Topaze, never replayed.
    This client does not automatically switch services when a request fails.
    ``expected_central_serial`` can pin the central identity across reloads.
    """

    uses_topaze = True

    def __init__(self, **kwargs: Any) -> None:
        """Accept the keyword arguments of :class:`DiagralAPI`."""
        super().__init__(**kwargs)
        if self.vendor != "DIAGRAL":
            raise ConfigurationError("Topaze supports the Diagral vendor only")
        self._topaze_password = kwargs["password"]
        self._topaze_pin = kwargs.get("pincode")
        self._topaze_lock = asyncio.Lock()
        self._configuration_read_at = 0.0
        self.expected_central_serial: str | None = None
        self._cleanup_tasks: set[asyncio.Task] = set()

    async def _topaze_call(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        token: str | None = None,
        timeout: float = TOPAZE_REQUEST_TIMEOUT,
    ) -> dict[str, Any]:
        """Reuse SDK HTTP handling with a dedicated service URL and redacted logs."""
        headers = dict(TOPAZE_HEADERS)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        kwargs: dict[str, Any] = {}
        if payload is not None:
            kwargs["json"] = payload
        body, _ = await super()._request(
            method,
            endpoint,
            base_url=TOPAZE_BASE_URL,
            versioned=False,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
        return body

    async def _close_owned_session(
        self, token: str, system: dict[str, Any] | None, ttm: str | None
    ) -> None:
        """Never discover or disconnect a session belonging to the mobile app."""
        operations = []
        if ttm and system:
            operations.append(
                (
                    "authenticate/disconnect",
                    {
                        "systemId": str(system["id"]),
                        "ttmSessionId": ttm,
                    },
                )
            )
        operations.append(("authenticate/logout", {"systemId": "null"}))
        for endpoint, payload in operations:
            try:
                response = await self._topaze_call(
                    "POST",
                    endpoint,
                    payload=payload,
                    token=token,
                    timeout=TOPAZE_CLEANUP_TIMEOUT,
                )
                if response.get("status") != "OK":
                    _LOGGER.warning(
                        "Topaze session cleanup failed (unconfirmed closure)"
                    )
            except (DiagralAPIError, TimeoutError) as err:
                _LOGGER.warning(
                    "Topaze session cleanup failed (%s)", type(err).__name__
                )

    @asynccontextmanager
    async def _topaze_session(self) -> AsyncIterator[_Session]:
        """Serialize short account/TTM sessions and release them on cancellation."""
        async with self._topaze_lock:
            token = ttm = None
            system = None
            try:
                login = await self._topaze_call(
                    "POST",
                    "authenticate/login",
                    payload={
                        "username": self.username,
                        "password": self._topaze_password,
                    },
                )
                token = login.get("sessionId")
                if not isinstance(token, str) or not token:
                    token = None
                    raise AuthenticationError("Topaze login did not return a session")
                systems = await self._topaze_call(
                    "POST", "configuration/getSystems", payload={}, token=token
                )
                selected = None
                candidates = systems.get("systems")
                if not isinstance(candidates, list):
                    raise ValidationError("Invalid Topaze systems list")
                for candidate in candidates:
                    if (
                        not isinstance(candidate, dict)
                        or not {"id", "role"} <= candidate.keys()
                    ):
                        raise ValidationError("Invalid Topaze system entry")
                    config = await self._topaze_call(
                        "POST",
                        "configuration/getConfiguration",
                        payload={
                            "systemId": candidate["id"],
                            "role": candidate["role"],
                        },
                        token=token,
                    )
                    if config.get("transmitterId") == self.serial_id:
                        selected = {
                            **config,
                            "id": candidate["id"],
                            "role": candidate["role"],
                        }
                        break
                if selected is None:
                    raise ConfigurationError(
                        "Topaze did not find the configured transmitter"
                    )
                system = selected
                central = system.get("centralId")
                if not isinstance(central, str) or not central:
                    raise ValidationError("Topaze did not identify the central")
                if (
                    self.expected_central_serial
                    and central != self.expected_central_serial
                ):
                    raise ConfigurationError(
                        "Topaze central differs from the expected device"
                    )
                connected = await self._topaze_call(
                    "POST",
                    "authenticate/connect",
                    payload={
                        "masterCode": self._topaze_pin,
                        "transmitterId": self.serial_id,
                        "systemId": system["id"],
                        "role": system["role"],
                    },
                    token=token,
                )
                ttm = connected.get("ttmSessionId")
                if not isinstance(ttm, str) or not ttm:
                    ttm = None
                    raise DiagralAPIError("Topaze could not open its own session")
                yield _Session(token, ttm, system, connected)
            finally:
                if token:
                    cleanup = asyncio.create_task(
                        self._close_owned_session(token, system, ttm)
                    )
                    self._cleanup_tasks.add(cleanup)
                    cleanup.add_done_callback(self._cleanup_tasks.discard)
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        await asyncio.shield(cleanup)
                        raise

    async def _read_inventory(self, context: _Session) -> dict[str, Any]:
        """Translate an inventory deadline into the library's error hierarchy."""
        try:
            return await self._poll_inventory(context)
        except TimeoutError:
            raise ClientError("Topaze inventory read timed out") from None

    async def _poll_inventory(self, context: _Session) -> dict[str, Any]:
        """Read one inventory job, allowing its empty HTTP 200 acknowledgement."""
        versions = context.connected.get("versions")
        if (
            not isinstance(versions, dict)
            or not isinstance(versions.get("box"), str)
            or not versions["box"]
        ):
            raise ValidationError("Topaze did not provide the box version")
        endpoint = f"configuration/v2/getDevicesMultizone/{uuid4()}"
        payload = {
            "systemId": str(context.config["id"]),
            "centralId": context.config["centralId"],
            "transmitterId": context.config["transmitterId"],
            "ttmSessionId": context.ttm,
            "isVideoOptional": "true",
            "isScenariosZoneOptional": "true",
            "boxVersion": versions["box"],
        }
        async with asyncio.timeout(TOPAZE_INVENTORY_TIMEOUT):
            try:
                await self._topaze_call(
                    "POST", endpoint, payload=payload, token=context.token
                )
            except ValidationError as err:
                if err.status_code != HTTPStatus.OK:
                    raise
            while True:
                await asyncio.sleep(TOPAZE_INVENTORY_POLL_INTERVAL)
                result = await self._topaze_call("GET", endpoint, token=context.token)
                if result.get("status") == "request_status_done":
                    response = result.get("response")
                    try:
                        decoded = (
                            json.loads(response)
                            if isinstance(response, str)
                            else response
                        )
                    except ValueError:
                        raise ValidationError("Invalid Topaze inventory JSON") from None
                    if not isinstance(decoded, dict):
                        raise ValidationError("Invalid Topaze inventory object")
                    return decoded
                if result.get("status") not in (
                    "request_status_pending",
                    "request_status_in_progress",
                    "request_status_waiting",
                ):
                    raise DiagralAPIError("Topaze inventory did not complete")

    async def get_configuration(self) -> AlarmConfiguration:
        """Refresh metadata hourly; normal status reads need no full inventory."""
        if (
            self.alarm_configuration
            and time.monotonic() - self._configuration_read_at
            < TOPAZE_CONFIGURATION_TTL
        ):
            return self.alarm_configuration
        try:
            async with self._topaze_session() as context:
                inventory = await self._read_inventory(context)
                config = build_configuration(
                    inventory, context.config, context.connected
                )
        except (ClientError, ServerError, TimeoutError):
            if self.alarm_configuration is None:
                raise
            _LOGGER.warning(
                "Topaze metadata refresh failed; retaining validated metadata"
            )
            return self.alarm_configuration
        self.alarm_configuration = config
        self._configuration_read_at = time.monotonic()
        return config

    async def get_devices_info(self) -> DeviceList:
        """Keep the existing anomaly sensor's label lookup for every category."""
        config = self.alarm_configuration or await self.get_configuration()
        devices = {}
        for category in ("cameras", "commands", "sensors", "sirens", "transmitters"):
            devices[category] = [
                DeviceInfos(
                    index=item.index,
                    label=(
                        getattr(item, "label", None)
                        or getattr(item, "name", None)
                        or ""
                    ),
                )
                for item in getattr(config, category) or []
            ]
        return DeviceList(**devices)

    async def get_system_status(self) -> SystemStatus:
        """Publish only a fresh, validated state from the actual central."""
        config = self.alarm_configuration or await self.get_configuration()
        async with self._topaze_session() as context:
            response = await self._topaze_call(
                "POST",
                "status/getSystemState",
                payload={
                    "centralId": context.config["centralId"],
                    "ttmSessionId": context.ttm,
                },
                token=context.token,
            )
            return normalize_status(response, config)

    async def _topaze_command(self, action: str) -> SystemStatus:
        """Dispatch once, then require a real state read instead of optimistic UI."""
        config = self.alarm_configuration or await self.get_configuration()
        async with self._topaze_session() as context:
            status = normalize_status(context.connected, config)
            payload = plan_command(action, config, status)
            payload["ttmSessionId"] = context.ttm
            result = await self._topaze_call(
                "POST", "action/stateCommand", payload=payload, token=context.token
            )
            if result.get("commandStatus") != "CMD_OK":
                raise DiagralAPIError("Topaze command was not confirmed")
            response = await self._topaze_call(
                "POST",
                "status/getSystemState",
                payload={
                    "centralId": context.config["centralId"],
                    "ttmSessionId": context.ttm,
                },
                token=context.token,
            )
            observed = normalize_status(response, config)
            expected = {
                "start": (STATUS_GROUP, STATUS_TEMPO_GROUP),
                "stop": (STATUS_OFF,),
                "presence": (STATUS_PRESENCE,),
            }[action]
            if observed.status not in expected:
                raise DiagralAPIError("Topaze did not confirm the requested state")
            return observed

    async def start_system(self) -> SystemStatus:
        """Arm using one Topaze command."""
        return await self._topaze_command("start")

    async def stop_system(self) -> SystemStatus:
        """Disarm using one Topaze command."""
        return await self._topaze_command("stop")

    async def presence(self) -> SystemStatus:
        """Arm presence mode using one Topaze command."""
        return await self._topaze_command("presence")
