---
name: git-conventions
description: Commit and PR procedure for pydiagral — branch check, pre-commit test gate, Tests line, breaking changes, PR description template, and GitHub CLI usage.
---

# Git Conventions — pydiagral

Use this skill for any commit, PR creation, or pre-commit verification task.

---

## 0. GitHub Tooling

`gh` is installed and is the way to reach GitHub: issues, PRs, comments, checks, raw API. There is no MCP GitHub server configured for this repository.

```bash
gh pr create --base dev --title "..." --body-file <file>
gh pr checks <n>
gh run list -w pytest.yaml -L 5
gh search code --repo mguyard/hass-diagral "<symbol>"
```

Write issue and PR bodies from a file rather than inline: it keeps the text reviewable before it is published, and lets it be scanned for personal data first (credentials, serial, e-mail, webhook URL, local paths — see `CLAUDE.md`).

Ask before any outward-facing action — opening or closing an issue or PR, posting a comment, pushing to a shared branch.

---

## 1. Message and Title Format

The format, the type-to-gitmoji mapping, the scope vocabulary and the `Tests:` line are defined in **`AGENTS.md` → Commits**. This skill covers the procedure around them.

Worked examples (the first two are illustrative; the last two are from the history):

```
feat(models): ✨ Rename `Webhook.webhook_url` to `Webhook.url`

- Aligns the field with the name the API returns

Tests: ✅ 58 passed, ❌ 0 failed, ⚠️ 0 errors

BREAKING CHANGE: `Webhook.webhook_url` no longer exists; use `Webhook.url`.
```

```
fix(api): 🐛 Re-raise unmatched errors in `get_anomalies`

Tests: ✅ 59 passed, ❌ 0 failed, ⚠️ 0 errors
```

```
chore(workflow): 🔧 Add base reference for documentation change checks

Tests: N/A (no src or tests change)
```

```
docs(index): 📝 Update requirements for Diagral box compatibility

Tests: N/A (no src or tests change)
```

---

## 2. Pre-commit Gate (Mandatory)

### 2.0 Branch check (always first)

```bash
git branch --show-current
```

- `beta` or `main` → **stop**. Switch to `dev` (or a branch cut from it), then re-apply the changes.
- `dev` or a feature branch → continue.

### 2.1 Is the gate required?

```bash
git diff --name-only HEAD | grep -qE "^(src|tests)/" && echo "tests required" || echo "tests not required"
```

- Nothing under `src/` or `tests/` changed → skip, write `Tests: N/A (no src or tests change)`.
- Otherwise the gate is mandatory: no commit until the suite passes at 100%.

### 2.2 Run the suite and ruff

Use the commands in `testing-pydiagral` §2 and §7. Capture the pytest summary line.

### 2.3 Fix loop

Read the failing output, find the root cause, fix the code or the test, rerun. Repeat until green.

### 2.4 Embed the result

Last line of the commit body, unless a `BREAKING CHANGE:` footer follows it (§2.5):

- `Tests: ✅ N passed, ❌ M failed, ⚠️ E errors` — when the gate ran
- `Tests: N/A (no src or tests change)` — when it was skipped

### 2.5 Breaking changes

If the change touches anything in `AGENTS.md` → Contracts, add a `BREAKING CHANGE:` footer after the `Tests:` line, as the last paragraph: the parser appends every following line to the note. semantic-release turns it into a major version.

---

## 3. PR Conventions

### 3.1 Title

Same format as the commit first line. `semantic-prs.yml` validates it.

### 3.2 Description template

```markdown
## Summary

<One paragraph explaining the purpose and impact of the change.>

## Commits

- [`abc1234`](https://github.com/mguyard/pydiagral/commit/abc1234) fix(api): 🐛 ... — short explanation

## Tests

```
pytest -v
✅ N passed, ❌ 0 failed, ⚠️ 0 errors — Python 3.14
```

## Impact on hass-diagral

<None, or what the integration must change and in which version. Required whenever a public method, model, exception or error message changed.>

## Related Issues

Refs #<issue_number>
```

`## Tests` is mandatory. Use `Closes #N` only when the issue should close once the change reaches `main` — see `AGENTS.md` → Branches.

### 3.3 Prepare-PR workflow

1. Confirm the branch (§2.0)
2. Run the gate (§2)
3. `git log origin/dev..HEAD --oneline` — commits for the `## Commits` section
4. `git diff origin/dev --stat` — check the scope
5. Write the title and body from the template into a file
6. Show it to the user; open with `gh pr create --base dev` only once they agree
