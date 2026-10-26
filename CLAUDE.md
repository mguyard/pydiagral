# CLAUDE.md

@AGENTS.md

The file above holds every repository rule and is shared with other agents. What follows applies to Claude Code only.

## Tooling

- **`gh` is installed and is the way to reach GitHub** — issues, PRs, comments, checks, API calls. There is no MCP GitHub server configured here.
- Use `AskUserQuestion` when a decision is genuinely the user's to make. Do not ask about choices that have an obvious default or facts the repository can answer.
- Context7 is available for library documentation. Prefer it over web search for aiohttp, pytest, MkDocs or mkdocstrings APIs.
- **Never read `.env`**, not even to check which variables it defines: it holds real Diagral credentials. Never run `try_pydiagral.py`.

## Skills

Project skills live in `.claude/skills/` and load on demand:

| Skill | Load it for |
|---|---|
| `add-api-method` | Adding or changing a `DiagralAPI` method, endpoint or model |
| `testing-pydiagral` | Running or writing tests, coverage |
| `git-conventions` | Commits, PRs, branch rules |
| `docs-pydiagral` | Docstrings, `docs/`, `mkdocs.yml`, `README.md` |

## Writing to GitHub

- **Never self-reference in commits.** No `Co-Authored-By: Claude`, no `Claude-Session:` trailer, no mention of the assistant or the session — in commit messages, PR bodies or issue text. Only add them if asked for a specific commit.
- **Correct a mistake in an issue or PR by editing the body**, and delete any correction comment already posted. Once a discussion is under way, say in the thread that the body changed rather than editing silently.
- **Never publish personal data.** No credential, central serial, account e-mail, webhook URL or path from the maintainer's machine in an issue, a commit, a PR or a tracked file. Never quote a `pydiagral.api` debug line unredacted — it carries headers, the serial and URLs. Link to public GitHub URLs instead of local paths.
- Ask before any outward-facing action: opening or closing an issue or PR, posting a comment, pushing to a shared branch.

## Verifying

The user expects claims to be checked, not asserted. Read the code, run the command. When a measurement contradicts an earlier statement, say so plainly and correct it.

## Committing

Do not commit or push unless asked. The user reviews changes first.
