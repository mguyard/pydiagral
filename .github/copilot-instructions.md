# Project Guidelines — pydiagral

## Project Context

- **Project Type:** Asynchronous Python library for interacting with the Diagral alarm system via its official REST API.
- **Public API:** A single entry point — the `DiagralAPI` class — exported via `__init__.py`.
- **Language:** All code, comments, and docstrings must be in **English**.
- **Documentation:** Files in `docs/` must use the `docs` commit type. Documentation is in Markdown.

## Architecture

```
src/pydiagral/
├── api.py          # DiagralAPI — main public class (async context manager)
├── models.py       # Dataclasses: CamelCaseModel base + all API entities
├── exceptions.py   # Exception hierarchy (DiagralAPIError → subclasses)
├── constants.py    # BASE_URL, API_VERSION
└── utils.py        # generate_hmac_signature() — HMAC-SHA256 signature
tests/
├── test_pydiagral_api.py   # Main test suite
└── data/                   # JSON fixtures (configuration_sample.json, …)
```

**Key patterns:**

- The private method `_request()` centralizes all HTTP calls and HTTP error handling → never bypass it.
- `CamelCaseModel` handles bidirectional snake_case ↔ camelCase conversion for all models.
- All Diagral API calls go through the `DiagralAPI` class — never call the Diagral API directly.

## Build & Test

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest -v --html=report.html --self-contained-html

# Linter (Ruff)
ruff check --output-format=github --verbose
```

Full Ruff configuration is in [pyproject.toml](../pyproject.toml). Do not disable rules without explicit justification.

## Code Conventions

**Async:** All public methods of `DiagralAPI` are `async def`. Use `aiohttp.ClientSession` exclusively for HTTP requests.

**Type hints:** PEP 604 syntax (`str | None`), full annotations on all functions and methods.

**Docstrings:** Google style (`Args:`, `Returns:`, `Raises:` sections). Required on all public classes and methods.

**Logging:** Module-level logger `_LOGGER = logging.getLogger(__name__)`. Obfuscate sensitive data (e.g., `...%s` for the last 4 characters of a key).

**Error handling:** Use the exception hierarchy defined in `exceptions.py`. Map HTTP status codes → exceptions in `_request()`. Chain with `raise ... from e`.

**Models:** Inherit from `CamelCaseModel`, decorate with `@dataclass`. For fields whose name differs from the API: `field(metadata={"alias": "apiFieldName"})`.

## Tests

- Framework: `pytest` + `pytest-asyncio` (`@pytest.mark.asyncio`)
- **Mock `_request()`** with `unittest.mock.AsyncMock` and `@patch` — never mock `aiohttp` directly.
- Load JSON fixtures from `tests/data/` to simulate API responses.
- **Whenever any `src/pydiagral/*.py` file is created or modified, immediately analyse `tests/test_pydiagral_api.py` and CREATE, UPDATE, or DELETE tests as needed. Never skip this step silently.**
- Always test error paths (exceptions) in addition to nominal cases.

## CI/CD

| Workflow               | Trigger                           | Purpose                   |
| ---------------------- | --------------------------------- | ------------------------- |
| `lint.yaml`            | push `dev` / PR to `main`, `beta` | Ruff linting              |
| `pytest.yaml`          | push `dev` / PR to `main`, `beta` | pytest + Codecov upload   |
| `release_and_doc.yaml` | tag push                          | semantic-release + MkDocs |

**Branch strategy:** `dev` is the development branch. `beta` is pre-release. `main` is stable. All PRs must target `dev`.

## Pull Request Best Practices

- **Title:** Must follow the same format as commit messages: `<type>[optional scope]: <gitmoji> <description>`
- **Description:** Must provide a clear summary of all changes. For each commit, include a brief explanation and a direct link to the commit SHA. Reference issues with GitHub keywords (e.g., `Closes #123`).
- **Base branch:** All PRs must target `dev`.

## Commit Message Guidelines

Full specification in [copilot-commit-message-instructions.md](./copilot-commit-message-instructions.md).

**Types and gitmoji:**

- `feat`: ✨ — New features
- `fix`: 🐛 — Bug fixes
- `docs`: 📝 — Documentation changes
- `refactor`: ♻️ — Refactoring without adding features or fixing bugs
- `test`: ✅ — Adding or updating tests
- `chore`: 🔧 — Maintenance, build, or tooling changes

## Python Best Practices

- Use `async`/`await` for all I/O-bound operations.
- Handle exceptions gracefully and log errors using `_LOGGER`.
- Prefer list comprehensions and generator expressions for concise code.
- Use constants from `constants.py` for configuration values — avoid magic strings.
- Avoid global variables.

## For Copilot Coding Agent

- All code, comments, and docstrings must be in **English**.
- When generating commit messages or PR titles, follow the Conventional Commits + gitmoji rules above.
- After every code change in `src/pydiagral/*.py`, analyse `tests/test_pydiagral_api.py` and CREATE, UPDATE, or DELETE tests as needed. Never skip this step.
- Enforce Ruff linting — run `ruff check` after any code change and fix all errors before considering the task done.
- Never bypass `_request()` for HTTP calls.
- New public models must be exported via `__init__.py` if intended for library consumers.

## Documentation

- API Reference: [docs/api.md](../docs/api.md)
- Data Models: [docs/models.md](../docs/models.md)
- Exceptions: [docs/exceptions.md](../docs/exceptions.md)
- Changelog: [CHANGELOG.md](../CHANGELOG.md)

---

These instructions are designed to help GitHub Copilot and Copilot Coding Agent generate code, documentation, and commit messages consistent with the project's standards and best practices.
