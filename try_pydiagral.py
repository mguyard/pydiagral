# /// script
# requires-python = ">=3.11"
# dependencies = ["pydiagral>=2.0.0b3", "python-dotenv"]
#
# # The latest pydiagral on every run, betas included.
# [tool.uv]
# prerelease-package = { pydiagral = "allow" }
# upgrade-package = ["pydiagral"]
# ///
"""Try pydiagral against your own Diagral alarm.

Copy `.env.example` to `.env` next to this script and fill it in, then:

    uv run try_pydiagral.py                   # every read-only scenario
    uv run try_pydiagral.py status anomalies  # only these
    uv run try_pydiagral.py arm --wait 10     # arm, wait 10 s, then disarm
    uv run try_pydiagral.py --help            # every scenario and option

uv installs the latest pydiagral, betas included, in an environment of its own.
Without uv: `pip install --upgrade --pre pydiagral python-dotenv`, then run the
same commands with `python` instead of `uv run`.

Without arguments, nothing changes on the alarm or the account, apart from the
temporary API key created when `.env` holds none. The scenarios that do change
something only run when named. The output ends with a diagnostics report that
holds no value you typed and no identifier, ready to attach to an issue.
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import signal
import sys
from types import FrameType
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from dotenv import load_dotenv

from pydiagral import DiagralAPI, DiagralAPIError
from pydiagral.models import (
    Anomalies,
    SystemStatus,
    Webhook,
    WebHookNotification,
    unexpected_data,
)
from pydiagral.utils import shape

ENV_FILE = Path(__file__).with_name(".env")
ENV_PREFIX = "DIAGRAL_"
DEFAULT_WAIT = 30
DEVICE_TYPES = ("sensors", "commands", "sirens", "cameras", "transmitters")
ANOMALY_SOURCES = (
    "central",
    "sensors",
    "badges",
    "sirens",
    "cameras",
    "commands",
    "transceivers",
    "transmitters",
)
TRIGGERS = ("none", "presence", "arm")
LISTEN_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_LISTEN_FOR = 120
# An away arm notifies only once its exit delay, about 4 minutes, is over.
ARM_LISTEN_MINIMUM = 300
AFTER_DISARM = 30
REACHABLE_TIMEOUT = 120
REACHABLE_RETRY_DELAY = 5
# Codespaces forwards a port a few seconds after something listens on it.
PORT_PUBLIC_ATTEMPTS = 5
PORT_PUBLIC_DELAY = 2
PROBE_TIMEOUT = 10
MAX_NOTIFICATION_SIZE = 64 * 1024
PROBE_KEY = "try_pydiagral_probe"
# Shapes of the notifications webhook-listen receives, for the diagnostics report.
WEBHOOK_SHAPES: list[Any] = []


@dataclass(frozen=True)
class Settings:
    """The connection settings read from the environment."""

    username: str
    password: str
    serial_id: str | None
    apikey: str | None
    secret_key: str | None
    pincode: str | None
    vendor: str


@dataclass(frozen=True)
class Options:
    """What the scenarios take from the command line."""

    wait: int
    partial: int
    groups: list[int]
    trigger: str
    listen_for: int
    port: int
    public_url: str | None


@dataclass(frozen=True)
class Scenario:
    """A named step, and whether it runs when no scenario is named."""

    run: Callable[[DiagralAPI, Options], Awaitable[None]]
    help: str
    needs_serial: bool
    needs_keys: bool
    by_default: bool


class ScenarioFailed(Exception):
    """A scenario could not check what it checks; the message says why."""


SCENARIOS: dict[str, Scenario] = {}


def scenario(
    name: str,
    help_text: str,
    *,
    needs_serial: bool = True,
    needs_keys: bool = True,
    by_default: bool = True,
) -> Callable[
    [Callable[[DiagralAPI, Options], Awaitable[None]]],
    Callable[[DiagralAPI, Options], Awaitable[None]],
]:
    """Register a scenario under `name`, in definition order."""

    def register(
        func: Callable[[DiagralAPI, Options], Awaitable[None]],
    ) -> Callable[[DiagralAPI, Options], Awaitable[None]]:
        SCENARIOS[name] = Scenario(
            func, help_text, needs_serial, needs_keys, by_default
        )
        return func

    return register


def env(name: str) -> str | None:
    """Read `DIAGRAL_<name>`, an empty value counting as unset."""
    return os.getenv(ENV_PREFIX + name) or None


def load_settings() -> Settings:
    """Read the settings from `.env` and the environment, or exit."""
    load_dotenv(ENV_FILE)
    username, password = env("USERNAME"), env("PASSWORD")
    if not username or not password:
        sys.exit(
            f"{ENV_PREFIX}USERNAME and {ENV_PREFIX}PASSWORD are required: "
            f"copy .env.example to {ENV_FILE.name} and fill it in."
        )
    return Settings(
        username=username,
        password=password,
        serial_id=env("SERIAL_ID"),
        apikey=env("API_KEY"),
        secret_key=env("SECRET_KEY"),
        pincode=env("PIN_CODE"),
        vendor=env("VENDOR") or "DIAGRAL",
    )


def host_only(url: str) -> str:
    """Hide the path of a URL, which may carry a secret."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/…"


