# archify

## Agent skills

### Issue tracker

Issues live as GitHub issues on `AymanKastali/archify`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## What this repo is

A Claude Code plugin. `archify` is the binding standard for DDD, Clean
Architecture and Clean Code in Go, used across other projects.

**It is a standards layer, not a workflow.** The workflow is
`mattpocock-skills`; archify sits underneath it in the slot `/codebase-design`
and `/domain-modeling` occupy. Four of its five skills are model-invoked so the
flow's own steps pull them in; only `setup` is user-invoked.

| Path | Holds |
|---|---|
| `.claude-plugin/plugin.json` | The plugin manifest; the `skills` array lists every skill |
| `.claude-plugin/marketplace.json` | Lets the repo be installed directly as a marketplace |
| `standards/` | The corpus. This is the product; everything else is an interface onto it |
| `standards/modular-monolith/` | The default architecture and **the canonical project layout** every Go project adopts |
| `skills/<name>/SKILL.md` | Entry points, invoked as `/archify:<name>` |
| `agents/` | Subagent definitions |
| `hooks/` | SessionStart announcement, Go projects only |
| `scripts/` | `check.sh` and the checks it runs; CI runs the same script |
| `CONTEXT.md` | Glossary for talking about the standard as an artifact — not about DDD |

## Working on it

- **Skills point at `standards/`, they do not restate it.** A rule written in
  two places drifts. If a skill needs to state a rule, the rule belongs on a
  standards page and the skill cites it.
- **Adding a skill means editing `.claude-plugin/plugin.json`.** A skill
  directory not listed in the manifest is not loaded.
- **Every standards page ends with `## Sources`.** Book citations are
  chapter-level and links are checked before being added — a fabricated citation
  is worse than none in a document whose whole claim is that it is
  authoritative.
- **Relative links from a skill into the corpus are `../../standards/…`.** Check
  them after moving anything.
- **Run `./scripts/check.sh` before committing.** It checks the things that
  silently rot: relative links, fence languages, `## Sources`, manifest and
  skill agreement, the hook's behaviour in five scenarios, and — the one that
  matters most — that every Go sample is gofmt-exact. Code copied out of this
  corpus has to be conformant on arrival, or the corpus is arguing against
  itself. `ARCHIFY_CHECK_URLS=1` adds the cited-URL sweep; CI runs it weekly.
- **`scripts/check_arch_rules.py` runs the `forbidden()` function printed on
  `modular-monolith/enforcement.md`** against a table of edges that must be
  refused and edges that must be allowed. That function is the highest-stakes
  code here: a project copies it in, CI goes green, and everyone believes the
  boundaries hold. It has already been wrong once in a way that asserted
  nothing while reporting `ok`. Do not edit it without running that check.

## Working alongside `mattpocock-skills`

- **No archify skill may replace a flow step.** `/to-spec` writes specs,
  `/implement` implements, `/code-review` reviews. archify supplies what those
  steps say about the model. A skill here that reads like a competing entry
  point is the bug this layout was rewritten to fix.
- **Reference the other plugin as prose `/skill` invocation, never a file
  path.** Its install path carries a pinned version and would break on upgrade.
  This is also its own stated rule for cross-skill dependencies.
- **`CONTEXT.md` and `docs/adr/` belong to `/domain-modeling`.** archify states
  what must be true of the glossary; it does not own the file or its format.
- **Write "context", never "module".** The word already means `go.mod` and it
  means a Go package in `/codebase-design`. The directory is
  `internal/contexts/`; `internal/modules/` is a finding. Resolved once in
  `standards/vocabulary.md`.
- **A term collision goes in `standards/vocabulary.md`**, resolved one way, with
  the reason. Do not coin a synonym to avoid the collision, and do not restate
  the other plugin's glossary — map to it.
- **Integrate through published seams.** `CODING_STANDARDS.md` at a project root
  is how `/code-review` discovers the corpus; that is the pattern. Never require
  an edit to the other plugin.
