# Platform

`internal/platform/` is the most dangerous directory in the tree. Every rule on
this page exists because it is the one place with no owner, no glossary and no
boundary — and therefore the place everything drifts into.

**Authorities.** Evans, ch. 14, on the shared kernel and the price of one.
Cheney, _Avoid package names like base, util, or common_, which is the same
argument from the Go side. This page's rules about **who may import platform**
are this standard's own.

## The one test

> **Would this type or function have to change because a business rule
> changed?**
>
> If yes, it is not platform. It belongs to a context — and if two contexts both
> need it, it belongs to both, separately.

`Money` as "an amount and a currency with correct arithmetic" passes. `Money` as
"the amount owed, which excludes tax before invoicing" fails, and belongs to
billing. A retry helper passes. A retry helper that knows an order may be
retried three times fails.

## The rules

1. **Nothing in `platform/` has domain meaning.** The test above, applied
   without negotiation.
2. **`platform/` imports no context.** Not a domain package, not a facade, not
   even `published/`. It is a leaf of the import graph, and that is what
   guarantees it can never become a coupling between two contexts.
3. **`domain` never imports platform.** It imports the standard library and its
   own context's `domain`. Nothing else.
   → [`../structure.md`](../structure.md)
4. **`application` never imports platform.** It declares the port it needs; the
   adapter satisfies it with a platform type. An application service that names
   `eventbus.Message` has a framework type in the use-case layer.
5. **`adapters` and `composition` import platform freely.** That is what it is
   for.
6. **A `_test.go` file anywhere may import `platform/testsupport`.** This is the
   only exception to rules 3 and 4, and it is scoped to test files.
7. **Packages are named for what they do**, and `x`-suffixed when they wrap a
   standard-library package: `httpx`, not `httputil`, `helpers` or `common`.
8. **There is no `platform/util`, `platform/common`, `platform/shared`,
   `platform/core`, `platform/base` or `platform/misc`.** If the right name is
   one of those, the package is two packages or it is nothing.
9. **A file in platform that only one context uses is in the wrong place.** Move
   it into that context's `adapters/`. Platform is for what several contexts
   genuinely share, not for what one context wanted out of the way.
10. **A shared kernel — a type with domain meaning shared between contexts — is
    permitted, lives here, and requires an ADR.** It is also rarely correct; see
    below.

## What may live here

| Package | Holds | Because |
|---|---|---|
| `config/` | Environment decoding, defaults, validation helpers | Configuration is a deployment concern, not a domain one |
| `postgres/` | Pool construction, the migration runner, retry-on-serialisation-failure, SQLSTATE mapping | Driver mechanics every context's adapters need, identically |
| `outbox/` | The relay loop, the store interface, dead-lettering | One implementation, one per context at runtime → [communication](./communication.md) |
| `eventbus/` | `Message`, `Subscription`, the in-process publisher, backoff | It carries topics and bytes and knows no context |
| `httpx/` | Middleware — request id, recovery, timeout, logging, CORS — and the problem-details error writer | Mounted once by composition, in front of every context's routes |
| `observability/` | Logger construction, tracing set-up, metric registration | Cross-cutting by definition |
| `clock/` | A real clock and a controllable one | Every context declares its own `Clock` **port**; this is the adapter both use |
| `ids/` | UUID generation, and a deterministic generator for tests | Same reasoning as `clock/` |
| `testsupport/` | Container start-up, throwaway schemas, golden-file helpers | Rule 6 exists so this is reachable from any test |

That table is close to exhaustive for a normal project. A tenth package is a
decision, not a convenience.

## What may not

