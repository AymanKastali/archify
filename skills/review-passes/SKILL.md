---
name: review-passes
description: The archify standards passes for reviewing a Go DDD diff — context boundaries, data ownership, cross-context communication, composition, platform, then dependency direction, port placement, domain purity, aggregate design, transaction scope, repository surface, language, errors, and finally naming, function and type shape, doc comments, tests and doubles. Also the list of Clean Code rules that must never be reported as findings in Go. Use as the standards source when reviewing Go code that follows DDD, hexagonal architecture or a modular monolith, including inside a /code-review Standards axis, or before merging work in such a project.
---

# Review passes

This is the **Standards axis material** for a Go DDD project. `/code-review`
owns the review: it pins the fixed point, resolves the diff, finds the spec, and
runs the Standards and Spec sub-agents in parallel. This supplies what the
Standards sub-agent checks.

Read [`../standard/SKILL.md`](../standard/SKILL.md) for precedence first.

**Do not add a third axis.** Two is deliberate — code can pass Standards and
fail Spec, and reporting them separately is what stops one masking the other.
archify findings are Standards findings. A finding that the *model in the spec*
is wrong belongs to the Spec axis and stays there.

## How `/code-review` finds this

Its step 3 collects "anything in the repo that documents how code should be
written". [`archify:setup`](../setup/SKILL.md) writes a `CODING_STANDARDS.md`
at the repo root that names this plugin and its corpus, so a project that ran
setup is discovered with no change to `/code-review` at all.

If that file is missing and the project is Go with a `domain`/`application`
split, say so and offer `/archify:setup` — then review anyway.

## Scope

**Review the diff, not the tree.** The standard applies to what this change
adds. Pre-existing violations it merely touches are noted separately as
"existing, not introduced here" — a ratchet, not a rewrite. Otherwise every
review of a legacy codebase becomes a refactoring argument and the actual change
goes unreviewed.

An ADR in `docs/adr/` that overrules a rule settles it. Check there before
reporting a finding that contradicts one. An ADR-backed departure is never a
finding.

## The passes

Work these in order. The early ones are cheap and catch the expensive problems.

**Passes 1–5 are the boundary passes.** They are three greps and a look at the
migrations on most diffs, and they catch the defects that cost most to fix
later — a cross-context join is discovered years after it ships, and by then
neither context can be changed alone. On a diff that adds no directory, no SQL
and no wiring, they are done in a minute.

### The boundary passes

**1 — Context boundary.** A new directory under `internal/contexts/`? Does every
touched context still have exactly `CONTEXT.md`, `<name>.go`, `published/`,
`migrations/`, `internal/`? Does anything import another context's **facade
package**, or its `published/` from anywhere but `adapters/` and the facade? Does the facade contain
a conditional reading business state, or return a domain type, repository or
database handle?
→ [`modular-monolith/modules.md`](../../standards/modular-monolith/modules.md),
[`modular-monolith/layout.md`](../../standards/modular-monolith/layout.md)

**2 — Data ownership.** Any SQL naming a table outside its own context's schema.
Any foreign key crossing a schema. Any transaction touching two contexts. Any
migration outside a context's `migrations/`. Any shared table with a `kind`
discriminator. **Nothing in the import graph reveals any of these**, so this
pass reads the SQL, not the imports.
→ [`modular-monolith/data.md`](../../standards/modular-monolith/data.md)

**3 — Cross-context communication.** A command crossing a boundary — always a
finding. A synchronous cross-context call without an ADR. Events published
outside the aggregate's transaction, or to a broker instead of the outbox. A
subscriber with no ACL, or with no idempotency on the message id. A topic as a
string literal. `errors.Is` against another context's error.
→ [`modular-monolith/communication.md`](../../standards/modular-monolith/communication.md)

**4 — Composition.** `init()` registration, a registry, or a reflection-based
container. A context reading an environment variable. A conditional in
`internal/composition/` that reads a domain value. A goroutine started in a
constructor rather than supervised by the composition root. Lazy construction
behind a `sync.Once`.
→ [`modular-monolith/composition.md`](../../standards/modular-monolith/composition.md)

**5 — Platform.** Anything new under `internal/platform/` that would change
because a business rule changed. `platform` importing a context — including
`published/`. `domain` or `application` importing `platform` outside a
`_test.go`. A package named `util`, `common`, `shared`, `core` or `base`.
→ [`modular-monolith/platform.md`](../../standards/modular-monolith/platform.md)

### The model passes

**6 — Direction.** For every new or changed import in `domain` and
`application`: is it allowed by the region table?
→ [`structure.md`](../../standards/structure.md)

**7 — Port placement.** Every interface introduced: repository interfaces in
`domain`, every other port in `application` beside its use case. An interface
declared in `adapters` and consumed inwards is inverted.

**8 — Purity of `domain`.** Struct tags, `context.Context` outside a repository
interface, `any`, driver or framework types, `time.Now()` called inside the
model, exported mutable fields, setters.

**9 — Aggregate design.** Can an invalid instance be constructed? Is another
aggregate held by pointer rather than by identity? Is the invariant statable in
one sentence?
→ [`ddd/aggregates.md`](../../standards/ddd/aggregates.md)

**10 — Transaction scope.** One aggregate per transaction. Events written to the
outbox inside the same transaction. No broker call inside a transaction.
→ [`ddd/domain-events.md`](../../standards/ddd/domain-events.md)

**11 — Repository surface.** Any method returning a row, projection or partial
shape is a read model in the wrong place. Any predicate or function parameter is
an in-memory filter waiting to happen.
→ [`ddd/repositories.md`](../../standards/ddd/repositories.md),
[`ddd/specifications.md`](../../standards/ddd/specifications.md)

