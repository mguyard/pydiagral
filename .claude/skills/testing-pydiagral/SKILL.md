---
name: testing-pydiagral
description: Test setup for pydiagral — installing, running pytest and coverage, the _request() mocking pattern, testing _request() itself, fixtures, the ruff gate, and the mandatory test impact analysis.
---

# Testing — pydiagral

Use this skill for any task that runs, writes or reviews tests.

---

## 1. Layout

```
tests/
├── __init__.py
├── test_pydiagral_api.py      # The whole suite — 58 tests, grouped by banner comments
└── data/
    ├── configuration_sample.json
    └── system_details_sample.json
```

There is no `conftest.py`. Shared constants (`USERNAME`, `PASSWORD`, `SERIAL_ID`, `API_KEY`, `SECRET_KEY`, `PIN_CODE`, `FAKE_TOKEN`, `WEBHOOK_URL`) and the `load_sample(file_name)` helper are at the top of the test module. They are dummies — never replace them with real values.

---

## 2. Running

```bash
python3 -m venv .venv && . .venv/bin/activate
PYPROJECT_VERSION=0.1.0-dev pip install -e ".[dev]" pytest-cov pytest-html ruff

pytest -v
pytest --cov=src/pydiagral --cov-report=term-missing
```

- `PYPROJECT_VERSION` is required: hatchling takes the version from it.
- `pytest-cov`, `pytest-html` and `ruff` are not in the `dev` extra.
- `pyproject.toml` sets `asyncio_mode = "auto"`.

CI (`pytest.yaml`) runs on Python 3.14 with `--cov=src/pydiagral --cov-report=xml --junitxml=junit.xml --html=report.html`, only when `src/pydiagral/**` changes. Run the suite locally when only `tests/` changed.

> **This section is the canonical source for running tests.** `git-conventions` refers to it.

---

## 3. Testing a `DiagralAPI` Method — mock `_request`

```python
@pytest.mark.asyncio
@patch("pydiagral.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_system_status(mock_request):
    """Test that get_system_status returns the parsed SystemStatus."""
    mock_request.side_effect = [
        ({"access_token": FAKE_TOKEN}, 200),                  # login
        ({"status": "OFF", "activated_groups": []}, 200),     # get_system_status
    ]
    async with DiagralAPI(
        username=USERNAME,
        password=PASSWORD,
        serial_id=SERIAL_ID,
        apikey=API_KEY,
        secret_key=SECRET_KEY,
        pincode=PIN_CODE,
    ) as diagral:
        await diagral.login()
        system_status = await diagral.get_system_status()

    assert system_status.status == "OFF"
    method, endpoint = mock_request.call_args.args
    assert (method, endpoint) == ("GET", f"systems/{SERIAL_ID}/status")
    assert mock_request.call_args.kwargs["headers"]["X-PIN-CODE"] == PIN_CODE
```

- The patch target used across the suite is **`pydiagral.DiagralAPI._request`**. It is the same class object as `pydiagral.api.DiagralAPI`; keep one spelling.
- `_request` returns a **tuple** `(body, status)` — every mocked value is a tuple.
- `side_effect` as a list: one entry per `_request` call, in order. Most tests call `login()` first.
- To simulate an API error, put the exception in the list: `side_effect = [({"access_token": FAKE_TOKEN}, 200), DiagralAPIError("...", status_code=404)]`.
- Always use `async with DiagralAPI(...)` — `_request` requires the session `__aenter__` creates.
- Existing tests rarely assert on the request made. New tests should: a wrong endpoint or a missing header is exactly what a mocked response cannot catch.
- Private state is read through name mangling, `diagral._DiagralAPI__access_token`, with `# noqa: SLF001`.

---

## 4. Testing `_request` Itself — mock the transport

`_request` maps HTTP status codes to exceptions and wraps `aiohttp` errors. Mocking it, as in §3, means it is never executed — which is why `api.py` coverage is 66%. Test it by mocking what it calls, for instance `session.request`:

```python
class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def json(self):
        return self._body

    async def text(self):
        return str(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_request_401_raises_authentication_error():
    """Test that a 401 response raises AuthenticationError with the server detail."""
    async with DiagralAPI(username=USERNAME, password=PASSWORD, serial_id=SERIAL_ID) as diagral:
        with patch.object(diagral.session, "request", return_value=_FakeResponse(401, {"detail": "expired"})):
            with pytest.raises(AuthenticationError, match="expired"):
                await diagral._request("GET", "users/me")  # noqa: SLF001
```

Cover each mapped status (400, 401, 403, 404 with `status_code`, 422, 500, 503, other ≥ 400), `aiohttp.ContentTypeError`, `aiohttp.ClientError`, and the URL built from `pydiagral.api.BASE_URL` (a contract with hass-diagral — see `AGENTS.md`). If a new test dependency such as `aioresponses` is preferred, add it to the `dev` extra and to `pytest.yaml` in the same change.

---

## 5. Fixtures

Large responses live in `tests/data/<name>.json`, loaded with `load_sample("<name>.json")`. Fixtures are synthetic: never paste a captured real response without replacing the serial, names, e-mail addresses and URLs.

---

## 6. Test Impact Analysis (Mandatory)

Every time a file in `src/pydiagral/*.py` is created or modified, before finishing the task:

1. **Read** the tests covering the changed functions in `tests/test_pydiagral_api.py`
2. **For each function or class added, changed or removed**, decide:
   - `CREATE` — new behaviour needs a test
   - `UPDATE` — an existing test no longer reflects the logic
   - `DELETE` — the code is gone and the test is dead
3. **Apply** the changes — never skip silently
4. **Run** the suite (§2)

For a bug fix, write the test first and watch it fail for the right reason. A test that passes against the unfixed code proves nothing.

---

## 7. Ruff Gate

```bash
ruff check .
ruff format --check .
```

CI runs only `ruff check`, through `chartboost/ruff-action@v1` without a pinned version. A finding that appears with no code change comes from a ruff release, not from your diff — report it rather than silencing it.

---

## 8. Rules

- Never make a real call to the Diagral cloud, and never run `example_code.py` or `diag_code.py`.
- Nominal path and error path for every public method.
- Name tests `test_<method>_<condition>` — e.g. `test_get_system_status_without_pincode`.
- Prefer `pytest.mark.parametrize` with `ids` over near-identical functions, for new tests.
- Docstrings on test functions are required by ruff's `D` rules.
