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
| Run `mypy` / `pyright` after editing | No type checker is configured yet. `mypy src/pydiagral` reports 33 errors today, and the package ships no `py.typed` marker. Adding both is planned as separate work; until then, keep annotations complete and accurate rather than silencing anything. |
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
- Type hints use PEP 604 (`str | None`) and `list[...]` / `dict[...]`. Annotate every function signature.
- Raise exceptions from `exceptions.py`, and chain them: `raise ... from err`. Model validation raises `ModelValidationError`, which is also a `ValueError`.
- When catching `DiagralAPIError` to translate a specific error, **re-raise everything else** — falling through leaves the response variable unbound.
- Logging: `_LOGGER = logging.getLogger(__name__)` in `api.py`; `models.py` uses `logger`. Never `print()` in `src/`.
- All I/O is `async`/`await`. No blocking calls.
- **Never log a secret**: password, access token, API key, secret key, PIN code, HMAC signature. Wrap anything that may carry one — headers, request bodies, API responses — in `utils.Redacted(...)` when logging it: values of the keys in `constants.SENSITIVE_KEYS` become `**REDACTED**`, and the copy is only made when the record is formatted. Redact rather than drop the line: users attach debug logs to bug reports. A new secret field name goes into `SENSITIVE_KEYS`.
- Constants live in `constants.py`. No magic strings or numbers inline.

## Contracts with hass-diagral

These are relied on by the integration. Changing any of them is a breaking change and needs a `BREAKING CHANGE:` footer and a coordinated update of hass-diagral.

- **Import paths**, not only `__all__`: hass-diagral imports from `pydiagral`, `pydiagral.api`, `pydiagral.exceptions` and `pydiagral.models` (`AlarmConfiguration`, `Anomalies`, `AnomalyDetail`, `ApiKeyWithSecret`, `DeviceInfos`, `DeviceList`, `Group`, `SystemStatus`, `TryConnectResult`, `Webhook`, `WebHookNotification`, `WebHookNotificationUser`).
- **`pydiagral.api.BASE_URL` is read at call time.** `_request()` looks the name up in the `api` module on every request, and hass-diagral's fake Diagral cloud reassigns `pydiagral.api.BASE_URL` to redirect traffic. Do not move the lookup to `constants.BASE_URL`, cache it in `__init__`, or bind it as a default argument.
- **Error strings.** hass-diagral matches `"No subscription found for"` in the `DiagralAPIError` raised by the webhook actions. `get_anomalies()` returns `{}` when the API answers 404 with `"No anomalies found"`, and hass-diagral relies on that empty result.
- **Every exception the library raises derives from `DiagralAPIError`**, so a single `except DiagralAPIError` covers it. aiohttp errors are wrapped by `_request()`.
- **Return values used despite their annotation.** `get_configuration()` is annotated `-> None` but returns the `AlarmConfiguration`, and hass-diagral uses it. Fix the annotation, never the return.

## Secrets

`.env` holds real Diagral credentials for the maintainer's manual scripts. **Never read, print, copy or commit it**, and never run `example_code.py` or `diag_code.py`: they talk to the real alarm. Tests use the dummy values at the top of `tests/test_pydiagral_api.py`.

## Commands

```bash
# Install — hatchling reads the version from PYPROJECT_VERSION; without it the build fails.
# The dev extra holds pytest, pytest-asyncio, pytest-cov, pytest-html and the pinned ruff.
PYPROJECT_VERSION=0.1.0-dev pip install -e ".[dev]"

# Lint and format
ruff check .
ruff format --check .

# Tests — asyncio_mode = "auto" is set in pyproject.toml
pytest -v
pytest --cov=src/pydiagral --cov-report=term-missing   # fails under 80%
```

CI pins `ruff==0.17.2`, the same version as the `dev` extra; bump both together, with the fixes the new release requires. A new ruff release must not be able to turn a green PR red on its own. Ruff takes its target version from `requires-python`. Line length is 88, and `E501` is deliberately ignored. `PLR0917` is ignored because making `DiagralAPI.__init__`'s arguments keyword-only would break callers. `.claude/rules/` is excluded from ruff: ruff also formats Python blocks in Markdown, and those files must stay byte-identical.

There is no Makefile and no `requirements*.txt`.

## Python versions

