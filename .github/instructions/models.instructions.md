---
description: "Use when adding or modifying data models in pydiagral models.py. Covers CamelCaseModel inheritance, dataclass decoration, field aliasing, and type hint conventions."
applyTo: "src/pydiagral/models.py"
---

# Model Guidelines — pydiagral

## Structure obligatoire

Chaque modèle doit :

1. Hériter de `CamelCaseModel`
2. Être décoré avec `@dataclass`

```python
from dataclasses import dataclass, field
from .models import CamelCaseModel

@dataclass
class MyModel(CamelCaseModel):
    my_field: str
    count: int
```

## Aliasing de champs

Quand le nom Python (snake_case) diffère du nom JSON de l'API (camelCase non standard ou abréviation) :

```python
@dataclass
class MyModel(CamelCaseModel):
    device_id: str = field(metadata={"alias": "devId"})
    is_active: bool = field(metadata={"alias": "active"})
```

> `CamelCaseModel` gère automatiquement la conversion `snake_case` ↔ `camelCase` standard — n'utiliser `alias` que pour les cas non-standard.

## Type hints

- Syntaxe PEP 604 : `str | None` (pas `Optional[str]`)
- Listes : `list[str]`, `list[MyModel]`
- Dicts : `dict[str, Any]`
- Python ≥ 3.10 — pas besoin d'importer `Optional` ou `Union`

## Valeurs par défaut

```python
@dataclass
class MyModel(CamelCaseModel):
    name: str
    items: list[str] = field(default_factory=list)
    optional_field: str | None = None
```
