---
name: docs-pydiagral
description: Documentation for pydiagral — MkDocs Material with mkdocstrings, docstrings as the API reference, the hand-written pages, local build with --strict, and when docs must change.
---

# Documentation — pydiagral

Use this skill for any change to docstrings, `docs/`, `mkdocs.yml` or `README.md`.

---

## 1. How the Site Is Built

- [MkDocs](https://www.mkdocs.org/) with the Material theme and [mkdocstrings](https://mkdocstrings.github.io/) (`default_handler: python`), configured in `mkdocs.yml`.
- Published to GitHub Pages ([mguyard.github.io/pydiagral](https://mguyard.github.io/pydiagral/)) by `release_and_doc.yaml`, on a push to `main` or `beta`, when a release was published or `docs/` / `mkdocs.yml` changed.
- Built with `mkdocs build --strict`: any warning fails the deployment.

Check mkdocs-material and mkdocstrings options with Context7 before using one; do not rely on memory.

---

## 2. Pages

| Page | Content |
|---|---|
| `docs/index.md` | Hand-written: requirements, features, installation, usage |
| `docs/api.md` | `::: pydiagral.api` — generated |
| `docs/models.md` | `::: pydiagral.models` — generated |
| `docs/exceptions.md` | `::: pydiagral.exceptions` — generated |

The generated pages are wrapped in `<!-- prettier-ignore-start -->` / `<!-- prettier-ignore-end -->` so that Prettier does not reflow the `:::` options. Keep the markers.

A new page must be added to `nav` in `mkdocs.yml`, or `--strict` fails on it.

`README.md` is the PyPI and GitHub landing page and overlaps `docs/index.md`. When a feature list, requirement or usage example changes, update both.

---

## 3. Docstrings Are the API Reference

- Google style: summary line, blank line, then `Args:`, `Returns:`, `Raises:` (and `Attributes:` on models).
- Document every exception a public method can raise, including those raised by `_request()` that the caller is expected to handle.
- Use backticks for code. A cross-reference to another object is `[Name][pydiagral.models.Name]`.
- Never put real values in examples: no serial, e-mail, key or PIN.
- Put examples under `Examples:`, plural. `Example:` is rendered as a box of plain text, where `>>>` lines become nested quotes on a single line.
- `models.py` and `utils.py` examples run as doctests: write them as a session would print them (`print()` output without quotes, every name defined in the example).

---

## 4. Building Locally

```bash
PYPROJECT_VERSION=0.1.0-dev pip install -e . mkdocs "mkdocstrings[python]" mkdocs-material
mkdocs build --strict
mkdocs serve        # http://127.0.0.1:8000
```

`--strict` is the only check that catches a broken docstring before `beta`. Run it whenever a docstring, `docs/` or `mkdocs.yml` changed. `site/` is git-ignored.

---

## 5. When to Update

After any change to the public behaviour — a method, a model field, an exception, a requirement:

1. Docstrings in the changed code — always.
2. `docs/index.md` and `README.md` — if the feature list, requirements or usage changed.
3. When in doubt, ask with `AskUserQuestion`.

Commit type: `docs(<scope>): 📝 ...` for `docs/`, `mkdocs.yml` and `README.md` changes. A docstring change made alongside code goes in that code's commit. `docs` commits do not trigger a release, so the published site only refreshes on the next push to `main` or `beta` that touches `docs/`.
