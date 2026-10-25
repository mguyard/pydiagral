# Contributing to pydiagral

Thanks for your interest in pydiagral! 💙 Bug reports, feature requests and pull requests are all welcome.

- 🐛 **Report a bug or request a feature** through the [issue templates](https://github.com/mguyard/pydiagral/issues/new/choose).
- 🔀 **Submit a pull request**: review open PRs, or submit your own following the steps below.

The full repository rules live in [`AGENTS.md`](AGENTS.md). This page is the short version for contributors.

## 🛠️ Set up

```bash
git clone https://github.com/<your-account>/pydiagral
cd pydiagral
python3 -m venv .venv && . .venv/bin/activate

# hatchling reads the version from PYPROJECT_VERSION; without it the build fails.
PYPROJECT_VERSION=0.1.0-dev pip install -e ".[dev]"
```

The `dev` extra holds pytest and the pinned versions of ruff and mypy that CI uses.

## 🔀 Workflow

1. **Fork** the repository and clone your fork.
2. **Create a branch** from `dev`, with a descriptive name:
   ```sh
   git checkout -b new-feature-x origin/dev
   ```
3. **Make your changes**, with tests for every change under `src/`.
4. **Check them locally** — CI runs the same commands, and all of them are required to merge:
   ```sh
   ruff check .
   ruff format --check .
   mypy
   pytest
   ```
5. **Commit** with a signed commit (see below), and push to your fork.
6. **Open a pull request against `dev`**, and fill in the template.

Once reviewed and approved, the PR is merged into `dev`, then promoted to `beta` for a prerelease and to `main` for a stable release.

## 📝 Commits

Commits follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), with a gitmoji after the type, and end with a `Tests:` line:

```
fix(api): 🐛 Re-raise unmatched errors in `get_anomalies`

Tests: ✅ 59 passed, ❌ 0 failed, ⚠️ 0 errors
```

| Type | Gitmoji | Released? |
|---|---|---|
| `feat` | ✨ | ✅ minor |
| `fix` | 🐛 | ✅ patch |
| `perf` | ⚡ | ✅ patch |
| `docs` | 📝 | — |
| `refactor` | ♻️ | — |
| `test` | ✅ | — |
| `chore`, `ci` | 🔧 | — |

Use `Tests: N/A (no src or tests change)` when nothing under `src/` or `tests/` changed. The PR title follows the same format, and a check validates it. The details, including breaking changes, are in `AGENTS.md` → *Commits*.

> [!IMPORTANT]
>
> **Every commit must be signed**: the branches only accept signed commits. See GitHub's guide to [signing commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

## 🔒 Ground rules

- **No real Diagral call in tests.** Tests mock the API and never touch the Diagral cloud.
- **No personal data.** No credential, serial number, e-mail address or webhook URL in code, fixtures, commits, issues or PRs. Fixtures are synthetic.
- **Keep hass-diagral working.** [hass-diagral](https://github.com/mguyard/hass-diagral) relies on the public surface listed under *Contracts with hass-diagral* in `AGENTS.md`. Changing it is a breaking change.
- **Never log a secret.** Passwords, tokens, API keys, PIN codes and signatures are redacted in the logs; a new one goes into `SENSITIVE_KEYS`.

## 🤖 Contributing with an AI assistant

AI coding assistants are welcome, under the same rules as everyone else. Point yours at [`AGENTS.md`](AGENTS.md): it holds the repository rules, in the `AGENTS.md` format that many agents read automatically. Claude Code reads it through [`CLAUDE.md`](CLAUDE.md).

You stay the author of what you submit: read and understand every line before opening the PR, and say in its description when an assistant helped.

## 📄 License

By contributing, you agree that your contributions are distributed under the [GPL-v3 License](LICENSE) of the project.
