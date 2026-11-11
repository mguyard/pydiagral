# Automatic fallback and recovery

`FailoverDiagralAPI` automatically handles partial Emerald outages. Every
`get_core_snapshot()` call first reads authenticated Emerald configuration and live
status under a ten-second deadline. A network error, timeout or server error switches
that core read to Topaze. Every subsequent poll tries Emerald again; only a complete
valid snapshot of the same central restores the primary backend. A successful public
ping alone is insufficient. Authentication, PIN, identity and validation errors
propagate without using the alternate service.

`CoreSnapshot` contains `alarm_config`, `devices_infos` and `system_status` from one
backend. It is published only after all fields validate, so a failed primary status
read cannot mix newly read primary configuration into an alternate snapshot.
`active_api` reports `emerald` or `topaze`; `uses_topaze` follows that selection.
`fallback_api_connected` is unknown before a core read, true after a successful
alternate read, and false when idle or failed. Returning to Emerald does not open
any Topaze session.

`primary_api_connected` follows the authenticated core probe, not the public ping:
it is unknown initially, false on any failed probe, and true only after a validated
primary snapshot. `primary_error` contains only the exception category (for example,
`ClientError` or `ServerError`), never raw server text, and is cleared on recovery.
If both backends fail, both connection flags are false; the last `active_api` alone
must not be interpreted as proof of current connectivity.

```python
from pydiagral import FailoverDiagralAPI

async with FailoverDiagralAPI(
    username=username,
    password=password,
    serial_id=serial_id,
    pincode=pin_code,
    apikey=api_key,
    secret_key=secret_key,
) as api:
    api.expected_central_serial = known_central_serial
    snapshot = await api.get_core_snapshot()
    status = snapshot.system_status
```

`get_configuration()` refreshes the complete snapshot and returns its configuration;
`get_devices_info()` returns labels from the last validated snapshot;
`get_system_status()` refreshes the snapshot and returns fresh state. A consumer
polling all core data should call `get_core_snapshot()` once per poll.

Core reads and whole-system commands share a lock. Each whole-system command performs
a read-only preflight to select a working backend before sending its POST exactly
once. An uncertain response is never retried on either service. The caller can make
a later read-only status check. Group commands, anomalies, webhooks and account
management continue to use Emerald.

The primary probe has a ten-second deadline. The alternate snapshot has a 120-second
deadline, allowing its owned-session cleanup to complete after cancellation. A
normal poll never needs Topaze while authenticated Emerald reads remain healthy.
Unit tests and local HTTP servers cover failure, atomic snapshots, recovery,
cancellation, session ownership and no command replay without calling the real cloud.

## Direct Topaze client

`TopazeDiagralAPI` provides an explicit alternative for installations affected by a
partial Emerald outage. The standard `DiagralAPI` client and its behavior are
unchanged. Consumers choose the client before polling; requests and commands are
never retried against a second backend automatically.

## Supported operations

| Operation | Backend | Behavior |
|---|---|---|
| `get_configuration` | Topaze | Validated metadata, cached for one hour |
| `get_devices_info` | Cached Topaze configuration | Device index/label lookup |
| `get_system_status` | Topaze | Fresh state and activated groups |
| `start_system`, `stop_system`, `presence` | Topaze | One command, then a matching state read |
| Anomalies, webhooks, group commands, account management | Emerald | Inherited behavior; independently subject to Emerald outages |

The public models are unchanged. Central identity comes from `centralId`, not the
different radio identifier. Group count, labels, selected groups and available delays
come from the configuration; neither four groups nor a 90-second delay is assumed.
Missing or inconsistent state/group data raises a validation error instead of
inventing a safe or armed state. No raw inventory is exposed or logged: it can contain
camera credentials and encryption material unrelated to these public models.

## Usage

```python
from pydiagral import TopazeDiagralAPI

async with TopazeDiagralAPI(
    username=username,
    password=password,
    serial_id=serial_id,
    pincode=pin_code,
    apikey=api_key,
    secret_key=secret_key,
) as api:
    api.expected_central_serial = known_central_serial
    configuration = await api.get_configuration()
    status = await api.get_system_status()
```

`expected_central_serial` is optional. Consumers with an existing device registry
should set it before reading; a mismatch stops the operation before opening a TTM
connection. A caller-owned `aiohttp.ClientSession` can be passed as `session=`; it is
neither replaced nor closed by the client. Other constructor keyword arguments have
the same meaning as for `DiagralAPI`.

## Sessions, timeouts and caching

Every core read opens an owned account session, selects the configured transmitter,
and opens an owned TTM session. A per-client lock prevents overlapping sessions.
Cleanup attempts disconnect and logout even after failure or cancellation, using
bounded requests. It never discovers or disconnects a session belonging to another
client; a busy mobile session can therefore prevent a read.

Individual requests are bounded to eight seconds, cleanup requests to three seconds,
and inventory polling to eighteen seconds. These are request/job limits, not a
deadline for the entire multi-request operation. Rate limits are undocumented and
historical implementations report hourly connection limits: avoid fast polling.

Configuration is refreshed after one hour. A transient transport or server error
retains the last validated configuration so that the consumer can still read current
status. Initial inventory failure, changed identity, rejected authentication and
malformed metadata remain errors. Cached metadata is never used as live alarm status.

Whole-system commands are dispatched once. `CMD_OK` is insufficient: a fresh state
must match the requested mode. If the response is lost or the state is inconsistent,
the method raises an error and does not retry. Group commands remain on Emerald
because their Topaze transition semantics have not been validated.

## Validation and limits

Configuration and status reads worked on one real installation during Emerald
timeouts. Real alarm commands and webhook delivery were not tested. Unit tests cover
request construction, secret redaction, identity validation, owned-session cleanup,
cancellation, inventory parsing, invalid states, and no command replay.

Topaze remains a cloud dependency. It does not restore Emerald anomaly data or prove
that a remote webhook subscription is delivering events. No claim is made that the
current official mobile application uses this exact protocol.

Historical protocol references:

- [eedomus-diagral](https://github.com/Aymkdn/eedomus-diagral/blob/main/diagral.php)
- [Jeedom-Diagral_eOne](https://github.com/eliovir/Jeedom-Diagral_eOne/blob/master/3rparty/Diagral/Diagral_eOne.class.php)

<!-- prettier-ignore-start -->

## API reference

::: pydiagral.failover_api.FailoverDiagralAPI
    handler: python
    options:
      show_root_heading: true
      show_root_toc_entry: false
      members_order: source

::: pydiagral.topaze_api.TopazeDiagralAPI
    handler: python
    options:
      show_root_heading: true
      show_root_toc_entry: false
      members_order: source

<!-- prettier-ignore-end -->
