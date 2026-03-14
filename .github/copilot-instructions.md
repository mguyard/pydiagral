# Project Guidelines — pydiagral

`pydiagral` est une bibliothèque Python asynchrone pour interagir avec le système d'alarme Diagral via son API REST officielle.

## Architecture

```
src/pydiagral/
├── api.py          # DiagralAPI — classe publique principale (async context manager)
├── models.py       # Dataclasses : CamelCaseModel base + toutes les entités API
├── exceptions.py   # Hiérarchie d'exceptions (DiagralAPIError → sous-classes)
├── constants.py    # BASE_URL, API_VERSION
└── utils.py        # generate_hmac_signature() — signature HMAC-SHA256
tests/
├── test_pydiagral_api.py   # Suite de tests principale
└── data/                   # Fixtures JSON (configuration_sample.json, …)
```

- **Un seul point d'entrée public** : `DiagralAPI` (exporté via `__init__.py`)
- La méthode privée `_request()` centralise tous les appels HTTP et la gestion d'erreurs HTTP → ne pas contourner
- `CamelCaseModel` gère la conversion snake_case ↔ camelCase pour tous les modèles

## Build & Test

```bash
# Installation en mode développement
pip install -e ".[dev]"

# Lancer les tests
pytest -v --html=report.html --self-contained-html

# Linter (Ruff)
ruff check --output-format=github --verbose
```

La configuration complète de Ruff est dans [pyproject.toml](../pyproject.toml). Ne pas désactiver de règles sans raison explicite.

## Conventions de code

**Async** : toutes les méthodes publiques de `DiagralAPI` sont `async def`. Utiliser `aiohttp.ClientSession` exclusivement pour les requêtes HTTP.

**Type hints** : syntaxe PEP 604 (`str | None`), annotations complètes sur toutes les fonctions et méthodes.

**Docstrings** : style Google (sections `Args:`, `Returns:`, `Raises:`). Obligatoires sur toutes les classes et méthodes publiques.

**Logging** : logger module `_LOGGER = logging.getLogger(__name__)`. Obfusquer les données sensibles (ex. : `...%s` pour les 4 derniers caractères d'une clé).

**Gestion d'erreurs** : utiliser la hiérarchie d'exceptions définie dans `exceptions.py`. Mapper les codes HTTP → exceptions dans `_request()`. Chaîner avec `raise ... from e`.

**Modèles** : hériter de `CamelCaseModel`, décorer avec `@dataclass`. Pour les champs dont le nom diffère de l'API : `field(metadata={"alias": "apiFieldName"})`.

## Tests

- Framework : `pytest` + `pytest-asyncio` (`@pytest.mark.asyncio`)
- **Mocker `_request()`** avec `unittest.mock.AsyncMock` et `@patch` — ne pas mocker `aiohttp` directement
- Charger les fixtures JSON depuis `tests/data/` pour simuler les réponses API
- Tester systématiquement les chemins d'erreur (exceptions) en plus des cas nominaux

## Commits

Format Conventional Commits + gitmoji, défini dans [copilot-commit-message-instructions.md](./copilot-commit-message-instructions.md).

## Documentation

- Référence API : [docs/api.md](../docs/api.md)
- Modèles de données : [docs/models.md](../docs/models.md)
- Exceptions : [docs/exceptions.md](../docs/exceptions.md)
- Changelog : [CHANGELOG.md](../CHANGELOG.md)
