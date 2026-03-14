---
name: add-api-method
description: 'Add a complete new method to DiagralAPI in pydiagral. Use when implementing a new Diagral API endpoint: creates the async method in api.py, the response dataclass in models.py, updates __init__.py exports if needed, and writes pytest tests mocking _request(). Triggers: "add method", "new endpoint", "implement API call", "add support for".'
argument-hint: 'Describe the API method to add (e.g., "get webhooks", "activate zone 2")'
---

# Add API Method — pydiagral

Workflow complet pour ajouter une nouvelle méthode à `DiagralAPI` : modèle de données, méthode async, exports et tests.

## When to Use

- Implémenter un nouvel endpoint de l'API Diagral
- Ajouter une action système (activer/désactiver une zone, déclencher un automatisme…)
- Étendre `DiagralAPI` avec une nouvelle capacité de lecture ou d'écriture

## Information to Gather First

Avant de coder, collecter :

1. **Endpoint** : méthode HTTP (`GET`/`POST`/…) + chemin relatif (ex. `alarm/{serial_id}/status`)
2. **Corps de la requête** (si applicable) : champs et types
3. **Schéma de la réponse** : champs JSON retournés par l'API
4. **Authentification** : requiert-elle la signature HMAC ? (en général oui — voir `utils.generate_hmac_signature`)
5. **Nom Python souhaité** pour la méthode (snake_case)

Si ces informations ne sont pas fournies, les demander à l'utilisateur ou inférer depuis la documentation dans `docs/api.md`.

## Procedure

### 1. Créer ou étendre le modèle de données (`models.py`)

- Hériter de `CamelCaseModel` et décorer avec `@dataclass`
- Un champ dont le nom API diffère du nom Python → `field(metadata={"alias": "apiFieldName"})`
- Exemple :
  ```python
  @dataclass
  class MyResponse(CamelCaseModel):
      my_field: str
      other_id: int = field(metadata={"alias": "otherId"})
  ```

### 2. Ajouter la méthode dans `DiagralAPI` (`api.py`)

- Toujours `async def`, retour typé, docstring Google obligatoire
- Appeler exclusivement `self._request()` pour les requêtes HTTP
- Pattern minimal :

  ```python
  async def get_something(self) -> MyResponse:
      """Retrieve something from the API.

      Returns:
          MyResponse: The response data.

      Raises:
          AuthenticationError: If not authenticated.
          ServerError: On 5xx responses.
      """
      response = await self._request("GET", f"alarm/{self.serial_id}/something")
      return MyResponse.from_dict(response)
  ```

- Pour les méthodes nécessitant la signature HMAC, utiliser `generate_hmac_signature` depuis `utils.py`

### 3. Mettre à jour les exports (`__init__.py`)

- Si le nouveau modèle doit être accessible par les utilisateurs de la bibliothèque, l'ajouter dans `__all__` et l'import de `__init__.py`
- Les exceptions internes n'ont pas besoin d'être exportées

### 4. Écrire les tests (`tests/test_pydiagral_api.py`)

Pour chaque méthode, écrire **deux tests minimum** :

**Test nominal** :

```python
@pytest.mark.asyncio
@patch("pydiagral.api.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_something(mock_request):
    mock_request.return_value = {"myField": "value", "otherId": 42}
    async with DiagralAPI(...) as diagral:
        result = await diagral.get_something()
    assert result.my_field == "value"
    mock_request.assert_called_once_with("GET", "alarm/.../something")
```

**Test erreur** (au moins un chemin d'exception) :

```python
@pytest.mark.asyncio
@patch("pydiagral.api.DiagralAPI._request", new_callable=AsyncMock)
async def test_get_something_auth_error(mock_request):
    mock_request.side_effect = AuthenticationError("Unauthorized")
    async with DiagralAPI(...) as diagral:
        with pytest.raises(AuthenticationError):
            await diagral.get_something()
```

- Charger les réponses complexes depuis `tests/data/<fixture>.json` via `json.load()`

### 5. Vérifier la qualité

```bash
ruff check --output-format=github --verbose
pytest -v --html=report.html --self-contained-html
```

- Corriger toutes les erreurs Ruff avant de considérer la tâche terminée
- S'assurer que tous les tests passent

## Checklist de complétion

- [ ] Modèle `@dataclass` héritant de `CamelCaseModel` créé dans `models.py`
- [ ] Méthode `async def` avec docstring Google ajoutée dans `api.py`
- [ ] Export dans `__init__.py` si le modèle est public
- [ ] Test nominal + test d'erreur dans `test_pydiagral_api.py`
- [ ] `ruff check` sans erreur
- [ ] `pytest` passe sans régression
