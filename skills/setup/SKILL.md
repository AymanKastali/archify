---
name: setup
description: Set a Go project up so the archify standard is enforced rather than remembered — the modular-monolith layout, schema per context, depguard rules, an architecture test, and the CODING_STANDARDS.md that /code-review reads.
disable-model-invocation: true
---

# Setting a project up

The standard binds whether or not this runs. What this adds is **enforcement**:
the parts a tool can check without knowing what the code is for, and the one
file that makes the standard discoverable to a review that was never told about
this plugin.

Read [`../standard/SKILL.md`](../standard/SKILL.md) first.

## 0 — Precondition

Run **`/setup-matt-pocock-skills`** first if `docs/agents/` is missing. It
configures the issue tracker, the triage labels and the domain-doc layout that
`/to-spec`, `/to-tickets`, `/triage` and `/code-review` all assume. This skill
configures the Go standard on top of that; it does not replace it and does not
duplicate any of its files.

If `docs/agents/` already exists, read `docs/agents/domain.md` and follow the
layout it records — single-context or multi-context — rather than imposing one.

## 1 — Establish the layout

Ask which bounded contexts exist. **One is normal at the start**; do not invent a
second because the layout has room for it — a second context costs a schema, a
published language, an ACL per consumer, and eventual consistency with
everything it used to be consistent with.

The layout is not negotiable and is not a starting point to adapt. It is
[`modular-monolith/layout.md`](../../standards/modular-monolith/layout.md) —
**read that page and scaffold what it shows**, which is:

```text
go.mod                                one module, for the whole repository
cmd/app/main.go                       flags, signals, exit code. Nothing else
internal/
  composition/                        the binary's composition root
  contexts/
    <context>/
      CONTEXT.md                      this context's glossary
      <context>.go                    the facade: the only non-published export
      published/                      event types and identifiers other contexts may import
      migrations/                     this context's schema. There is no root migrations/
      internal/                       <- makes the boundary a compile error, not a convention
        domain/<aggregate>/           one package per aggregate
        application/
        adapters/inbound/
        adapters/outbound/
  platform/                           technical, no domain meaning
test/e2e/
```

Four points to make to the user, because each is a decision they are entitled to
push back on and each has a page:

- **Everything is under `internal/`. There is no `pkg/`.** A product has no
  external importers.
- **The nested `internal/` is the point.** Code outside
  `internal/contexts/<context>/` cannot import that context's `domain` at all.
  The compiler enforces the boundary a linter can only complain about.
- **One binary.** Run modes are subcommands — `app serve`, `app worker`,
  `app migrate` — not separate `cmd/` directories.
- **`internal/platform/` is not a `shared` package.** Nothing in it may change
  because a business rule changed, and it may import no context.
  → [`modular-monolith/platform.md`](../../standards/modular-monolith/platform.md)

Do not create `internal/platform/util`, `common` or `shared`. Ever.

## 1b — One schema per context

Each context owns a schema and, where the database supports it, a role:

```sql
CREATE SCHEMA IF NOT EXISTS ordering;
CREATE ROLE app_ordering LOGIN PASSWORD :'ordering_password';
GRANT USAGE ON SCHEMA ordering TO app_ordering;
ALTER DEFAULT PRIVILEGES IN SCHEMA ordering
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_ordering;
```

The composition root then builds one pool per context, each with
`search_path=<context>`, so unqualified SQL in a context can only resolve to its
own schema. **This is the step that converts "no cross-context join" from a
review item into an error the database raises** — and the cross-schema join is
the one boundary violation nothing in the import graph reveals.

If the project already has one shared schema, say so and take the fallback — one
pool, one role, qualified table names — **as an ADR**, naming the enforcement
being given up. Do not take it silently.
→ [`modular-monolith/data.md`](../../standards/modular-monolith/data.md)

## 2 — `CODING_STANDARDS.md`

Write this at the repo root. It is the seam: `/code-review` collects "anything
in the repo that documents how code should be written", so this file is how a
review finds the standard without anyone remembering to mention it.

```markdown
# Coding standards

This project follows **archify** — the binding standard for Domain-Driven
Design, Clean Architecture, Clean Code and the modular monolith in Go. The
project layout, the context boundaries and the schema-per-context rule come
from it and are not local choices.

The corpus is the `archify` Claude Code plugin, under `standards/`. Reviewers
and implementers read it there; it is not copied into this repo, because a rule
kept in two places drifts.

- `standards/modular-monolith.md` — the project layout, what a module is, and
  the six properties that make a monolith modular
- `standards/structure.md` — regions inside a context, the dependency rule,
  where a port lives
- `standards/domain-driven-design.md` — the model, and an index of the rest
- `standards/clean-code.md` — style, and the _Clean Code_ rules that are
  deliberately **not** applied in Go
- `standards/vocabulary.md` — how these terms map to `/codebase-design`'s

Agents: run `/archify:review-passes` for the Standards axis of a review, and
`/archify:writing-order` when implementing.

## Deviations

Departing from an archify rule requires an ADR in `docs/adr/` naming the rule
and arguing the trade-off. **A deviation without an ADR is a defect**, not a
style choice. An ADR-backed departure is settled and is never a review finding.

## Inherited

<Only in an existing project: name the directories that predate adoption and
are not held to the standard, and link the ADR that records them.>
```

Keep it to that. It is a pointer, not a second copy of the corpus.

## 3 — `CONTEXT.md` and `docs/adr/`