`requires-python = ">= 3.11"` — the floor set by `typing.Self` and `datetime.UTC`. CI tests on 3.14 only, which is what Home Assistant — and so hass-diagral — requires. Do not add code that needs more than 3.11 without raising `requires-python` in the same change.

## CI

| Workflow | Trigger | Purpose |
|---|---|---|
| `lint.yaml` | push on `dev`; PR to `dev`, `beta`, `main`; manual | `ruff check` + `ruff format --check`, pinned ruff |
| `pytest.yaml` | PR to `dev`, any path; push on `dev`, paths `src/pydiagral/**`, `tests/**`, `pyproject.toml`; weekly (Monday 01:00); manual, on a chosen branch | pytest on Python 3.14 with the `dev` extra, coverage gate (80%), coverage and test results to Codecov |
| `release_and_doc.yaml` | push on `main`, `beta`; manual | semantic-release, PyPI upload, then MkDocs `build --strict` to GitHub Pages when a release was published or `docs/` / `mkdocs.yml` changed |
| `semantic-prs.yml` | PR opened / edited / synchronized | validates the PR title against Conventional Commits |
| `labeler.yml` | push on `main`, manual | syncs labels from `.github/labels.yml` |
| `lock.yml` | daily | locks issues and PRs inactive for 30 days |

Gaps to know about:

- `ruff` and `pytest` are **required checks** on `dev`, so both run on every PR. Do not add a path filter to their `pull_request` trigger: a PR that never reports a required check can never be merged.
- The MkDocs build only runs on `main` / `beta`. A broken docstring reference is caught there, not on `dev`.
- Codecov is informational (`fail_ci_if_error: false`); the coverage gate is `fail_under` in `pyproject.toml`.

## Branches

| Branch | Role |
|---|---|
| `dev` | Development. **All PRs target this branch.** Dependabot targets it too. |
| `beta` | Prereleases, published by semantic-release (`.releaserc`) |
| `main` | Stable releases, published by semantic-release. Repository default. |

Changes flow `dev` → `beta` → `main` through PRs. Never commit or push directly to `beta` or `main`. Always confirm the current branch with `git branch --show-current` before committing.

Because `main` is the default branch, a `Closes #N` keyword only fires when the change reaches `main`.

## Commits

```
<type>[optional scope]: <gitmoji> <description>

[optional body — bullet points]

Tests: ✅ N passed, ❌ 0 failed, ⚠️ 0 errors
```

- First line in English, 72 characters maximum. Use backticks for code references.
- Types and gitmoji: `feat` ✨, `fix` 🐛, `docs` 📝, `refactor` ♻️, `test` ✅, `chore` 🔧, `perf` ⚡, `ci` 🔧. Removing code or files uses 🔥. `semantic-prs.yml` accepts `feat|fix|docs|test|ci|refactor|perf|chore`.
- Scope is the module filename without extension (`api`, `models`, `exceptions`, `utils`), or the area: `tests`, `deps`, `workflow`, `devcontainer`, `readme`, `index`…
- The `Tests:` line is required whenever `src/` or `tests/` changed. Use `Tests: N/A (no src or tests change)` otherwise.
- The body explains **why**. Never restate what the diff already shows.
- A breaking change to a contract listed above takes a `BREAKING CHANGE:` footer.

`.releaserc` uses semantic-release's default (Angular) presets: only `feat`, `fix` and `perf` — plus reverts and breaking changes — trigger a release and appear in `CHANGELOG.md`. A `docs`, `refactor` or `chore` commit is invisible to users and to PyPI.

The pre-commit gate and the PR description template live in the `git-conventions` skill.

## Pull requests

- Title follows the commit format; `semantic-prs.yml` enforces it.
- Target `dev`, always.
- Run the full suite and both ruff commands before opening. Fix everything first.
- Describe what changed and why, and how it was verified.

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

Docstrings follow the Google style (`Args:`, `Returns:`, `Raises:`), which mkdocstrings renders. Ruff's `D` rules require a docstring on every public object but set no `convention`, so they do not check the sections. `exceptions.py` still uses `:param:`; do not spread it.

## Comments

Explain why, never what. One short line stating a non-obvious constraint, or no comment at all. Do not restate the following line, do not justify a change by describing what the code looked like before, and do not add section dividers.