async def current_webhook(api: DiagralAPI) -> Webhook | None:
    """Return the webhook subscription, or None when there is none."""
    try:
        return await api.get_webhook()
    except DiagralAPIError as err:
        if "No subscription found for" in str(err):
            return None
        raise


async def wait_or_ctrl_c(seconds: float) -> None:
    """Wait `seconds`, or until Ctrl+C, which ends the wait instead of the run."""
    loop = asyncio.get_running_loop()
    pressed = asyncio.Event()
    previous = signal.getsignal(signal.SIGINT)

    def on_ctrl_c(signum: int, frame: FrameType | None) -> None:
        # Hand Ctrl+C back to asyncio at once: outside a wait, it quits.
        signal.signal(signal.SIGINT, previous)
        loop.call_soon_threadsafe(pressed.set)

    signal.signal(signal.SIGINT, on_ctrl_c)
    try:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(pressed.wait(), seconds)
    finally:
        signal.signal(signal.SIGINT, previous)
    if pressed.is_set():
        print("\nStopped waiting")


async def arm_then_disarm(
    api: DiagralAPI,
    label: str,
    arm: Coroutine[Any, Any, SystemStatus],
    wait: int,
) -> None:
    """Run `arm`, wait, then disarm, even when `arm` fails or Ctrl+C is pressed."""
    try:
        status = await arm
        print(f"{label}: {status.status}, active groups {status.activated_groups}")
        print(f"Disarming in {wait} s (Ctrl+C disarms now)")
        await wait_or_ctrl_c(wait)
    finally:
        try:
            print(f"Disarmed: {(await api.stop_system()).status}")
        except DiagralAPIError as err:
            print(f"!! Could not disarm, check your alarm: {err}")


def describe(notification: WebHookNotification) -> str:
    """Summarize a notification, without the serial or the user name."""
    parts = [f"{notification.alarm_type} {notification.alarm_code}"]
    if notification.alarm_description:
        parts.append(notification.alarm_description)
    if notification.group_index:
        parts.append(f"group {notification.group_index}")
    if notification.detail.device_type:
        device = f"{notification.detail.device_type} {notification.detail.device_index or ''}"
        parts.append(f"device {device.strip()}")
    if notification.user and notification.user.user_type:
        parts.append(f"by {notification.user.user_type}")
    return ", ".join(parts)


