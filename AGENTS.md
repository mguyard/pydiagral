# Agent Instructions — pydiagral

Repository rules for AI coding agents. This file is the source of truth; `CLAUDE.md` imports it and adds only what is specific to Claude Code.

## Precedence

`.claude/rules/` is vendored from the ECC plugin (2.2.3) and kept byte-identical to upstream, so it can be refreshed without merge work.
It is generic advice, written for no repository in particular.
**Where it disagrees with this file, this file wins.**

The known divergences, so they do not have to be rediscovered:

| An ECC rule says | This repository does |
|---|---|
| Format with `black`, sort imports with `isort` | `ruff format` and ruff's isort (`I`) only. Imports use `force-sort-within-sections`, which isort does not reproduce by default, and `black` disagrees with `ruff format` on conditional expressions — running either would fight the configured tools. `lint.yaml` runs `ruff format --check`. |
| Run `mypy` / `pyright` after editing | `mypy` only, configured under `[tool.mypy]` in `pyproject.toml`: it checks `src/pydiagral` against the Python 3.11 floor, and `lint.yaml` runs it. No pyright. The package ships a `py.typed` marker, so consumers' type checkers read these annotations: an annotation is part of the public surface. Fix the type rather than adding `# type: ignore`. |
| Scan with `bandit` | Ruff's full `S` rule set (flake8-bandit); `tests/` ignores `S101`, `S105`, `S106`. `bandit -r src/` finds nothing either. Neither catches secrets written to logs — see Invariants. |
| `@pytest.mark.unit` / `.integration`, E2E tests | No marker is registered in `pyproject.toml`. Every test is a unit test; a real integration test would need live Diagral credentials in CI, which is not acceptable. End-to-end coverage lives in hass-diagral, against its fake Diagral cloud. |
| Prefer `@dataclass(frozen=True)` | Models are plain `@dataclass`. Freezing them changes the public API for every consumer, for no gain on response objects. |
| Load secrets from `.env` with `python-dotenv` | `.env` exists for the maintainer's manual scripts only (`example_code.py`, `diag_code.py`). The library itself takes credentials as constructor arguments. Agents never read `.env` — see Secrets. |
| Anything about FastAPI | `rules/ecc/python/fastapi.md` has nothing to do with this library. Its `**/*_api.py` glob happens to match `tests/test_pydiagral_api.py`; ignore it there. |

## Project