| Tempting | Where it actually goes |
|---|---|
| `platform/domain/`, `platform/models/` | Nowhere. This is a fourth model with no owner → [`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md) |
| `platform/auth/` deciding **who may do what** | The context that owns the rule. Token *verification* is platform; authorisation is a domain rule |
| `platform/validation/` with business rules in it | Value object constructors, in each context's `domain` → [`../ddd/value-objects.md`](../ddd/value-objects.md) |
| `platform/events/` holding every context's event types | Each context's `published/`. A central event package is a shared model wearing a technical name |
| `platform/repository/` with a generic `Repository[T]` | Each context's `domain`. A generic repository has no aggregate's vocabulary and therefore no reason to exist → [`../ddd/repositories.md`](../ddd/repositories.md) |
| `platform/errors/` with domain error types | `domain/<agg>/errors.go`. A shared error taxonomy is a shared model → [`../ddd/errors.md`](../ddd/errors.md) |
| `platform/dto/` | The inbound adapter of whichever context owns the endpoint |
| A helper only `ordering` calls | `ordering/internal/adapters/...`. Rule 9 |

## Why `application` may not import it

Rule 4 is the one that gets argued, because importing `platform/eventbus` from
an application service is one line and works.

```go
// Wrong: the use case now speaks the bus's language. Its test needs a bus, its
// signature names a transport type, and swapping the bus edits the use case.
package command

import "myapp/internal/platform/eventbus"

func (s *PlaceOrder) Handle(ctx context.Context, cmd Cmd) error {
	...
	return s.bus.Publish(ctx, eventbus.Message{Topic: "ordering.OrderPlaced", Payload: b})
}
```

```go
// Correct: the use case declares what it needs. It records events to an outbox
// port; a platform type appears for the first time in the adapter that
// satisfies it, which is exactly where a transport belongs.
package command

// Outbox records the events an aggregate released, in the same transaction as
// the aggregate itself.
type Outbox interface {
	Record(ctx context.Context, events []order.Event) error
}
```

The test of rule 4 is mechanical: **read the imports of every file under
`application/`. A `platform/` path there is a finding.** It is also the single
easiest architecture test to write → [enforcement](./enforcement.md).

## How platform becomes the model

The decay is always the same five steps, and it takes about a year:

1. A helper is shared by two contexts, so it moves to `platform/util`.
2. Something with a *little* domain meaning goes in beside it, because moving it
   properly would have meant duplicating thirty lines.
3. A third context imports the second thing, because it is already there.
4. A business rule changes. Three contexts change, plus a package that belongs
   to none of them, in one pull request nobody can review.
5. `platform/` is now the model, and every context depends on it. The boundaries
   are decorative and have been for months.

Rules 1, 8 and 9 are aimed at steps 1 and 2. Nothing catches step 4 in time.

## The shared kernel

[`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md) permits one for types
with no domain meaning and requires an ADR. This page adds where it goes —
`internal/platform/<name>` — and one default:

**Prefer duplication.** A `Money` value object is forty lines. Three contexts
with their own `Money` can each change theirs without a conversation; three
contexts sharing one cannot change it at all. Go's own position is the right one
here: _a little copying is better than a little dependency_, and the duplicated
thing is **code**, not knowledge — billing's rounding rule and ordering's are
allowed to diverge, and one day will.
→ [`../clean-code/smells.md`](../clean-code/smells.md)

Take the shared kernel when the type is genuinely knowledge that must not
diverge — an ISO currency table, a canonical time zone list — and record the ADR
naming which contexts are now coupled.

## Wrong, and why

```go
// Wrong: platform imports a context. The import graph now has an edge from the
// place with no owner into the place with one, and a cycle is one refactor away.
package outbox

import "myapp/internal/contexts/ordering/published"

func (r *Relay) drain(ctx context.Context) error {
	var e published.OrderPlaced // the relay now knows what an order is
	...
}
```

```go
// Wrong: authorisation in platform. "Who may cancel an order" is ordering's
// rule, in ordering's glossary, and it is now in a package with neither.
package auth

func CanCancelOrder(u User, o Order) bool { return u.Role == "admin" || o.Owner == u.ID }
```

```go
// Wrong: the generic repository. It has no aggregate's vocabulary, it invites
// Get/Update/Delete, and it makes every context's persistence identical in a
// way no context asked for.
package repository

type Repository[T any] interface {
	Get(ctx context.Context, id string) (T, error)
	Save(ctx context.Context, v T) error
}
```

```go
// Wrong: a package named for nothing. Nobody can say what belongs in it, so
// everything does.
package common
```

## Checklist

- [ ] No package under `platform/` would change because a business rule changed
- [ ] No file under `platform/` imports a context — including `published/`
- [ ] No file under `domain/` or `application/` imports `platform/`, except `_test.go` importing `testsupport`
- [ ] No package named `util`, `common`, `shared`, `core`, `base` or `misc`
- [ ] Every package under `platform/` is used by at least two contexts, or by composition
- [ ] Any shared type with domain meaning has an ADR naming the contexts it couples

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 14 — Shared Kernel, and the
warning that it is the hardest relationship to maintain. Vernon, ch. 3. Martin,
_Clean Architecture_, ch. 13 ("Component Cohesion"), for the Common Closure
Principle — things that change for the same reason belong together, which is
rule 1 stated from the other direction.

**Online.** Every link below was reachable when this page was written.

- [Avoid package names like base, util, or common](https://dave.cheney.net/2019/01/08/avoid-package-names-like-base-util-or-common)
  — Cheney. Rule 8, argued properly
- [Package names](https://go.dev/blog/package-names) — the Go blog, including
  the naming convention rule 7 follows
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the Go
  team's own list, which agrees about `util`
- [Go Proverbs](https://go-proverbs.github.io/) — "a little copying is better
  than a little dependency", which is the shared-kernel default above
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — why
  everything here is under `internal/` and none of it is an external surface