class NotificationInbox:
    """Receive notifications on a secret path, and the probe that checks the URL."""

    def __init__(self) -> None:
        """Draw the secret path and the probe value."""
        self.path = f"/{secrets.token_urlsafe(24)}"
        self.probe = secrets.token_urlsafe(16)
        self.reachable = asyncio.Event()
        self.received = 0

    async def handle(self, request: web.Request) -> web.Response:
        """Answer 200 to any JSON body, and print what it holds."""
        try:
            payload = await request.json()
        except ValueError:
            return web.Response(status=400)
        if payload == {PROBE_KEY: self.probe}:
            self.reachable.set()
            return web.Response()
        self.received += 1
        WEBHOOK_SHAPES.append(shape(payload))
        try:
            notification = WebHookNotification.from_dict(payload)
        except DiagralAPIError as err:
            print(f"!! Notification {self.received} could not be parsed: {err}")
        else:
            print(f"Notification {self.received}: {describe(notification)}")
        return web.Response()


def public_base_url(options: Options) -> str:
    """Return the public URL that reaches the listener, from Codespaces or a tunnel."""
    if options.public_url:
        return options.public_url.rstrip("/")
    name = os.getenv("CODESPACE_NAME")
    domain = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if name and domain:
        return f"https://{name}-{options.port}.{domain}"
    raise ScenarioFailed(
        "Outside Codespaces, start a tunnel to the listener and pass its URL "
        "with --public-url: see the guide."
    )


