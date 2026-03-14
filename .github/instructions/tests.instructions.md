---
description: "Use when writing, editing, or reviewing tests for pydiagral. Covers mocking strategy, async test patterns, fixture loading, and required test coverage."
applyTo: "tests/**"
---

# Test Guidelines — pydiagral

## Mocking

- **Toujours mocker `DiagralAPI._request`** avec `unittest.mock.AsyncMock` et `@patch` — ne jamais mocker `aiohttp` directement
- Import requis :
  ```python
  from unittest.mock import AsyncMock, patch
  ```
- Pattern type :
  ```python
  @pytest.mark.asyncio
  @patch("pydiagral.api.DiagralAPI._request", new_callable=AsyncMock)
  async def test_my_method(mock_request):
      mock_request.return_value = {"field": "value"}
      async with DiagralAPI(...) as diagral:
          result = await diagral.my_method()
      mock_request.assert_called_once_with("GET", "expected/endpoint")
  ```

## Async

- Décorer chaque test async avec `@pytest.mark.asyncio`
- Utiliser `async with DiagralAPI(...) as diagral:` — toujours via le context manager

## Fixtures JSON

- Stocker les réponses API complexes dans `tests/data/<nom>.json`
- Charger avec :
  ```python
  import json, pathlib
  data = json.loads((pathlib.Path("tests/data/my_fixture.json")).read_text())
  mock_request.return_value = data
  ```

## Couverture minimale

Pour chaque méthode publique de `DiagralAPI`, écrire **au minimum** :

1. Un test nominal (retour attendu, `assert_called_once_with`)
2. Un test d'erreur (ex. `AuthenticationError`, `ServerError`) avec `mock_request.side_effect`
