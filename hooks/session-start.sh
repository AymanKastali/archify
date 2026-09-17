#!/usr/bin/env bash
# archify SessionStart hook.
#
# Announces the standard in Go projects only, and stays silent everywhere else.
# Create a file named .archify-off at the project root to silence it there.
#
# The project root is CLAUDE_PROJECT_DIR when the harness sets it, and otherwise
# the nearest ancestor of the working directory that holds a go.mod — so a
# session started in internal/contexts/ordering is still a Go project.

set -euo pipefail

find_root() {
    local dir="$1"
    while [ "$dir" != "/" ] && [ -n "$dir" ]; do
        if [ -f "$dir/go.mod" ]; then
            printf '%s' "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    [ -f "/go.mod" ] && printf '/' && return 0
    return 1
}

start="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -d "$start" ] || start="$PWD"

root=$(find_root "$start") || exit 0
[ -f "$root/.archify-off" ] && exit 0
[ -f "$PWD/.archify-off" ] && exit 0

read -r -d '' CONTEXT <<'EOF' || true
<archify>
This is a Go project, and **archify** is the binding standard for its domain
modelling, architecture and style. Before planning or writing code under
`internal/`, invoke the `archify:standard` skill and read the page that applies
— do not work from a recalled summary of DDD.

archify is a standards layer, not a workflow. The workflow stays Matt Pocock's
skills; archify feeds them:
- inside `/to-spec` and `/to-tickets` -> `archify:modelling-decisions`
- inside `/implement` and `/tdd`      -> `archify:writing-order`
- inside `/code-review` (Standards)   -> `archify:review-passes`
- `archify:standard` is the corpus router; `/archify:setup` configures a repo.

Never substitute an archify skill for a flow step. `CONTEXT.md` and ADRs belong
to `/domain-modeling`; write them through it.

_Clean Code_ is filtered here, not adopted. Function length, repeated
`if err != nil`, short receiver names, table-driven tests and type switches over
a closed set are **conformant** — `standards/clean-code.md` lists every rule of
Martin's that Go idiom overrules. Do not report one as a finding.

The default architecture is a **modular monolith**: one `go.mod`, one binary,
`internal/contexts/<name>/` per bounded context behind a nested `internal/`, and
`internal/platform/` for what has no domain meaning. The canonical tree is
`standards/modular-monolith/layout.md`. There is no `pkg/`, no
`internal/modules/` and no `internal/shared/`.

Six rules apply without invoking anything:
- `domain` imports the standard library and its own context's `domain`. Nothing else.
- A repository interface lives in `domain`; every other port lives in `application`.
- One aggregate per transaction.
- An aggregate is never constructed invalid — no setters, no exported fields.
- A context owns its schema. No cross-context join, foreign key or transaction —
  and none of those three is visible in the import graph or to any linter.
- A context never imports another context's facade package. It declares the
  interface it needs; the composition root satisfies it.

Departing from a rule requires an ADR in `docs/adr/`. A deviation without one
is a defect.
</archify>
EOF

escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' \
    "$(escape_for_json "$CONTEXT")"
