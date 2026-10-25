<div align="center">

<img src="https://raw.githubusercontent.com/mguyard/pydiagral/main/docs/pydiagral-Logo.png" width="360" alt="pydiagral" />

### Control and monitor your Diagral alarm from Python 🐍

*An asynchronous client for the official Diagral cloud API, built on `aiohttp`.*

<br />

<a href="https://pypi.org/project/pydiagral/"><img src="https://img.shields.io/pypi/v/pydiagral?color=0080ff&label=PyPI" alt="PyPI"></a>
<img src="https://img.shields.io/badge/python-3.11%2B-0080ff" alt="Python 3.11+">
<img src="https://img.shields.io/github/license/mguyard/pydiagral?color=0080ff" alt="License">
<a href="https://codecov.io/gh/mguyard/pydiagral"><img src="https://codecov.io/gh/mguyard/pydiagral/graph/badge.svg?token=CMVSXEUIRW" alt="Codecov"></a>
<br />
<a href="https://github.com/mguyard/pydiagral/actions/workflows/lint.yaml"><img src="https://github.com/mguyard/pydiagral/actions/workflows/lint.yaml/badge.svg" alt="Lint"></a>
<a href="https://github.com/mguyard/pydiagral/actions/workflows/pytest.yaml"><img src="https://github.com/mguyard/pydiagral/actions/workflows/pytest.yaml/badge.svg" alt="Tests"></a>
<a href="https://github.com/mguyard/pydiagral/actions/workflows/release_and_doc.yaml"><img src="https://github.com/mguyard/pydiagral/actions/workflows/release_and_doc.yaml/badge.svg" alt="Release & Doc"></a>
<img src="https://img.shields.io/github/release-date/mguyard/pydiagral?label=last%20release" alt="Last release date">

<br />