Both belong to **`/domain-modeling`**. Run it rather than writing them here, and
use its formats.

Two things archify adds to what it produces:

- **One `CONTEXT.md` per bounded context**, or one at the root for a
  single-context project — matching `docs/agents/domain.md`.
- **The glossary term and the Go identifier are the same word.** If the
  glossary says `Shipment`, the type is `Shipment`, not `ShipmentModel` or
  `ShipmentDTO`. A rename in one is a rename in the other.
  → [`ddd/ubiquitous-language.md`](../../standards/ddd/ubiquitous-language.md)

`/domain-modeling`'s rule that general programming concepts stay out of the
glossary holds. `Money` and `SKU` belong there; `Result` and `Clock` do not.

Then write the first ADR, recording that the project follows archify and that
the deviation rule above is live. Without it, "we decided to do it differently"
is indistinguishable from "someone did it differently".

## 4 — depguard

Turn the dependency rule into a build failure. The config is written out in full
on [`modular-monolith/enforcement.md`](../../standards/modular-monolith/enforcement.md)
— **copy `.golangci.yml` from there**, and replace `myapp` with the real module
path everywhere it appears. Do not retype it from memory: a depguard rule with a
path slightly wrong matches nothing, and the build stays green while the rule it
claims to enforce is not enforced. That is worse than having no rule at all,
because the green build is now evidence of nothing.

It declares five rules — one per region, plus one for the read side — and each
exists for a reason named on that page:

| Rule | Scoped to | Refuses |
|---|---|---|
| `domain` | `contexts/*/internal/domain/**` | everything but the standard library and its own context's domain |
| `application` | `contexts/*/internal/application/**` | `platform`, `database/sql`, `net/http`, any third-party type |
| `query` | `contexts/*/internal/application/query/**` | anything in this module — a read model is primitives, so the read side names no domain type and no repository |
| `platform` | `internal/platform/**` | any bounded context, `published/` included |
| `published` | `contexts/*/published/**` | anything from this module — published types are plain data |

Then verify it rather than assuming it parses:

```bash
golangci-lint config verify && golangci-lint run ./...
```

## 4b — The architecture test

depguard matches import paths by prefix and has no notion of *which* context a
file is in, so it cannot say "ordering may not import shipping". One Go test
can, by walking the real import graph, and it is the highest-value test in the
project after the composition build test.

Write `internal/arch/arch_test.go` from the worked implementation on
[`modular-monolith/enforcement.md`](../../standards/modular-monolith/enforcement.md).
It asserts what no other level reaches:

- only a context's `published/` crosses a context boundary,
- and only into another context's `adapters/` or its facade — a published type
  named in `application` or `domain` is an upstream contract that reached the
  model,
- `published/` imports nothing from this module,
- `platform/` imports no context,
- no context names another context's facade package.

Add it to CI as its own step, separate from `go test ./...`, because when it
fails the fix is not "make the test pass".

Write the composition build test too — it is six lines and it catches every
wiring mistake the compiler cannot.
→ [`modular-monolith/composition.md`](../../standards/modular-monolith/composition.md)

**Know what none of this catches.** No tool sees a cross-schema join, a
transaction spanning two contexts, a business rule in a subscriber, an aggregate
with exported fields, two aggregates in one transaction, or a `platform/`
package that has quietly acquired domain meaning. Those are review findings, and
pretending otherwise is how a green build starts meaning nothing.
→ [`modular-monolith/enforcement.md`](../../standards/modular-monolith/enforcement.md)

## 5 — Confirm

Report what was created, and name the enforcement level for each rule: what the
**compiler** catches (cross-context imports), what **depguard** catches (a region
importing what it may not), what the **architecture test** catches (published
types crossing wrongly, platform depending on a context, a facade import), what
the **database** catches (a cross-schema read, if the roles were created), and
what remains a **review** concern.

The user should finish knowing exactly which mistakes the build will now catch
and which it will not — and that the most expensive one, a cross-context join,
is caught only by the database role or by review.

Name the next step: the flow is `/grill-with-docs` → `/to-spec` → `/to-tickets`
→ `/implement`, and archify now feeds each of those without being invoked.

## Adopting in an existing project

Do not move every file. Write `CODING_STANDARDS.md` and the lint config, run
`/domain-modeling` for the glossary, apply the layout to **new** contexts only,
and record the existing layout in an ADR as inherited — then list those
directories under the file's **Inherited** heading so reviews do not report
them. The standard ratchets forward on new work; a big-bang restructure is how
adoption stalls.

Scope the enforcement the same way, in this order:

1. Add the `platform` and `published` depguard rules first — almost always
   already satisfied, and the two that decay silently.
2. Add the `domain` and `application` rules scoped to the new context's paths
   only, so the build is green on day one.
3. Add the architecture test with a **known-failures list**: literal `from → to`
   pairs that are allowed to exist, each with the ADR that permits it. Make the
   test fail when a listed pair has been fixed and not removed — a ratchet that
   only tightens.
4. Widen the file globs as each inherited context is migrated.

The **database** is the half that is usually skipped and is usually the whole
problem. Splitting a shared schema is `modular-monolith/data.md`'s *Migrating an
existing shared schema* section: assign every table to one context on paper,
move it with `ALTER TABLE ... SET SCHEMA` behind a compatibility view, drop the
cross-context foreign keys, replace each cross-context join with a projection,
then create the roles. Steps one and four are the work.
