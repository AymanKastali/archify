# archify

A Claude Code plugin. It is the binding standard for how Domain-Driven Design,
Clean Architecture, Clean Code and the modular monolith are applied in Go — the
project layout included — with worked examples, named authorities, an explicit
precedence rule when those authorities disagree, and gates at plan time and
review time so the standard is applied rather than remembered.

It exists because "follow DDD and clean architecture" is not an instruction. It
resolves to a different codebase every session unless someone has written down
which book wins, where a port lives, and what happens when a rule is broken.

**It is a standards layer, not a workflow.** The workflow is
[Matt Pocock's skills](https://github.com/mattpocock/skills); archify runs
underneath them, in the slot `/codebase-design` and `/domain-modeling` occupy —
pulled in by the flow's steps, never replacing one. See
[Working with mattpocock-skills](#working-with-mattpocock-skills).

## Install

```text
/plugin marketplace add AymanKastali/archify
/plugin install archify@archify
```

Or from a local clone:

```text
/plugin marketplace add ~/path/to/archify
/plugin install archify@archify
```

## What it gives you

**Skills** — invoke with `/archify:<name>`, or let them trigger themselves:

| Skill | For | Pulled in by |
|---|---|---|
| `archify:standard` | The rules, the precedence order, and the map of pages | anything |
| `archify:modelling-decisions` | The modelling decisions a spec or ticket must carry | `/to-spec`, `/to-tickets` |
| `archify:writing-order` | The order that makes a layering error unwritable, and where the test seam is | `/implement`, `/tdd` |
| `archify:review-passes` | The Standards-axis passes, with page-and-rule citations | `/code-review` |
| `archify:setup` | Scaffolding the layout, the schemas, depguard and the architecture test, so the build enforces what it can | you, once per repo |

The first four are model-invoked: they fire when the work calls for them, which
is the point — the standard was never lost because it was wrong, only because
nobody remembered to invoke it. `archify:setup` is yours to run.

**An agent** — `archify-reviewer`, which runs one review pass in isolation, so a
large diff can be reviewed by several in parallel without any of them losing
focus.

**A hook** — announces the standard at session start, in Go projects only.
Create a `.archify-off` file at a project root to silence it there.

**The standard itself**, in [`standards/`](./standards/). It is plain markdown
and worth reading directly:

- [`modular-monolith.md`](./standards/modular-monolith.md) — the default
  architecture: what a module is, the six properties, and 8 pages under
  [`modular-monolith/`](./standards/modular-monolith/) — including
  [the canonical project layout](./standards/modular-monolith/layout.md)
- [`structure.md`](./standards/structure.md) — the four regions inside one
  context, the dependency rule, and where a port lives
- [`domain-driven-design.md`](./standards/domain-driven-design.md) — the index,
  the precedence rule, and 15 pages under [`ddd/`](./standards/ddd/)
- [`clean-code.md`](./standards/clean-code.md) — the verdict on each chapter of
  Martin's book, the rules **deliberately not applied in Go**, and 11 pages
  under [`clean-code/`](./standards/clean-code/)
- [`vocabulary.md`](./standards/vocabulary.md) — how these terms map to
  `/codebase-design`'s, and the two places the two standards only *look* like
  they collide

## Working with mattpocock-skills

archify does not duplicate a single step of the flow `/ask-matt` maps. It
supplies what those steps cannot know: the model rules for a Go DDD codebase.

| Flow step | archify contributes |
|---|---|
| `/grill-with-docs` | nothing — the interview is the interview |
| `/to-spec` | the Implementation Decisions and Testing Decisions content, and the standing answer to "where is the seam" |
| `/to-tickets` | what a *vertical* slice is in a four-region layout, and the horizontal cut to refuse |
| `/codebase-design` | the layout the modules sit in, and the three meanings of "module" it disambiguates |
| `/implement`, `/tdd` | outside-in test, inside-out implementation; which ports get fakes and which collaborators never do |
| `/code-review` | the Standards axis, plus the two Fowler smells this layout overrides |
| `/domain-modeling` | it owns `CONTEXT.md` and ADRs; archify only adds that the glossary term and the Go identifier are the same word |

Three rules keep the two from fighting:

1. **No archify skill replaces a flow step.** Want a spec? Run `/to-spec`.
2. **`CONTEXT.md` and ADRs go through `/domain-modeling`**, in its formats.
3. **Cross-plugin references are prose `/skill` invocations, never file paths.**
   The other plugin's install path is version-pinned and would break on upgrade.

A repo that has run `/archify:setup` gets a `CODING_STANDARDS.md` at its root
pointing here — which is exactly what `/code-review` looks for when it collects
standards sources, so the integration needs no change to either plugin.

## How it decides things

Three authorities disagree, and averaging them is what produces code that looks
like DDD and is not. The order is fixed:

- **Vernon** wins on tactical design — aggregates, repositories, events
- **Evans** wins on strategic design — contexts, maps, language
- **Martin** wins on dependency direction, and on code-level style — with the
  Java-shaped parts of _Clean Code_ removed, page by page, and listed
- **Cockburn** supplies `port` and `adapter`
- **Newman**, with Evans ch. 14, underwrites the modular monolith — a context is
  a model boundary and a process is a deployment boundary, and conflating them
  is expensive in both directions
- **Go wins** wherever idiom collides with a book written about Java

Where DDD and Clean Architecture collide on names, DDD's names win: `Aggregate`,
not `Entity` in Martin's sense; `Application Service`, not `Interactor`.

## Deviating

A project may overrule any rule. The departure is recorded as an ADR in that
project's `docs/adr/`, naming the rule and arguing the trade-off.

**A deviation without an ADR is a defect,** not a style choice. An ADR-backed
one is settled, and a reviewer never raises it again.

## Checking it

The corpus is checkable, and checked:

```bash
./scripts/check.sh
```

Relative links resolve, every fenced block is labelled, every standards page
carries exactly one `## Sources`, the manifest and `skills/` agree, the hook
behaves in five scenarios — and **every Go sample is gofmt-exact**, so code
copied out of here is conformant on arrival. It also runs the `forbidden()`
function from [enforcement.md](./standards/modular-monolith/enforcement.md)
against a table of import edges that must be refused and edges that must be
allowed, because a boundary test that silently asserts nothing is worse than no
test. `ARCHIFY_CHECK_URLS=1` adds the cited-link sweep; CI runs that weekly.

## Status

The DDD corpus, the Clean Code corpus, the modular-monolith corpus, the
structure rules and the vocabulary map are written — 39 pages. Not yet written:
the pattern pages (transactional outbox, unit of work) as numbered clauses, and
the Go reference implementation.

## Sources

Every page ends with its sources — chapter-level book citations and links that
were checked, not assumed. The free primary material is worth having to hand:

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/) — Evans
- [Effective Aggregate Design](https://www.dddcommunity.org/library/vernon_2011/) — Vernon
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) — Cockburn

## Licence

MIT — see [LICENSE](./LICENSE).