**12 — Application layer thinness.** A conditional in `application` that reads
aggregate state to decide a business outcome is a rule that escaped the model.
→ [`ddd/application-services.md`](../../standards/ddd/application-services.md)

**13 — Language.** Every new type, method and event name against `CONTEXT.md`.
`Manager`, `Helper`, `Processor`, `Util`, `Data`, `Info` in `domain` are
findings on sight.
→ [`ddd/ubiquitous-language.md`](../../standards/ddd/ubiquitous-language.md)

**14 — Errors.** Sentinels or typed errors, `%w` wrapping, mapping to transport
only at the inbound adapter, no `sql.ErrNoRows` escaping an adapter.
→ [`ddd/errors.md`](../../standards/ddd/errors.md)

**15 — Heuristics sweep.** The review-heuristics list at the end of
[`ddd/anti-patterns.md`](../../standards/ddd/anti-patterns.md), then the
heuristics tables on
[`clean-code/smells.md`](../../standards/clean-code/smells.md).

## The style passes

Run these after the fifteen above, and only on what the diff introduced. They
are the [`clean-code/`](../../standards/clean-code/) corpus, and they are lower
priority by design: a misplaced port is a defect, a mediocre name is a cost.

**16 — Names.** Anything `CONTEXT.md` does not decide: package names, ports
named for their adapter, `Manager`/`Helper`/`Data`, `Get` prefixes, `Id`/`Url`
casing, stutter.
→ [`clean-code/naming.md`](../../standards/clean-code/naming.md)

**17 — Function and type shape.** Flag arguments, six-primitive signatures,
queries that mutate, hybrid types with exported fields *and* behaviour, an
interface declared beside its implementation, embedding used for reuse.
→ [`clean-code/functions.md`](../../standards/clean-code/functions.md),
[`clean-code/types-and-packages.md`](../../standards/clean-code/types-and-packages.md)

**18 — Doc comments.** Every new exported identifier has one, beginning with its
name; a new aggregate states its invariant; a new matchable error is documented
at the function that returns it.
→ [`clean-code/comments.md`](../../standards/clean-code/comments.md)

**19 — Tests and doubles.** Only ports are doubled; fakes return the same errors
as the real adapter; no mock of an aggregate, value object or application
service; no wall clock; table-driven where there is more than one case.
→ [`clean-code/tests.md`](../../standards/clean-code/tests.md)

**20 — Boundaries and concurrency.** A third-party type in `domain` or
`application`; a port mirroring an SDK; a goroutine with no owner; a network
call under a mutex; anything concurrent inside `domain`.
→ [`clean-code/boundaries.md`](../../standards/clean-code/boundaries.md),
[`clean-code/concurrency.md`](../../standards/clean-code/concurrency.md)

**None of these is a licence to report Go idiom.** Function length, repeated
`if err != nil`, short receiver names and type switches are **not findings** —
[`clean-code.md`](../../standards/clean-code.md) lists every _Clean Code_ rule
this standard refuses, and a finding that contradicts that list is itself the
defect.

## What no tool catches

The build being green means less than it looks. The compiler stops a
cross-context import; depguard stops a region importing what it may not; the
architecture test stops `published/` leaking. **None of them sees a cross-schema
join, a transaction spanning two contexts, a business rule in a subscriber, or a
`platform/` package that has quietly acquired domain meaning.** Those are passes
2, 3, 5 and 12, and they are the reason this review exists at all.
→ [`modular-monolith/enforcement.md`](../../standards/modular-monolith/enforcement.md)

## Against the Fowler smell baseline

`/code-review`'s Standards axis always carries a fixed set of Fowler smells, and
binds them with one rule: **the repo overrides — a documented repo standard
always wins.** archify is that documented standard. Two smells must be
suppressed in this layout:

- **Middle Man** — an application service is mostly delegation by design.
  Behaviour in it would be the defect.
- **Repeated Switches** — a type switch over a closed set of domain events is
  idiomatic Go and stays. "Replace with polymorphism" is a Java-shaped remedy.

Four run the same way archify does, and where they agree the finding cites the
archify page because it is the more specific rule: **Primitive Obsession**
(→ value objects), **Data Clumps** (→ value objects), **Message Chains**
(→ reference other aggregates by identity), **Feature Envy** (→ behaviour
belongs on the aggregate holding the state).

The reasoning behind both overrides is on
[`vocabulary.md`](../../standards/vocabulary.md), and the full baseline
reconciliation is on
[`clean-code/smells.md`](../../standards/clean-code/smells.md). Cite them rather
than re-arguing either in the report.

**Go idiom is not a smell.** `if err != nil` repeated, a short receiver name, a
function longer than twenty lines — none of these is a finding here, and no page
in the corpus says otherwise.

## Reporting

`/code-review` caps the Standards sub-agent at 400 words and reports it
verbatim, so findings must be dense. Each one in this shape:

> **`internal/contexts/ordering/internal/domain/order/order.go:41`** — exported
> field `Status` on an aggregate.
> **Rule:** `ddd/aggregates.md`, rule 3 — state changes only through behaviour.
> **Consequence:** any caller can move an order to `placed` without the
> transition rules running.
> **Fix:** unexport, add `Place(now time.Time) error`.

Order by consequence, not by file. Separate **introduced by this change** from
**existing**. Mark judgement calls as such; a documented-rule breach is hard, a
heuristic is not.

If nothing is found, say so plainly and name the passes you ran — a review that
reports nothing without saying what it checked is worth nothing.

## Dispatching

For a large diff, the `archify-reviewer` agent shipped with this plugin runs one
pass in isolation and returns findings. Dispatching several — one per pass —
keeps each reviewer's attention on one rule set, and nests cleanly inside the
Standards sub-agent `/code-review` already spawns. Do this only when the diff is
large enough to warrant it.
