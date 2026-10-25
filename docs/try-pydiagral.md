# Try pydiagral on your alarm

[`try_pydiagral.py`](https://github.com/mguyard/pydiagral/blob/main/try_pydiagral.py) runs ready-made scenarios against your own Diagral alarm: check that everything answers, read the configuration and the status, arm and disarm, test a webhook. It is the quickest way to see what pydiagral does with your installation, and to collect what an issue needs when something looks wrong.

!!! warning

    The script talks to your real alarm. Read what a scenario does before naming it: some arm the alarm, so make sure nobody moves in a protected area meanwhile.

## 1. Choose where to run it

### In GitHub Codespaces — nothing to install

[Codespaces](https://docs.github.com/en/codespaces/overview) runs the repository on a machine in the cloud, from your browser. It is free within a [monthly allowance](https://docs.github.com/en/billing/reference/product-usage-included) that a session with the script barely touches. Every scenario works there, and it is the simplest way to [test webhooks](#testing-webhooks).

1. **Fork the repository** to your account: [github.com/mguyard/pydiagral/fork](https://github.com/mguyard/pydiagral/fork). **Untick *Copy the `main` branch only***, so that your fork also gets `beta`, the branch with the latest version of pydiagral and of this script. Later, the *Sync fork* button of your fork brings it up to date.
2. **Create the codespace with *New with options***: on your fork, *Code > Codespaces*, then the *⋯* menu > *New with options*.
    1. Pick the `beta` branch.
    2. The page asks for the secrets the dev container suggests, the variables of [Configure](#2-configure). GitHub shows none as mandatory, since it lets you leave any empty, but the script needs:
        - `DIAGRAL_USERNAME` and `DIAGRAL_PASSWORD`: always;
        - `DIAGRAL_SERIAL_ID`: for every scenario but `ping` and `systems`. If you do not know it, leave it empty, run `systems` to find it, then add it as described in the note below;
        - `DIAGRAL_PIN_CODE`: to read the status and details, and to arm or disarm.
    3. Click *Create codespace*. It starts the repository's [dev container](https://github.com/mguyard/pydiagral/blob/main/CONTRIBUTING.md#-dev-container), with pydiagral and every tool installed. On first start, it opens this guide in a browser tab; its terminal shows the guide's address on every start.

    GitHub keeps these secrets [encrypted in your account](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces), never in the repository, and gives them to the script as environment variables. It does not ask again for your next codespaces on this fork.

3. **Run** the commands of [Run](#3-run) in the codespace's terminal, with:
    - `python try_pydiagral.py …` to try the code of the branch the codespace opened;
    - `uv run try_pydiagral.py …` to try the latest release, betas included.

!!! note "Adding or changing a secret afterwards"

    Only *New with options* asks for the secrets. If you created the codespace with the *Create codespace on …* button instead, or left a secret empty, add it yourself:

    1. open [Settings > Codespaces](https://github.com/settings/codespaces) on GitHub, and click *New secret*;
    2. enter its name, `DIAGRAL_SERIAL_ID` for instance, and its value;
    3. under *Repository access*, select your fork.

    To change a value, edit the secret on the same page.

    In both cases, stop and restart the codespace (*Codespaces: Stop Current Codespace* in the command palette, or from [github.com/codespaces](https://github.com/codespaces)): a codespace reads its secrets when it starts.

Stop the codespace once done, and delete it when you no longer need it: its storage counts against the allowance as long as it exists.

### On your machine

Download [`try_pydiagral.py`](https://github.com/mguyard/pydiagral/blob/main/try_pydiagral.py) and [`.env.example`](https://github.com/mguyard/pydiagral/blob/main/.env.example) into the same folder, or clone the repository.

The recommended way to run the script is [uv](https://docs.astral.sh/uv/getting-started/installation/). The script declares what it needs at its top ([inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)), and `uv run` installs it in an environment of its own, apart from your other projects: nothing else to install.

!!! info "Always the latest pydiagral"

    The script is meant to show what the library does today: on every run, uv checks for the latest pydiagral, **betas included**, and uses it. A new release can take a few minutes to show up, while uv's cache of the package index expires.

Without uv, install the dependencies yourself, ideally in a virtual environment, and run the commands below with `python` instead of `uv run`:

```bash
pip install --upgrade --pre pydiagral python-dotenv
```

`--pre` lets pip pick a beta. Run the same command again to move to a newer release.

!!! tip "Testing your own changes to pydiagral"

    `uv run` always takes pydiagral from PyPI, even inside the repository. To try a local change, install the repository in editable mode (`PYPROJECT_VERSION=0.1.0-dev pip install -e ".[dev]"`, which the [dev container](https://github.com/mguyard/pydiagral/blob/main/CONTRIBUTING.md#-dev-container) does for you) and run `python try_pydiagral.py`.

## 2. Configure

Where the settings come from depends on where the script runs:

- **In Codespaces**, the secrets you entered on *New with options* are the settings: nothing to do here. To add an optional one from the table below, or one you left empty, see the note *Adding or changing a secret afterwards* [above](#in-github-codespaces-nothing-to-install).
- **On your machine**, copy `.env.example` to `.env`, next to the script, and fill it in.

Every variable starts with `DIAGRAL_`, and an empty value counts as unset:

| Variable | Needed for | Purpose |
|---|---|---|
| `DIAGRAL_USERNAME` | everything | The e-mail address of your Diagral account |
| `DIAGRAL_PASSWORD` | everything | The password of your Diagral account |
| `DIAGRAL_SERIAL_ID` | every scenario but `ping` and `systems` | The serial ID of your box. Run the `systems` scenario to find it |
| `DIAGRAL_PIN_CODE` | `status`, `details`, and every scenario that arms | Your alarm PIN code, also named master code |
| `DIAGRAL_API_KEY`, `DIAGRAL_SECRET_KEY` | optional | An existing API key. Left empty, the script creates a temporary one — see [API keys](#api-keys) |
| `DIAGRAL_VENDOR` | optional | The brand of your account: `DIAGRAL` (default), `DAITEM`, `EDAITEM`, `LOGISTYALMA` or `DISTRIBUTION` |

Variables already set in the environment, Codespaces secrets included, take precedence over `.env`.

!!! danger

    `.env` holds your credentials: never commit it, attach it to an issue or share it.

## 3. Run

The commands start with `python` or `uv run`, depending on where the script runs and which pydiagral it should use:

| Where | Command | pydiagral used |
|---|---|---|
| Codespaces | `python try_pydiagral.py …` | The code of the branch the codespace opened, `beta` of your fork: the usual choice |
| Codespaces | `uv run try_pydiagral.py …` | The latest release on PyPI, betas included, whatever the branch |
| Your machine, with uv | `uv run try_pydiagral.py …` | The latest release on PyPI, betas included |
| Your machine, without uv | `python try_pydiagral.py …` | The one you installed with pip |

The examples below use `python`; replace it with `uv run` where the table says so.

```bash
python try_pydiagral.py                  # every read-only scenario
python try_pydiagral.py ping systems     # only these, in this order
python try_pydiagral.py arm --wait 10    # arm, wait 10 s, then disarm
python try_pydiagral.py --help           # every scenario and option
```

Without arguments, the script runs every read-only scenario: nothing changes on your alarm. Each scenario prints a `== name ==` header followed by what it found. When one fails, its error is printed and the next one runs.

A good first run is `ping systems`: it only needs the username and password, checks that the Diagral cloud answers, and shows the serial ID of each system of your account.

## Scenarios

### Read-only — run by default

| Scenario | What it shows |
|---|---|
| `ping` | Whether the Diagral cloud answers. Needs no API key |
| `systems` | The serial ID of each system of your account, and how many API keys each has. Needs no serial ID |
| `configuration` | The alarm name, its groups, and how many devices of each type it has |
| `devices` | Every device of the alarm, by type, with its index and label |
| `details` | The box model, firmware version and mode. Needs the PIN code |
| `status` | Whether the alarm is armed, and which groups are active. Needs the PIN code |
| `anomalies` | The current anomalies, by device |
| `webhook` | The webhook subscription, if any, with the host of its URL only |
| `automatisms` | The automatism rules. This call is [untested](https://github.com/mguyard/pydiagral#-untested-features): pydiagral logs a warning |

### Named only — never run by default

| Scenario | What it does |
|---|---|
| `connection` | Tests the connection the way hass-diagral's setup does. Without an API key, it creates a temporary one and deletes it |
| `arm` | Arms the whole alarm, waits, then disarms |
| `presence` | Arms in presence mode, waits, then disarms |
| `partial` | Runs partial start 1 or 2 (`--partial`), waits, then disarms |
| `groups` | Arms the groups given by `--groups`, waits, then disarms |
| `webhook-listen` | Receives the alarm's notifications on a temporary listener — see [Testing webhooks](#testing-webhooks) |

The scenarios that arm **always disarm at the end**: after the wait, and when the arming call fails. If disarming itself fails, the script says so: check your alarm.

**Ctrl+C** depends on when you press it:

- while the script waits or listens, as its message says, it ends that wait only: the scenarios that armed disarm at once, and the run goes on to the end, [diagnostics report](#diagnostics-report) included;
- at any other moment, it stops the run, after the usual clean-up: disarming, deleting the temporary API key and the webhook subscription.

## Options

| Option | Default | Effect |
|---|---|---|
| `--wait SECONDS` | `30` | How long the arming scenarios stay armed before disarming |
| `--partial {1,2}` | `1` | Which partial start `partial` runs |
| `--groups N [N ...]` | `1` | Which groups `groups` arms, e.g. `--groups 1 2` |
| `--keep-apikey` | off | Keeps the API key the script creates, and prints it |
| `--trigger {none,presence,arm}` | `none` | What `webhook-listen` does to provoke a notification |
| `--listen-for SECONDS` | `120` | How long `webhook-listen` listens |
| `--port PORT` | `8080` | The local port `webhook-listen` listens on |
| `--public-url URL` | found alone in Codespaces | The public URL of your tunnel to that port |
| `--debug` | off | Logs every request and answer — see [Debug log](#debug-log) |

## Testing webhooks

Diagral can push the alarm's events to a URL: state changes, alerts and anomalies. `webhook-listen` checks that they reach you and that pydiagral reads them. It starts a temporary listener, makes sure the public URL reaches it, subscribes it, waits for notifications and shows each one, then deletes the subscription.

!!! warning "One subscription per box"

    Diagral keeps a single webhook subscription per box. When one exists, hass-diagral's for instance, the scenario stops before doing anything, since it would replace it. With hass-diagral, disable the Diagral entry in Home Assistant (*Settings > Devices & services*), run the test, then enable the entry again: the integration subscribes again when the entry starts.

Diagral must reach the listener from the Internet, which a computer at home usually does not allow. Two free ways around it:

### In GitHub Codespaces — recommended

In a codespace [set up as above](#in-github-codespaces-nothing-to-install), run:

```bash
python try_pydiagral.py webhook-listen
```

While it listens, two minutes by default, arm or disarm the alarm yourself, from a keypad, a badge or the Diagral app, and watch the notifications arrive. To let the script arm and disarm instead, see [Triggers](#triggers).

Nothing else is needed: the script builds the public URL of the codespace's port, makes the port public with the GitHub CLI, and makes it private again at the end. When it cannot, it says so and waits up to two minutes: in the *Ports* tab, right-click port 8080, then *Port Visibility > Public*.

### On your machine, with a Cloudflare Quick Tunnel

A [Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) gives a public `trycloudflare.com` address to a local port, without a Cloudflare account.

1. Install `cloudflared` by following [Cloudflare's downloads page](https://developers.cloudflare.com/tunnel/downloads/).
2. In another terminal, start the tunnel to the listener's port, and copy the `https://….trycloudflare.com` address it prints:

    ```bash
    cloudflared tunnel --url http://localhost:8080
    ```

3. Run the scenario with that address:

    ```bash
    uv run try_pydiagral.py webhook-listen --public-url https://….trycloudflare.com
    ```

The address changes every time the tunnel starts: pass the new one on each run. Do not add `--allowed-mail` to the tunnel, since Diagral cannot sign in. Any other tunnel to the same port, ngrok for instance, works the same way.

### Triggers

| `--trigger` | What happens |
|---|---|
| `none` (default) | The script listens for `--listen-for` seconds, while you arm or disarm the alarm yourself, from a keypad, a badge or the Diagral app |
| `presence` | The script arms in presence mode, listens for `--listen-for` seconds, disarms, then listens 30 seconds more for the disarm notification. Presence mode has no exit delay: the quickest way to let the script provoke a notification |
| `arm` | The same with the whole alarm. Its notification only arrives once the exit delay is over, about four minutes, so the script stays armed and listens at least five minutes |

With `presence` or `arm`, the scenario fails when no notification arrived.

### What you see

Each notification prints its type, code and description, the group, the device type and the type of user who acted. The transmitter ID, which is your serial number, and the user name are never printed. The structure of each notification, without its values, joins the [diagnostics report](#diagnostics-report) under `webhook_shapes`.

### Safety

- The listener only accepts connections from the computer itself (`127.0.0.1`), which the tunnel uses, and only on a random path drawn for the run: any other request is refused.
- The script deletes the subscription, disarms if it armed, and makes the Codespaces port private again at the end, even after an error or Ctrl+C.
- If the script is killed before cleaning up, its subscription stays in place. Recent versions of hass-diagral then show a repair, *webhook used by another installation*, that lets you take the subscription back. With older versions, disabling then enabling the Diagral entry does the same.

## API keys

Most calls are signed with an API key. When `.env` holds none and a scenario needs one, the script creates a temporary key at the start and **deletes it at the end**, even when a scenario fails or you press Ctrl+C.

To stop creating a key on every run, run once with `--keep-apikey`: the script prints two lines to paste into `.env`.

```text
  DIAGRAL_API_KEY=…
  DIAGRAL_SECRET_KEY=…
```

The next runs use that key. The `systems` scenario shows how many keys each system has, which helps spot keys left behind.

## Diagnostics report

Every run that completes ends with a `== diagnostics ==` section, in JSON:

- `unexpected_data`: what Diagral sent that pydiagral's models did not expect, such as a missing field or an unknown value;
- `response_shapes`: the structure of the last answer of each read, keys kept and values replaced.

Neither holds a value you typed nor an identifier: it is made to be attached to an [issue](https://github.com/mguyard/pydiagral/issues) as is. When the output of a scenario looks wrong, or a warning asks you to report something, run that scenario and attach the report.

## Debug log

`--debug` logs every request and answer of pydiagral on the standard error. Keys, tokens, PIN codes and serial numbers are redacted, but the log still shows the names of your devices and groups: read it before posting it.

```bash
python try_pydiagral.py status --debug 2> debug.log
```

## Troubleshooting

| Message | Cause |
|---|---|
| `DIAGRAL_USERNAME and DIAGRAL_PASSWORD are required` | `.env` is missing, not next to the script, or does not set them |
| `DIAGRAL_SERIAL_ID is required for these scenarios` | Set it, or run `systems` to find it |
| `!! status failed: PIN code required to …` | Set `DIAGRAL_PIN_CODE` |
| `error: unknown scenario` | A typo in a scenario name: `--help` lists them |
| `A webhook subscription already exists` | See [One subscription per box](#testing-webhooks) |
| `Outside Codespaces, start a tunnel` | Start a tunnel and pass its address with `--public-url` |
| `The listener is not reachable` | In Codespaces, port 8080 is still private. Locally, the tunnel is not running, points to another port than `--port`, or a firewall blocks it: `cloudflared` needs to reach Cloudflare on port 7844 |
| `Cannot listen on port` | Another program uses the port: pick another with `--port`, and point the tunnel to it |
| `No notification arrived` | With `--trigger arm`, the exit delay may be longer than the listening time: raise `--listen-for`. Otherwise, run `webhook` to check that no other subscription took over |

The script exits with code `0` when every scenario succeeded, `1` when one failed or the run stopped, and `2` on a wrong command line.
