#!/usr/bin/env bash
#
# Everything CI runs, runnable locally:
#
#     ./scripts/check.sh
#
# Each check here exists because the thing it checks was once wrong. A corpus
# whose entire claim is that it is authoritative has to be checkable, or the
# claim is just a tone of voice.

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Deliberately unquoted below, so PYTHON can carry a launcher: PYTHON="uv run python"
# shellcheck disable=SC2086
PY=${PYTHON:-python3}
status=0

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32mok\033[0m   %s\n' "$*"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; status=1; }
skip() { printf '  --   %s (skipped: %s)\n' "$1" "$2"; }

say "Documents"
if out=$($PY scripts/check_docs.py 2>&1); then
    ok "$(printf '%s' "$out" | tail -1)"
else
    printf '%s\n' "$out"
    bad "corpus structure"
fi

say "Architecture rules"
if out=$($PY scripts/check_arch_rules.py 2>&1); then
    ok "$(printf '%s' "$out" | tail -1)"
else
    printf '%s\n' "$out"
    bad "the forbidden() logic on enforcement.md does not hold"
fi

say "Hook"
if bash -n hooks/session-start.sh; then
    ok "session-start.sh parses"
else
    bad "session-start.sh does not parse"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/proj/internal/contexts/ordering" "$tmp/plain"
echo "module myapp" > "$tmp/proj/go.mod"
hook="$PWD/hooks/session-start.sh"

emits() { (cd "$1" && bash "$hook" 2>/dev/null) | grep -q additionalContext; }

if emits "$tmp/proj"; then ok "announces at a Go project root"
else bad "silent at a Go project root"; fi

if emits "$tmp/proj/internal/contexts/ordering"; then ok "announces from a subdirectory"
else bad "silent in a subdirectory of a Go project"; fi

if emits "$tmp/plain"; then bad "announces outside a Go project"
else ok "silent outside a Go project"; fi

touch "$tmp/proj/.archify-off"
if emits "$tmp/proj/internal/contexts/ordering"; then bad ".archify-off does not silence it"
else ok ".archify-off silences it, from anywhere in the tree"; fi
rm "$tmp/proj/.archify-off"

if (cd "$tmp/proj" && bash "$hook") | $PY -c 'import json,sys; json.load(sys.stdin)'; then
    ok "emits valid JSON"
else
    bad "hook output is not valid JSON"
fi

say "Plugin manifest"
if command -v claude >/dev/null 2>&1; then
    if out=$(claude plugin validate . --strict 2>&1); then
        ok "claude plugin validate --strict"
    else
        printf '%s\n' "$out"
        bad "claude plugin validate --strict"
    fi
else
    skip "claude plugin validate" "claude not on PATH"
fi

say "Links"
if [ "${ARCHIFY_CHECK_URLS:-0}" = "1" ]; then
    $PY scripts/check_urls.py || bad "some cited URLs are unreachable"
else
    skip "external URLs" "set ARCHIFY_CHECK_URLS=1 to check them"
fi

echo
if [ "$status" -eq 0 ]; then
    printf '\033[32mAll checks passed.\033[0m\n'
else
    printf '\033[31mSome checks failed.\033[0m\n'
fi
exit "$status"