async def set_port_visibility(port: int, visibility: str) -> bool:
    """Set the visibility of a Codespaces port with the GitHub CLI."""
    gh, name = shutil.which("gh"), os.getenv("CODESPACE_NAME")
    if not gh or not name:
        return False
    process = await asyncio.create_subprocess_exec(
        gh,
        "codespace",
        "ports",
        "visibility",
        f"{port}:{visibility}",
        "--codespace",
        name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await process.wait() == 0


async def make_port_public(port: int) -> bool:
    """Make the listener's Codespaces port public, once Codespaces forwards it."""
    for _ in range(PORT_PUBLIC_ATTEMPTS):
        if await set_port_visibility(port, "public"):
            print(f"Made port {port} public")
            return True
        await asyncio.sleep(PORT_PUBLIC_DELAY)
    print(
        f"!! Could not make port {port} public: in the Ports tab, right-click "
        "it, then Port Visibility > Public. Waiting for it…"
    )
    return False


async def wait_until_reachable(url: str, inbox: NotificationInbox) -> None:
    """Post the probe to the public URL until it reaches the listener."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + REACHABLE_TIMEOUT
    async with ClientSession(timeout=ClientTimeout(total=PROBE_TIMEOUT)) as session:
        while True:
            with contextlib.suppress(ClientError, TimeoutError):
                async with session.post(url, json={PROBE_KEY: inbox.probe}):
                    pass
            if inbox.reachable.is_set():
                print(f"The listener is reachable at {host_only(url)}")
                return
            if loop.time() >= deadline:
                raise ScenarioFailed(
                    f"The listener is not reachable from {host_only(url)} after "
                    f"{REACHABLE_TIMEOUT} s: see Troubleshooting in the guide."
                )
            await asyncio.sleep(REACHABLE_RETRY_DELAY)


async def provoke_and_listen(api: DiagralAPI, options: Options) -> None:
    """Wait for notifications, after arming when a trigger is chosen."""
    if options.trigger == "none":
        print(
            f"Listening for {options.listen_for} s: arm or disarm from a keypad, "
            "a badge or the Diagral app (Ctrl+C stops listening)"
        )
        await wait_or_ctrl_c(options.listen_for)
        return
    if options.trigger == "presence":
        await arm_then_disarm(api, "Presence", api.presence(), options.listen_for)
    else:
        wait = max(options.listen_for, ARM_LISTEN_MINIMUM)
        print(f"An away arm notifies after its exit delay: listening {wait} s")
        await arm_then_disarm(api, "Armed", api.start_system(), wait)
    print(
        f"Listening {AFTER_DISARM} s more for the disarm notification "
        "(Ctrl+C stops listening)"
    )
    await wait_or_ctrl_c(AFTER_DISARM)


@scenario(
    "ping",
    "Check that the Diagral cloud answers",
    needs_serial=False,
    needs_keys=False,
)
async def ping(api: DiagralAPI, options: Options) -> None:
    """Check that the Diagral cloud answers."""
    print(f"Diagral cloud: {(await api.ping()).status}")


@scenario(
    "systems",
    "List the systems of the account, to find your serial ID",
    needs_serial=False,
    needs_keys=False,
)
async def systems(api: DiagralAPI, options: Options) -> None:
    """List the systems of the account."""
    for system in await api.get_systems():
        print(f"System {system.serial_id}: {len(system.api_keys)} API key(s)")


@scenario("configuration", "Show the alarm name, its groups and its device count")
async def configuration(api: DiagralAPI, options: Options) -> None:
    """Show the alarm name, its groups and how many devices it has."""
    config = await api.get_configuration()
    print(f"Alarm: {await api.get_alarm_name() or '(no name)'}")
    for group in config.groups or []:
        print(f"  Group {group.index}: {group.name}")
    for device_type in (*DEVICE_TYPES, "transceivers"):
        print(f"  {device_type}: {len(getattr(config, device_type) or [])}")


@scenario("devices", "List the devices of the alarm, by type")
async def devices(api: DiagralAPI, options: Options) -> None:
    """List the devices of the alarm."""
    device_list = await api.get_devices_info()
    for device_type in DEVICE_TYPES:
        for device in getattr(device_list, device_type) or []:
            print(f"  {device_type} {device.index}: {device.label}")


@scenario("details", "Show the box model, firmware and mode (needs the PIN code)")
async def details(api: DiagralAPI, options: Options) -> None:
    """Show the box model, firmware and mode."""
    system = await api.get_system_details()
    print(
        f"Box {system.device_type}, firmware {system.firmware_version}, "
        f"mode {system.mode}"
    )


@scenario("status", "Show whether the alarm is armed (needs the PIN code)")
async def status(api: DiagralAPI, options: Options) -> None:
    """Show the alarm status and its active groups."""
    system_status = await api.get_system_status()
    print(
        f"Status: {system_status.status}, "
        f"active groups {system_status.activated_groups}"
    )


@scenario("anomalies", "List the current anomalies")
async def anomalies(api: DiagralAPI, options: Options) -> None:
    """List the current anomalies."""
    result = await api.get_anomalies()
    if not isinstance(result, Anomalies):
        print("No anomaly")
        return
    for source in ANOMALY_SOURCES:
        for detail in getattr(result, source) or []:
            names = ", ".join(anomaly.name for anomaly in detail.anomaly_names)
            print(f"  {source} {detail.label or detail.index}: {names}")


@scenario("webhook", "Show the webhook subscription, if any")
async def webhook(api: DiagralAPI, options: Options) -> None:
    """Show the webhook subscription."""
    subscription = await current_webhook(api)
    if subscription is None:
        print("No webhook subscription")
        return
    events = subscription.subscriptions
    print(
        f"Webhook to {host_only(subscription.webhook_url)}: anomaly={events.anomaly}, "
        f"alert={events.alert}, state={events.state}"
    )


@scenario("automatisms", "List the automatism rules (untested, see the README)")
async def automatisms(api: DiagralAPI, options: Options) -> None:
    """List the automatism rules."""
    rudes = (await api.get_automatism_rudes()).rudes
    if not rudes:
        print("No automatism")
    for rude in rudes:
        print(f"  {rude.name}: canal {rude.canal}, mode {rude.mode}")


@scenario(
    "connection",
    "Test the connection as hass-diagral's setup does",
    needs_keys=False,
    by_default=False,
)
async def connection(api: DiagralAPI, options: Options) -> None:
    """Test the connection, with a temporary API key when none is set."""
    result = await api.try_connection(ephemeral=True)
    print("Connection OK" if result.result else "!! Connection failed")


@scenario("arm", "Arm the whole alarm, wait, then disarm", by_default=False)
async def arm(api: DiagralAPI, options: Options) -> None:
    """Arm the whole alarm, wait, then disarm."""
    await arm_then_disarm(api, "Armed", api.start_system(), options.wait)


@scenario("presence", "Arm in presence mode, wait, then disarm", by_default=False)
async def presence(api: DiagralAPI, options: Options) -> None:
    """Arm in presence mode, wait, then disarm."""
    await arm_then_disarm(api, "Presence", api.presence(), options.wait)


@scenario(
    "partial",
    "Run partial start 1 or 2 (--partial), wait, then disarm",
    by_default=False,
)
async def partial(api: DiagralAPI, options: Options) -> None:
    """Run a partial start, wait, then disarm."""
    await arm_then_disarm(
        api,
        f"Partial start {options.partial}",
        api.partial_start_system(id=options.partial),
        options.wait,
    )


@scenario(
    "groups", "Arm the groups given by --groups, wait, then disarm", by_default=False
)
async def groups(api: DiagralAPI, options: Options) -> None:
    """Arm some groups, wait, then disarm."""
    await arm_then_disarm(
        api,
        f"Groups {options.groups}",
        api.activate_group(groups=options.groups),
        options.wait,
    )


@scenario(
    "webhook-listen",
    "Receive the alarm's notifications on a temporary listener (see the guide)",
    by_default=False,
)
async def webhook_listen(api: DiagralAPI, options: Options) -> None:
    """Subscribe a local listener, provoke events if asked, and show what arrives."""
    existing = await current_webhook(api)
    if existing is not None:
        raise ScenarioFailed(
            f"A webhook subscription already exists, to {host_only(existing.webhook_url)}\n"
            "   Diagral allows one per box: this test would replace it.\n"
            "   If it is hass-diagral's, disable the Diagral entry in Home Assistant\n"
            "   (Settings > Devices & services), run the test, then enable it again."
        )
    base_url = public_base_url(options)
    inbox = NotificationInbox()
    app = web.Application(client_max_size=MAX_NOTIFICATION_SIZE)
    app.router.add_post(inbox.path, inbox.handle)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    made_public = registered = False
    try:
        try:
            await web.TCPSite(runner, LISTEN_HOST, options.port).start()
        except OSError as err:
            raise ScenarioFailed(
                f"Cannot listen on port {options.port}, pick another with --port: {err}"
            ) from err
        if not options.public_url:
            made_public = await make_port_public(options.port)
        url = base_url + inbox.path
        await wait_until_reachable(url, inbox)
        await api.register_webhook(
            webhook_url=url,
            subscribe_to_anomaly=True,
            subscribe_to_alert=True,
            subscribe_to_state=True,
        )
        registered = True
        print("Subscribed the listener to anomalies, alerts and state changes")
        await provoke_and_listen(api, options)
    finally:
        if registered:
            try:
                await api.delete_webhook()
                print("Deleted the webhook subscription")
            except DiagralAPIError as err:
                print(f"!! Could not delete the webhook subscription: {err}")
        if made_public:
            await set_port_visibility(options.port, "private")
        await runner.cleanup()
    print(f"Received {inbox.received} notification(s)")
    if options.trigger != "none" and not inbox.received:
        raise ScenarioFailed(
            "No notification arrived: see Troubleshooting in the guide."
        )


def print_diagnostics(api: DiagralAPI) -> None:
    """Print what an issue about an unexpected answer needs."""
    report: dict[str, Any] = {
        "unexpected_data": unexpected_data(),
        "response_shapes": api.response_shapes(),
    }
    if WEBHOOK_SHAPES:
        report["webhook_shapes"] = WEBHOOK_SHAPES
    print("\n== diagnostics ==")
    print("Attach this to an issue: it holds no value you typed and no identifier.")
    print(json.dumps(report, indent=2, default=str))


async def create_apikey(api: DiagralAPI, keep: bool) -> None:
    """Create the API key the scenarios need, and say what becomes of it."""
    keys = await api.set_apikey()
    if not keep:
        print("Created a temporary API key, deleted at the end")
        return
    print("Created an API key. Store it in .env and never share it:")
    print(f"  {ENV_PREFIX}API_KEY={keys.api_key}")
    print(f"  {ENV_PREFIX}SECRET_KEY={keys.secret_key}")


async def run(
    settings: Settings, names: list[str], options: Options, keep_apikey: bool
) -> int:
    """Run the scenarios in order, and return how many failed."""
    failures = 0
    needs_keys = any(SCENARIOS[name].needs_keys for name in names)
    temporary_key = needs_keys and not (settings.apikey and settings.secret_key)
    async with DiagralAPI(
        username=settings.username,
        password=settings.password,
        serial_id=settings.serial_id,
        apikey=settings.apikey,
        secret_key=settings.secret_key,
        pincode=settings.pincode,
        vendor=settings.vendor,
    ) as api:
        if temporary_key:
            await create_apikey(api, keep_apikey)
        try:
            for name in names:
                print(f"\n== {name} ==")
                try:
                    await SCENARIOS[name].run(api, options)
                except (DiagralAPIError, ScenarioFailed) as err:
                    failures += 1
                    print(f"!! {name} failed: {err}")
        finally:
            if temporary_key and not keep_apikey:
                await api.delete_apikey()
                print("\nDeleted the temporary API key")
        print_diagnostics(api)
    return failures


def parse_args() -> argparse.Namespace:
    """Parse the command line."""
    listing = "\n".join(
        f"  {name:<16}{'' if s.by_default else '[named only] '}{s.help}"
        for name, s in SCENARIOS.items()
    )
    parser = argparse.ArgumentParser(
        description="Try pydiagral against your own Diagral alarm.",
        epilog=f"scenarios:\n{listing}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "scenarios",
        nargs="*",
        metavar="scenario",
        help="scenarios to run, in this order (default: every read-only one)",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=DEFAULT_WAIT,
        help=f"seconds to stay armed before disarming (default: {DEFAULT_WAIT})",
    )
    parser.add_argument(
        "--partial",
        type=int,
        choices=(1, 2),
        default=1,
        help="partial start to run (default: 1)",
    )
    parser.add_argument(
        "--groups",
        type=int,
        nargs="+",
        default=[1],
        help="groups to arm (default: 1)",
    )
    parser.add_argument(
        "--keep-apikey",
        action="store_true",
        help="keep the API key created when .env holds none, and print it",
    )
    parser.add_argument(
        "--trigger",
        choices=TRIGGERS,
        default="none",
        help="webhook-listen: what provokes a notification (default: none, "
        "you act on the alarm yourself)",
    )
    parser.add_argument(
        "--listen-for",
        type=int,
        default=DEFAULT_LISTEN_FOR,
        help=f"webhook-listen: seconds to listen (default: {DEFAULT_LISTEN_FOR})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"webhook-listen: local port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--public-url",
        help="webhook-listen: public URL of your tunnel; found alone in Codespaces",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="log every request and answer, secrets redacted",
    )
    args = parser.parse_args()
    unknown = [name for name in args.scenarios if name not in SCENARIOS]
    if unknown:
        parser.error(f"unknown scenario: {', '.join(unknown)} (see --help)")
    if args.wait < 0 or args.listen_for < 0:
        parser.error("--wait and --listen-for cannot be negative")
    if args.public_url and urlsplit(args.public_url).scheme not in {"http", "https"}:
        parser.error("--public-url must start with http:// or https://")
    return args


def main() -> None:
    """Run the scenarios named on the command line."""
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    names = args.scenarios or [n for n, s in SCENARIOS.items() if s.by_default]
    if not settings.serial_id and any(SCENARIOS[n].needs_serial for n in names):
        sys.exit(
            f"{ENV_PREFIX}SERIAL_ID is required for these scenarios. "
            "Run `uv run try_pydiagral.py systems` to find it."
        )
    options = Options(
        wait=args.wait,
        partial=args.partial,
        groups=args.groups,
        trigger=args.trigger,
        listen_for=args.listen_for,
        port=args.port,
        public_url=args.public_url,
    )
    try:
        failures = asyncio.run(run(settings, names, options, args.keep_apikey))
    except DiagralAPIError as err:
        sys.exit(f"Error: {err}")
    except KeyboardInterrupt:
        sys.exit("Interrupted")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
