<!--
Title: Conventional Commits with a gitmoji, e.g. `fix(api): 🐛 Re-raise unmatched errors in get_anomalies`.
Target branch: `dev`. See CONTRIBUTING.md.
-->

## Summary

<!-- What changed and why. -->

## Tests

<!-- How it was verified: the pytest summary line, and anything checked by hand. -->

```
pytest
✅ N passed, ❌ 0 failed, ⚠️ 0 errors
```

## Impact on hass-diagral

<!-- None, or what the integration must change. Required when a public method, model, exception or error message changed. -->

## Related issues

<!-- `Refs #N`. Use `Closes #N` only if the issue should close once the change reaches `main`. -->

## Checklist

- [ ] The PR targets `dev`
- [ ] `ruff check .`, `ruff format --check .`, `mypy` and `pytest` pass locally
- [ ] Every change under `src/` comes with its tests
- [ ] Every commit is signed
- [ ] No credential, serial number, e-mail address or webhook URL in the code, the fixtures or this description
- [ ] An AI assistant helped with this PR, and I have read and understood every line