**[📖 Documentation](https://mguyard.github.io/pydiagral/stable/)** ·
**[🧪 Beta docs](https://mguyard.github.io/pydiagral/beta/)** ·
**[🔌 Diagral API](https://appv3.tt-monitor.com/emerald/docs)** ·
**[🏠 hass-diagral](https://github.com/mguyard/hass-diagral)** ·
**[🐛 Report an issue](https://github.com/mguyard/pydiagral/issues)**

</div>

<br />

## 📍 About

`pydiagral` lets you control and monitor a Diagral alarm system through the official Diagral cloud API: arm and disarm it, read its configuration and status, manage webhooks and anomalies, and more. Everything is `async`/`await`, behind a single entry point: `DiagralAPI`.

It powers [**hass-diagral**](https://github.com/mguyard/hass-diagral), the Home Assistant integration for Diagral alarms.

> [!CAUTION]
>
> Please note that the Diagral alarm system is a security system, and it may be preferable not to connect it to any automation platform for security reasons.
> In no event shall the developer of [`pydiagral`](https://github.com/mguyard/pydiagral) library be held liable for any issues arising from the use of this [`pydiagral`](https://github.com/mguyard/pydiagral) library.
> The user installs and uses this integration at their own risk and with full knowledge of the potential implications.

## ✅ Requirements

| | |
|---|---|
| 🐍 **Python** | 3.11 or later |
| 📦 **Diagral box** | DIAG56AAX or DIAG59AAX, which connects your alarm system to the internet and enables the API |
| 👤 **Account** | Your Diagral account e-mail and password |
| 🔢 **Serial ID** | The serial number of your box — see the [FAQ](#-faq), or [discover it from your account](#discover-the-serial-ids) |

> [!NOTE]
>
> The DIAG56AAX is end of sale. More information about the [DIAG59AAX](https://www.diagral.fr/2026/01/19/nouvelle-centrale-dalarme-ip-4g-diagral-diag99agx/), available inside the DIAG99AGX.

## ✨ Features

| | Area | What you can do |
|:---:|---|---|
| 🔐 | **Authentication** | Log in with username and password · create, validate and delete API keys · list the systems of the account and their API keys, to discover the serial IDs |
| ⚙️ | **Configuration** | Retrieve the alarm configuration |
| 📊 | **System information** | Read the system details and current status · check that the Diagral cloud answers (health check, no credential needed) · manage webhooks · manage anomalies |
| 🛡️ | **Control** | Arm or disarm the system, globally or partially · list automatism rules and run their actions |
| 🩺 | **Diagnostics** | List what Diagral sent that the models did not expect (`pydiagral.models.unexpected_data()`) · describe the structure of the last response of each read (`DiagralAPI.response_shapes()`) — both without any value the user entered |

## 🚀 Quick start

### 1. Install

```bash
pip install pydiagral
```

To try the latest beta: `pip install --pre pydiagral`.

### 2. Read your alarm status

```python
import asyncio

from pydiagral import DiagralAPI


async def main() -> None:
    async with DiagralAPI(
        username="your_email@example.com",
        password="your_password",
        serial_id="your_serial_id",
        pincode="your_pin_code",
    ) as diagral:
        await diagral.login()
        # Creates an API key on your account: keep it and pass apikey= and
        # secret_key= next time instead of creating a new one.
        api_key = await diagral.set_apikey()

        status = await diagral.get_system_status()
        print(status.status, status.activated_groups)


asyncio.run(main())
```

### 3. Try it on your alarm with the example script

[`try_pydiagral.py`](https://github.com/mguyard/pydiagral/blob/main/try_pydiagral.py) runs ready-made scenarios against your own alarm. Copy [`.env.example`](https://github.com/mguyard/pydiagral/blob/main/.env.example) to `.env` next to the script, fill it in, then run it with [uv](https://docs.astral.sh/uv/), which installs the latest pydiagral, betas included:

```bash
uv run try_pydiagral.py                  # every read-only scenario
uv run try_pydiagral.py status anomalies # only these
uv run try_pydiagral.py arm --wait 10    # arm, wait 10 s, then disarm
uv run try_pydiagral.py --help           # every scenario and option
```

No Python at hand? The script also runs in [GitHub Codespaces](https://mguyard.github.io/pydiagral/stable/try-pydiagral/#in-github-codespaces-nothing-to-install), from your browser, with nothing to install.

Every scenario, option and message is explained in the [**guide to try_pydiagral.py**](https://mguyard.github.io/pydiagral/stable/try-pydiagral/).

> [!TIP]
>
> Without arguments, the script changes nothing on your alarm: the scenarios that arm, disarm or register a webhook only run when you name them, and those that arm always disarm at the end, even on an error or Ctrl+C. Its output ends with a diagnostics report, ready to attach to an issue.

## ⚙️ Client options

| Option | Default | Purpose |
|---|---|---|
| `serial_id` | `None` | The box to talk to. Only `login()`, `get_systems()` and `ping()` work without it |
| `apikey`, `secret_key` | `None` | An existing API key, instead of creating one with `set_apikey()` |
| `pincode` | `None` | The alarm PIN code, needed to read the system status and details, to arm or disarm, and to run an action |
| `request_timeout` | `30` | Deadline of each request, in seconds |
| `session` | `None` | An `aiohttp.ClientSession` you already manage |
| `vendor` | `"DIAGRAL"` | The brand of the account |

<details>
<summary><b>⏱️ Request timeout</b></summary>

<br />

Each request to the Diagral cloud may take up to 30 seconds. To allow more, set `request_timeout` (in seconds) when creating the client:

```python
async with DiagralAPI(
    username=username,
    password=password,
    serial_id=serial_id,
    request_timeout=60,
) as diagral:
    ...
```

To give a single call a shorter deadline, wrap it in `asyncio.timeout()`. That deadline cannot exceed `request_timeout`.

</details>

<details>
<summary><b>🔗 Shared session</b></summary>

<br />

To send requests through an `aiohttp.ClientSession` you already manage, pass it as `session`. The client uses it as is and never closes it:

```python
async with aiohttp.ClientSession() as session:
    async with DiagralAPI(
        username=username,
        password=password,
        serial_id=serial_id,
        session=session,
    ) as diagral:
        ...
```

Without `session`, the client opens its own on `async with` and closes it on exit.

</details>

<details>
<summary><b>🏷️ Brand</b></summary>

<br />

Diagral shares its cloud with sister brands. For an account of another brand, set `vendor` when creating the client, to one of `DIAGRAL` (the default), `DAITEM`, `EDAITEM`, `LOGISTYALMA` or `DISTRIBUTION`, in any case:

```python
async with DiagralAPI(
    username=username,
    password=password,
    serial_id=serial_id,
    vendor="DAITEM",
) as diagral:
    ...
```

</details>

<a id="discover-the-serial-ids"></a>
<details>
<summary><b>🔎 Discover the serial IDs</b></summary>

<br />

Without a serial ID, the client can still log in and list the systems of the account. Create it with the serial ID you pick to use every other call:

```python
async with DiagralAPI(username=username, password=password) as diagral:
    systems = await diagral.get_systems()
serial_id = systems[0].serial_id
```

</details>

## 🧪 Untested features

Some parts of pydiagral are built from the Diagral API documentation only, because they could not be checked on a real installation. pydiagral logs a warning the first time each of them is used:

| Feature | Status |
|---|---|
| 📷 **Cameras** | `AlarmConfiguration.cameras` follows the `CameraModel` of the Diagral OpenAPI specification. The warning appears when a configuration includes cameras. |
| 🤖 **Automatisms** | `get_automatism_rudes()` lists the automatisms and `set_automatism_action()` runs one. Only an empty list has been seen; what `TIMER` does, and whether an action must match the automatism's mode, are unknown. |
| 🗑️ **Anomaly deletion** | `delete_anomalies()` deletes an anomaly. Which identifier it expects is unknown: the anomalies `get_anomalies()` returns have none of their own. |
| 🔌 **Product enabling and disabling** | `enable_product()` and `disable_product()` follow the specification. What disabling does, and which identifier designates a device, are unknown. |

> [!IMPORTANT]
>
> **You own the matching equipment or use these calls? Your help is welcome!** Please [open an issue](https://github.com/mguyard/pydiagral/issues) describing what you observe, with what pydiagral recorded about it, which holds no value you typed and no identifier:
>
> - With [hass-diagral](https://github.com/mguyard/hass-diagral), attach the integration's diagnostics: they include both lists below.
> - From Python, attach the output of `pydiagral.models.unexpected_data()`, and of `response_shapes()` called on the client after the calls in question.

The debug log shows the full answers instead: enable the `pydiagral` logger at debug level, with `logging.getLogger("pydiagral").setLevel(logging.DEBUG)`, or in Home Assistant with `pydiagral: debug` under `logger: logs:`. Keys, tokens, PIN codes and serial numbers are redacted, but the log still shows the names of your devices: read it before posting.

## 📖 Documentation

| | Stable | Beta |
|---|---|---|
| 🏠 **Home** | [stable](https://mguyard.github.io/pydiagral/stable/) | [beta](https://mguyard.github.io/pydiagral/beta/) |
| 🧩 **API reference** — the `DiagralAPI` class and its methods | [stable](https://mguyard.github.io/pydiagral/stable/api/) | [beta](https://mguyard.github.io/pydiagral/beta/api/) |
| 🗂️ **Data models** — the data structures used | [stable](https://mguyard.github.io/pydiagral/stable/models/) | [beta](https://mguyard.github.io/pydiagral/beta/models/) |
| ⚠️ **Exceptions** — the package exceptions | [stable](https://mguyard.github.io/pydiagral/stable/exceptions/) | [beta](https://mguyard.github.io/pydiagral/beta/exceptions/) |

The official Diagral API documentation is available [here](https://appv3.tt-monitor.com/emerald/docs).

## 🙋 FAQ

### How to find the serial on a DIAG56AAX?

The serial number can only be found with physical access to the box. You need to open it, and you will find a label with a QR Code.

On this label, there is a 14-character code that represents the serial number of the box.

<p align="center">
  <img src="https://raw.githubusercontent.com/mguyard/pydiagral/main/docs/how-to-find-diagral-serial.png" alt="How to find your Diagral serial" />
</p>

> [!IMPORTANT]
>
> This code is necessary to use this library and Diagral API.

## 🤝 Contributing

Contributions are welcome! 💙

- 🐛 **Report issues**: submit the bugs you find or request a feature.
- 🔀 **Submit pull requests**: review open PRs, and submit your own against the `dev` branch.
- 🤖 **Using an AI assistant?** It is welcome too: point it at [`AGENTS.md`](https://github.com/mguyard/pydiagral/blob/dev/AGENTS.md), which holds the repository rules.

Setup, workflow, commit format and ground rules are in [**CONTRIBUTING.md**](https://github.com/mguyard/pydiagral/blob/dev/CONTRIBUTING.md).

## 📄 License

pydiagral is distributed under the GPL-v3 License. See the [LICENSE](https://github.com/mguyard/pydiagral/blob/main/LICENSE) file for more details.

<div align="center">
<br />
<sub>Made with ❤️ for Diagral owners</sub>
</div>