Asynchronous Python client for the Diagral alarm cloud API (`appv3.tt-monitor.com/emerald`), built on `aiohttp`. Published to PyPI as [`pydiagral`](https://pypi.org/project/pydiagral/), documented at [mguyard.github.io/pydiagral](https://mguyard.github.io/pydiagral/).

- All code, comments, docstrings and commit messages in **English**.
- The single entry point is `DiagralAPI`, an async context manager.
- **The main consumer is [hass-diagral](https://github.com/mguyard/hass-diagral)**, the Home Assistant integration by the same author. It pins an exact version in its `manifest.json`. Any change to the public surface listed under Contracts is a breaking change for it.

## Module map

```
src/pydiagral/
├── __init__.py     # Public re-exports (__all__)
├── api.py          # DiagralAPI — every HTTP call, through _request()
├── models.py       # CamelCaseModel base + every request/response dataclass
├── exceptions.py   # DiagralAPIError and its subclasses
├── constants.py    # BASE_URL, API_VERSION
└── utils.py        # generate_hmac_signature()
tests/
├── test_pydiagral_api.py   # The whole suite
└── data/                   # JSON fixtures: configuration_sample.json, system_details_sample.json
docs/               # MkDocs pages — generated from docstrings, see Documentation
example_code.py     # Manual end-to-end script, reads .env
```

`diag_code.py` (diagnostic script) and `.env` are local to the maintainer's machine and git-ignored.

## Invariants

- **Every HTTP call goes through `DiagralAPI._request()`.** It builds the URL, maps HTTP status codes to exceptions and wraps `aiohttp` errors.
- `_request()` returns a **tuple** `(json_body, status_code)`. Callers unpack it: `response_data, *_ = await self._request(...)`.
- Authenticated endpoints build their headers in the method itself: `Authorization: Bearer <token>` after `login()`, or the HMAC set `X-HMAC`, `X-TIMESTAMP`, `X-APIKEY` — plus `X-PIN-CODE` where the endpoint needs it — from `generate_hmac_signature()`.
- Models inherit `CamelCaseModel` and are decorated with `@dataclass`. **`from_dict()` does not convert snake_case to camelCase**: it matches the field name or its `alias`, case-insensitively. A field whose API key is camelCase (`inputDelay`) needs `field(metadata={"alias": "inputDelay"})`, or it silently stays `None`. Only `to_dict()` converts automatically.
- A model field with no default and no `None` in its type is required: when a response leaves it out or sends null, the parser logs a one-time warning asking users to report it, and the field stays `None`. Declare a field the API may omit as `X | None = None`. Never make the parser reject such a payload: the models do not yet cover every box's responses, and a rejection would block hass-diagral over a field it may not read. A parser error raises `ModelValidationError`, whose message names the model but quotes no payload value.
- Type hints use PEP 604 (`str | None`) and `list[...]` / `dict[...]`. Annotate every function signature.
- Raise exceptions from `exceptions.py`, and chain them: `raise ... from err`. Model validation raises `ModelValidationError`, which is also a `ValueError`.
- When catching `DiagralAPIError` to translate a specific error, **re-raise everything else** — falling through leaves the response variable unbound.
- Logging: `_LOGGER = logging.getLogger(__name__)` in `api.py`; `models.py` uses `logger`. Never `print()` in `src/`.
- All I/O is `async`/`await`. No blocking calls.
- **Never log a secret**: password, access token, API key, secret key, PIN code, HMAC signature. Wrap anything that may carry one — headers, request bodies, API responses — in `utils.Redacted(...)` when logging it: values of the keys in `constants.SENSITIVE_KEYS` become `**REDACTED**`, and the copy is only made when the record is formatted. Redact rather than drop the line: users attach debug logs to bug reports. A new secret field name goes into `SENSITIVE_KEYS`; a URL field whose path is a secret (`webhook_url`) goes into `SENSITIVE_URL_PATH_KEYS`, which keeps the scheme and host. When the URL path itself carries a secret (`delete_apikey`), pass `log_endpoint=` to `_request()` with that segment replaced by `REDACTED`.
- Constants live in `constants.py`. No magic strings or numbers inline.

## Contracts with hass-diagral

These are relied on by the integration. Changing any of them is a breaking change and needs a `BREAKING CHANGE:` footer and a coordinated update of hass-diagral.

- **Import paths**, not only `__all__`: hass-diagral imports from `pydiagral`, `pydiagral.api` (`DiagralAPI`), `pydiagral.constants` (`AUTOMATISM_CANALS`, which its diagnostics use to show only known canals), `pydiagral.exceptions` (`AuthenticationError`, `ClientError`, `ConfigurationError`, `DiagralAPIError`, `ModelValidationError`, `PinCodeError`, `ServerError`, `SessionError`, `ValidationError`) and `pydiagral.models` (`AlarmConfiguration`, `Anomalies`, `AnomalyDetail`, `ApiKeyWithSecret`, `DeviceInfos`, `DeviceList`, `Group`, `SystemStatus`, `TryConnectResult`, `Webhook`, `WebHookNotification`, `WebHookNotificationUser`, and the `unexpected_data` function; its tests also import `AnomalyName` and `WebHookNotificationDetail`).
- **`pydiagral.api.BASE_URL` is read at call time.** `_request()` looks the name up in the `api` module on every request, and hass-diagral's fake Diagral cloud reassigns `pydiagral.api.BASE_URL` to redirect traffic. Do not move the lookup to `constants.BASE_URL`, cache it in `__init__`, or bind it as a default argument.
- **Error strings.** hass-diagral matches `"No subscription found for"` in the `DiagralAPIError` raised by `get_webhook()` when no subscription exists — so that 404's message must keep Diagral's detail — and by the webhook register/update actions. `get_anomalies()` returns `{}` when the API answers 404 with `"No anomalies found"`, and hass-diagral relies on that empty result.
- **Every exception the library raises derives from `DiagralAPIError`**, so a single `except DiagralAPIError` covers it. aiohttp errors are wrapped by `_request()`.
- **`request_timeout`** is set by hass-diagral as a ceiling (≥ 60 s); it drives each attempt's deadline below it with `asyncio.timeout()`. Keep it keyword-only and applied to every request.
- **Return values.** hass-diagral uses the `AlarmConfiguration` that `get_configuration()` returns, and the `str | None` from `get_alarm_name()`, `None` when the configuration names no alarm. `Anomalies.created_at` is None when Diagral sends no readable date, and hass-diagral guards it.
- **Diagnostics.** hass-diagral writes `models.unexpected_data()` and `DiagralAPI.response_shapes()` into the diagnostics file users attach to public issues. Neither may ever carry a value a user typed or an identifier: a new value made visible in `utils.shape()` needs the same review as a log line. `unexpected_data()` entries keep their `model`, `field`, `problem` and `value` keys, which hass-diagral copies one by one, so a new key stays out until it is added there. `response_shapes()` stays keyed by read method name.

## Secrets

`.env` holds real Diagral credentials for the maintainer's manual scripts. **Never read, print, copy or commit it**, and never run `example_code.py` or `diag_code.py`: they talk to the real alarm. Tests use the dummy values at the top of `tests/test_pydiagral_api.py`.

## Commands

```bash
# Install — hatchling reads the version from PYPROJECT_VERSION; without it the build fails.
# The dev extra holds pytest, pytest-asyncio, pytest-cov, pytest-html and the pinned ruff.
PYPROJECT_VERSION=0.1.0-dev pip install -e ".[dev]"

# Lint, format and type-check — mypy reads its targets from pyproject.toml
ruff check .
ruff format --check .
mypy

# Tests — asyncio_mode = "auto" is set in pyproject.toml
pytest -v
pytest --cov=src/pydiagral --cov-report=term-missing   # fails under 80%
```

Ruff is pinned once, in the `dev` extra (`ruff==0.17.2`); `lint.yaml` reads the version from there. Bump it there, with the fixes the new release requires. A new ruff release must not be able to turn a green PR red on its own. Ruff takes its target version from `requires-python`. Line length is 88, and `E501` is deliberately ignored. `PLR0917` is ignored because making `DiagralAPI.__init__`'s arguments keyword-only would break callers. `.claude/rules/` is excluded from ruff: ruff also formats Python blocks in Markdown, and those files must stay byte-identical.

mypy is pinned the same way (`mypy==2.4.0`), for the same reason; a bump comes with the fixes it requires.

There is no Makefile and no `requirements*.txt`.

## Python versions

`requires-python = ">= 3.11"` — the floor set by `typing.Self` and `datetime.UTC`. CI tests on 3.14 only, which is what Home Assistant — and so hass-diagral — requires. Do not add code that needs more than 3.11 without raising `requires-python` in the same change.

## CI

| Workflow | Trigger | Purpose |
|---|---|---|
| `lint.yaml` | push on `dev`; PR to `dev`, `beta`, `main`; manual | `ruff` job: `ruff check` + `ruff format --check`, pinned ruff. `mypy` job: `mypy` with the `dev` extra, pinned mypy |
| `pytest.yaml` | PR to `dev`, `beta`, `main`, any path; push on `dev`, paths `src/pydiagral/**`, `tests/**`, `pyproject.toml`; weekly (Monday 01:00); manual, on a chosen branch | pytest on Python 3.14 with the `dev` extra, coverage gate (80%), coverage and test results to Codecov |
| `release_and_doc.yaml` | push on `main`, `beta`; manual | semantic-release (toolchain pinned in `.github/release/`) with GPG-signed release commits, PyPI upload through the Trusted Publisher (OIDC, no token), then MkDocs `build --strict` and `mike deploy` to GitHub Pages when a release was published or `docs/`, `mkdocs.yml` or `overrides/` changed: `main` publishes `/stable/`, the default, and `beta` publishes `/beta/` |
| `semantic-prs.yml` | PR opened / edited / synchronized | validates the PR title against Conventional Commits |
| `labeler.yml` | push on `main`, manual | syncs labels from `.github/labels.yml` |
| `lock-stale.yml` | daily | `lock`: locks issues and PRs inactive for 30 days. `stale`: marks `stale` an issue labelled `waiting-for-response` after 30 days without activity, and closes it 7 days later; `no-stale`, `bug` and `documentation` exempt it. Pull requests are never marked stale |

Dependabot (`.github/dependabot.yml`) checks monthly, targets `dev`, and waits 7 days after a release before proposing it (30 for a pip major). GitHub Actions updates arrive as one grouped PR titled `chore(deps): 🔧 …`. For pip, runtime dependencies use `fix(deps): 🐛` — widening the `aiohttp` range changes published metadata and must release — and the `dev` extra uses `chore(deps-dev): 🔧`. Only constrained requirements get PRs: today `ruff`, `mypy` and `aiohttp`. The semantic-release toolchain (`.github/release/package-lock.json`) arrives as one grouped `chore(deps): 🔧 …` PR; dry-run it before merging, since a release only runs on `beta` and `main`.

Gaps to know about:

- `ruff`, `mypy` and `pytest` are **required checks** on `dev`, `beta` and `main`, so all three run on every PR to those branches. Do not add a path filter to their `pull_request` trigger or drop a branch from it: a PR that never reports a required check can never be merged.
- The MkDocs build only runs on `main` / `beta`. A broken docstring reference is caught there, not on `dev`.
- Codecov is informational (`fail_ci_if_error: false`); the coverage gate is `fail_under` in `pyproject.toml`.

## Branches

| Branch | Role |
|---|---|
| `dev` | Development. **All PRs target this branch.** Dependabot targets it too. |
| `beta` | Prereleases, published by semantic-release (`release.config.cjs`) |
| `main` | Stable releases, published by semantic-release. Repository default. |

Changes flow `dev` → `beta` → `main` through PRs. Never commit or push directly to any of them. Always confirm the current branch with `git branch --show-current` before committing.

Branch protection, identical on the three branches: PR required (no approval, the maintainer is the only reviewer), `ruff`, `mypy` and `pytest` required and up to date, **signed commits required**, conversations resolved, no force-push, **no deletion**. Only merge commits are allowed on the repository — a squash would collapse several `fix` commits into one changelog line. Automatic deletion of head branches is off on purpose; delete feature branches with `gh pr merge --delete-branch`.

- **Every commit must be signed.** Never rewrite commits (`filter-branch`, `rebase`, `commit --amend` on pushed work) without re-signing them, or the PR can no longer be merged without bypassing the rules.
- Release commits are signed in `release_and_doc.yaml` with a dedicated GPG key (`GPG_PRIVATE_KEY`, `GPG_PASSPHRASE` secrets), whose public half is on the maintainer's account.
- Never allow deletion on `dev`, `beta` or `main`: it is also what keeps them from being deleted when they are the head of a promotion PR.

Because `main` is the default branch, a `Closes #N` keyword only fires when the change reaches `main`.

## Commits

```
<type>[optional scope]: <gitmoji> <description>

[optional body — bullet points]

Tests: ✅ N passed, ❌ 0 failed, ⚠️ 0 errors

[optional BREAKING CHANGE: footer, always last]
```

- First line in English, 72 characters maximum. Use backticks for code references.
- Types and gitmoji: `feat` ✨, `fix` 🐛, `docs` 📝, `refactor` ♻️, `test` ✅, `chore` 🔧, `perf` ⚡, `ci` 🔧. Removing code or files uses 🔥. `semantic-prs.yml` accepts `feat|fix|docs|test|ci|refactor|perf|chore`.
- Scope is the module filename without extension (`api`, `models`, `exceptions`, `utils`), or the area: `tests`, `deps`, `workflow`, `devcontainer`, `readme`, `index`…
- The `Tests:` line is required whenever `src/` or `tests/` changed. Use `Tests: N/A (no src or tests change)` otherwise.
- The body explains **why**. Never restate what the diff already shows.
- A breaking change to a contract listed above takes a `BREAKING CHANGE:` footer, after the `Tests:` line. The commit parser appends every following line to the note, so a `Tests:` line placed after it ends up in the release notes.
- Keep issue and PR references (`#N`, `owner/repo#N`) out of a `BREAKING CHANGE:` paragraph. The commit parser ends the note at the first line that holds one and drops that line from the release notes. Put the reference in the body instead.
- Never write a closing keyword (`close`, `fix`, `resolve` and their forms) before an issue number in a commit message or PR body, even in quotes, unless that pydiagral issue should close. GitHub closes it when the commit reaches `main`, and at release time the semantic-release GitHub plugin looks up every such number and fails the release when one does not exist. To quote one, put it in backticks, which its parser skips.

`release.config.cjs` uses semantic-release's default (Angular) presets: only `feat`, `fix` and `perf` — plus reverts and breaking changes — trigger a release and appear in `CHANGELOG.md`. A `docs`, `refactor` or `chore` commit is invisible to users and to PyPI.

The changelog credits contributors: an author other than the maintainer appears as `(by …)`, and each `Co-authored-by:` trailer as `(co-authored by …)` — a GitHub login when the address is a noreply one, the name otherwise, never an e-mail address, and never an assistant or a bot. When carrying over someone else's work, add `Co-authored-by: Name <id+login@users.noreply.github.com>` so they are credited.

The pre-commit gate and the PR description template live in the `git-conventions` skill.

## Pull requests

- Title follows the commit format; `semantic-prs.yml` enforces it.
- Target `dev`, always.
- Run the full suite and both ruff commands before opening. Fix everything first.
- Describe what changed and why, and how it was verified.
- Before merging a contributor's PR, read every commit message, not only the diff: a `BREAKING CHANGE:` footer anywhere in the branch makes the next release a major, and it cannot be taken back once merged. Ask for it to be removed if the change is not breaking for callers.

## Testing

- Never make a real call to the Diagral cloud.
- **Method tests mock `DiagralAPI._request`** with `AsyncMock`, returning `(body, status)` tuples. **Tests of `_request` itself mock the transport** (`aiohttp`), since that is the code under test.
- `asyncio_mode = "auto"`: `@pytest.mark.asyncio` is not needed. Existing tests carry it; new ones may omit it.
- **After every change to `src/pydiagral/*.py`**, review `tests/test_pydiagral_api.py` and create, update or delete tests accordingly. Never skip this.
- For a bug fix, write the failing test first, confirm it fails for the right reason, then fix.
- Cover the error path, not only the nominal one.

The patterns are in the `testing-pydiagral` skill.

## Documentation

The reference pages (`docs/api.md`, `models.md`, `exceptions.md`) are generated by mkdocstrings from the docstrings. **A docstring change is a documentation change.** Hand-written content is `docs/index.md` and `README.md`; update them when a feature or requirement changes. See the `docs-pydiagral` skill.

Docstrings follow the Google style (`Args:`, `Returns:`, `Raises:`), which mkdocstrings renders. Ruff's `D` rules require a docstring on every public object but set no `convention`, so they do not check the sections. The Sphinx style (`:param:`) is not parsed: it shows as raw text.

Examples go under an `Examples:` section, plural: griffe renders its `>>>` lines as code, while an `Example:` section becomes a box of plain Markdown, where `>>>` reads as nested quotes and the lines run together. Any other unknown section (`Warning:`, `Note:`) also becomes a box of that kind. The `Examples:` blocks of `models.py` and `utils.py` run as doctests with the suite (`testpaths` and `--doctest-modules` in `pyproject.toml`): an example that no longer matches the code fails `pytest`. A module added to the docs with examples goes into `testpaths` too.

## Comments

Explain why, never what. One short line stating a non-obvious constraint, or no comment at all. Do not restate the following line, do not justify a change by describing what the code looked like before, and do not add section dividers.
