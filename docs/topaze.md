# Optional Topaze emergency client

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

::: pydiagral.topaze_api.TopazeDiagralAPI
    handler: python
    options:
      show_root_heading: true
      show_root_toc_entry: false
      members_order: source

<!-- prettier-ignore-end -->
