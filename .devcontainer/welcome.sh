#!/bin/sh
# Runs each time the editor attaches: prints the guide's address, and in
# Codespaces opens it in a browser tab the first time only.

if [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "main" ]; then
  version=stable
else
  version=beta
fi
guide="https://mguyard.github.io/pydiagral/${version}/try-pydiagral/"

printf '\nGuide to try_pydiagral.py: %s\n' "$guide"
printf 'To read it in the editor: Ctrl+Shift+P > "Simple Browser: Show", then paste the address.\n\n'

marker="$HOME/.try-pydiagral-guide-opened"
if [ "$CODESPACES" = "true" ] && [ -n "$BROWSER" ] && [ ! -e "$marker" ]; then
  "$BROWSER" "$guide" >/dev/null 2>&1 && touch "$marker"
fi
