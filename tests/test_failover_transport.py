"""Exercise recovery through real HTTP on a synthetic loopback-only cloud."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
import pytest

from pydiagral import FailoverDiagralAPI
import pydiagral.api as emerald_module
from pydiagral.exceptions import AuthenticationError, ConfigurationError
import pydiagral.failover_api as failover_module
import pydiagral.topaze_api as topaze_module

_TRANSMITTER = "SYNTHETIC-BOX"
_CENTRAL = "SYNTHETIC-CENTRAL"


def _emerald_configuration() -> dict[str, Any]:
    """Different labels reveal a snapshot accidentally mixed across backends."""
    return {
        "alarm": {
            "name": "Emerald example",
            "central": {"serial": _CENTRAL, "firmwares": {"CENTRAL": "1.0"}},
            "box": {"serial": _TRANSMITTER},
        },
        "groups": [{"index": 1, "name": "Emerald group", "outputDelay": 45}],
        "sensors": [{"index": 1, "label": "Emerald sensor"}],
    }


def _topaze_inventory() -> dict[str, Any]:
    """Provide only synthetic equipment and a non-default delay."""
    return {
        "centralLearningZone": {
            "centralInformation": {"radioId": "RADIO-EXAMPLE"},
            "groupNames": {"1": "Topaze group"},
            "sensors": [{"index": 1, "customLabel": "Topaze sensor"}],
        },
        "centralSettingsZone": {
            "nbGroups": 1,
            "outputDelays": {"1": 45},
        },
    }


@dataclass
class _Cloud:
    """Keep session ownership observable without touching an actual alarm."""

    failure: str | None = None
    central: str = _CENTRAL
    release: asyncio.Event = field(default_factory=asyncio.Event)
    calls: list[tuple[str, str]] = field(default_factory=list)
    tokens: set[str] = field(default_factory=set)
    ttms: set[str] = field(default_factory=set)
    logins: int = 0

    async def handle(self, request: web.Request) -> web.Response:
        """Serve the two protocols and reject every unrecognized endpoint."""
        self.calls.append((request.method, request.path))
        if request.path == "/emerald/":
            return web.json_response({"status": "OK"})
        if request.path.startswith("/emerald/"):
            return await self.emerald(request)
        return await self.topaze(request)

    async def emerald(self, request: web.Request) -> web.Response:
        """Fail authenticated status after configuration has already succeeded."""
        assert request.method == "GET"
        assert request.headers["X-APIKEY"] == "synthetic-key"
        assert request.headers["X-HMAC"]
        if request.path.endswith("/configurations"):
            return web.json_response(_emerald_configuration())
        assert request.path.endswith("/status")
        assert request.headers["X-PIN-CODE"] == "1234"
        if self.failure == "timeout":
            await self.release.wait()
        if self.failure == "server":
            return web.json_response({"detail": "Synthetic outage"}, status=500)
        if self.failure == "authentication":
            return web.json_response({"detail": "Synthetic rejection"}, status=401)
        return web.json_response({"status": "OFF", "activated_groups": []})

    async def topaze(self, request: web.Request) -> web.Response:
        """Accept owned read sessions only; no alarm command is implemented."""
        assert request.path.startswith("/topaze/")
        endpoint = request.path.removeprefix("/topaze/")
        payload = await request.json() if request.method == "POST" else {}
        if endpoint == "authenticate/login":
            assert payload == {
                "username": "test@example.com",
                "password": "synthetic-password",
            }
            self.logins += 1
            token = f"synthetic-token-{self.logins}"
            self.tokens.add(token)
            return web.json_response({"sessionId": token})
        token = request.headers["Authorization"].removeprefix("Bearer ")
        assert token in self.tokens
        if endpoint == "configuration/getSystems":
            return web.json_response({"systems": [{"id": 1, "role": 1}]})
        if endpoint == "configuration/getConfiguration":
            return web.json_response(
                {
                    "name": "Topaze example",
                    "transmitterId": _TRANSMITTER,
                    "centralId": self.central,
                }
            )
        if endpoint == "authenticate/connect":
            assert payload["masterCode"] == "1234"
            ttm = f"synthetic-ttm-{self.logins}"
            self.ttms.add(ttm)
            return web.json_response(
                {
                    "ttmSessionId": ttm,
                    "versions": {"box": "1.0"},
                    "systemState": "off",
                    "groups": [],
                }
            )
        if endpoint.startswith("configuration/v2/getDevicesMultizone/"):
            if request.method == "POST":
                assert payload["ttmSessionId"] in self.ttms
                return web.Response(status=200)
            return web.json_response(
                {"status": "request_status_done", "response": _topaze_inventory()}
            )
        if endpoint == "status/getSystemState":
            assert payload["ttmSessionId"] in self.ttms
            return web.json_response({"systemState": "off", "groups": []})
        if endpoint == "authenticate/disconnect":
            self.ttms.remove(payload["ttmSessionId"])
            return web.json_response({"status": "OK"})
        assert endpoint == "authenticate/logout"
        self.tokens.remove(token)
        return web.json_response({"status": "OK"})


@pytest.fixture
async def local_client(monkeypatch):
    """Redirect both service URLs to loopback before constructing any client."""
    cloud = _Cloud()
    application = web.Application()
    application.router.add_route("*", "/{path:.*}", cloud.handle)
    async with TestServer(application, host="127.0.0.1") as server:
        monkeypatch.setattr(
            emerald_module, "BASE_URL", str(server.make_url("/emerald"))
        )
        monkeypatch.setattr(
            topaze_module, "TOPAZE_BASE_URL", str(server.make_url("/topaze"))
        )
        monkeypatch.setattr(topaze_module, "TOPAZE_INVENTORY_POLL_INTERVAL", 0.001)
        monkeypatch.setattr(failover_module, "FAILOVER_PRIMARY_TIMEOUT", 2)
        async with ClientSession() as session:
            api = FailoverDiagralAPI(
                username="test@example.com",
                password="synthetic-password",
                serial_id=_TRANSMITTER,
                apikey="synthetic-key",
                secret_key="synthetic-secret",
                pincode="1234",
                session=session,
            )
            api.expected_central_serial = _CENTRAL
            try:
                yield api, cloud
            finally:
                cloud.release.set()


@pytest.mark.parametrize(
    ("failure", "outage_deadline"),
    [("server", 2), ("timeout", 0.2)],
    ids=["http-500", "deadline"],
)
async def test_authenticated_http_failure_recovers_atomically(
    local_client, failure, outage_deadline, monkeypatch
):
    """Only a fresh authenticated snapshot restores the primary backend."""
    api, cloud = local_client
    initial = await api.get_core_snapshot()
    assert api.active_api == "emerald"
    assert initial.alarm_config.alarm.name == "Emerald example"
    assert initial.devices_infos.sensors[0].label == "Emerald sensor"

    cloud.failure = failure
    monkeypatch.setattr(failover_module, "FAILOVER_PRIMARY_TIMEOUT", outage_deadline)
    emergency = await api.get_core_snapshot()
    assert api.active_api == "topaze"
    assert api.uses_topaze is True
    assert api.fallback_api_connected is True
    assert emergency.alarm_config.alarm.name == "Topaze example"
    assert emergency.devices_infos.sensors[0].label == "Topaze sensor"
    assert emergency.alarm_config.groups[0].output_delay == 45
    assert emergency.system_status.status == "off"
    assert not cloud.tokens
    assert not cloud.ttms
    login_count = cloud.logins

    assert (await api.ping()).status == "OK"
    assert api.active_api == "topaze"
    cloud.failure = None
    cloud.release.set()
    monkeypatch.setattr(failover_module, "FAILOVER_PRIMARY_TIMEOUT", 2)
    recovered = await api.get_core_snapshot()
    assert api.active_api == "emerald"
    assert api.uses_topaze is False
    assert recovered.alarm_config.alarm.name == "Emerald example"
    assert recovered.devices_infos.sensors[0].label == "Emerald sensor"
    assert cloud.logins == login_count
    assert all("stateCommand" not in path for _, path in cloud.calls)


async def test_http_authentication_failure_never_enters_fallback(local_client):
    """Wrong credentials are actionable errors rather than a transient outage."""
    api, cloud = local_client
    cloud.failure = "authentication"
    with pytest.raises(AuthenticationError):
        await api.get_core_snapshot()
    assert cloud.logins == 0
    assert all(not path.startswith("/topaze/") for _, path in cloud.calls)


async def test_http_fallback_rejects_changed_central_and_logs_out(local_client):
    """A matching transmitter cannot substitute a different central identity."""
    api, cloud = local_client
    cloud.failure = "server"
    cloud.central = "DIFFERENT-SYNTHETIC-CENTRAL"
    with pytest.raises(ConfigurationError):
        await api.get_core_snapshot()
    assert cloud.logins == 1
    assert not cloud.tokens
    assert not cloud.ttms
    assert ("POST", "/topaze/authenticate/connect") not in cloud.calls
