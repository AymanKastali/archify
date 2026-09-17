# Structure

Where code goes, and which way dependencies point.

**Authorities.** Robert C. Martin, _Clean Architecture_ — the dependency rule.
Alistair Cockburn, _Hexagonal Architecture_ (2005) — the words `port` and
`adapter`. Evans and Vernon own the model, not the structure; the one place they
reach into this page is the Repository, below.

This page is the whole of structure **inside one bounded context**. Where the
contexts themselves go, and the shape of the repository around them, is
[`modular-monolith.md`](./modular-monolith.md) and the eight pages under
[`modular-monolith/`](./modular-monolith/) — that is the default architecture of
every project held to this standard.

A structural rule not written on this page or one of those does not bind.

## The regions

A bounded context is divided into four regions, and every type belongs to
exactly one.

| Region | Holds | May import |
|---|---|---|
| `domain` | Aggregates, entities, value objects, domain services, domain events, repository interfaces | The standard library, and its own context's `domain` |
| `application` | Application services (use cases), non-repository ports, transaction boundaries. Two packages: `command` and `query` | `domain` — and `query` imports not even that |
| `adapters` | Inbound (HTTP, CLI, consumers) and outbound (persistence, messaging, clock, external services) | `application`, `domain` |
| `composition` | Wiring, dependency construction, `main` | Everything. Imported by nothing |

One package sits outside the four and is imported by two of them:
`internal/platform/` holds what has **no domain meaning** — config, the database
pool, the outbox relay, the event bus, HTTP middleware, telemetry, test support.
`adapters` and `composition` may import it freely. **`domain` and `application`
may not**, because a port declared in `application` is how a platform type
reaches a use case. The exception is a `_test.go` file importing
`platform/testsupport`.
→ [`modular-monolith/platform.md`](./modular-monolith/platform.md)

## The dependency rule

Dependencies point inward. A region never names anything in a region outside it.

`domain` is the innermost region and names nothing but itself and the standard
library. It has no imports of a driver, an SDK, an HTTP type, a JSON tag, an ORM
annotation, or a logger. If the domain cannot be compiled without a database,
the dependency rule is already broken.

Inversion is how the inside reaches the outside: the inner region declares an
interface, the outer region implements it, and `composition` supplies the
implementation. The interface belongs to the region that _calls_ it, never to
the region that satisfies it.

## Where a port lives

Two rules, because the authorities genuinely disagree here and an unstated
disagreement is why an interface ends up moving between regions every time the
code is touched.

1. **A repository interface lives in `domain`.** Vernon and Evans both place the
   Repository inside the model: it is part of the aggregate's vocabulary, it
   deals in aggregates and nothing else, and the model is entitled to say "an
   Order can be fetched by its id" without leaving the model.

2. **Every other port lives in `application`,** declared beside the use case
   that calls it — clock, mailer, publisher, payment gateway, any outbound
   service. This is Cockburn's consumer-side port. *Beside* is literal: a port
   with one caller is declared in that caller's file, and there is no `ports.go`
   and no `application/port/` package.
   → [`ddd/application-services.md`](./ddd/application-services.md)

A port is named for what the caller needs, not for what implements it:
`OrderRepository`, not `PostgresOrderRepository`; `Publisher`, not `KafkaPort`.
An implementation is named for its technology and lives in `adapters/outbound`.

## Crossing a context boundary

A context never imports another context's aggregates, entities or value objects.
Other contexts are referenced **by identity only**, and contexts communicate by
domain events carrying a published language, translated at an anti-corruption
layer on the consuming side.

A shared kernel is permitted only for types with no domain meaning — money,
identifiers, timestamps. Adding to it requires an ADR, and the default is to
duplicate instead.
→ [`modular-monolith/platform.md`](./modular-monolith/platform.md)

**The mechanics of getting a message across that boundary in one process** —
the outbox that still applies, the in-process bus, and the narrow case for a
synchronous call — are
[`modular-monolith/communication.md`](./modular-monolith/communication.md).
**Schema per context, and the transaction rule**, are
[`modular-monolith/data.md`](./modular-monolith/data.md).

## The Go layout

```text
cmd/app/main.go                                flags, signals, exit code
internal/composition/                          the binary's composition root
internal/contexts/<ctx>/<ctx>.go               the context's facade — construction and delegation
internal/contexts/<ctx>/published/             published language: event types, identifiers
internal/contexts/<ctx>/migrations/            this context's schema, owned by nobody else
internal/contexts/<ctx>/internal/domain/       one package per aggregate; value objects; events; repository interfaces
internal/contexts/<ctx>/internal/application/command/  use cases that change state; the ports they call
internal/contexts/<ctx>/internal/application/query/    read models, and the ports that answer them
internal/contexts/<ctx>/internal/adapters/     inbound/ and outbound/
internal/platform/                             technical, no domain meaning
```

**The full tree — every directory, what goes in each and what never does — is
[`modular-monolith/layout.md`](./modular-monolith/layout.md).** It is the
canonical layout, not a starting point to adapt.

The nested `internal/` is doing real work. Go permits a package under
`a/internal/b` to be imported only from within `a`, so a sibling context cannot
import another context's guts — it fails to compile rather than failing review.
Each context exposes exactly two packages: the facade for the composition root,
and `published/` for other contexts.

An aggregate is a package, because in Go the package is the encapsulation
boundary and the struct is not: fields are unexported, and the type is
constructed by a function returning `(T, error)` so an aggregate cannot exist in
an invalid state.

### `composition` exists at two levels

The region table above lists `composition` as a region of a context. In the
modular monolith that is the default here, it appears twice and the two are not
interchangeable:

| | Knows | Builds |
|---|---|---|
| `internal/contexts/<ctx>/<ctx>.go` | Only this context | This context's adapters and application services. Returns the facade |
| `internal/composition/` | Every context, and `platform/` | The pool, the logger, the bus — then calls each context's `New` and wires the results |

`internal/composition/` never reaches past a facade. It cannot: the nested
`internal/` forbids it.
→ [`modular-monolith/composition.md`](./modular-monolith/composition.md)

## What enforces this

- **The compiler.** Context boundaries, via the nested `internal/`. And layering
  inside a context: once `application` imports `domain`, `domain` importing
  `application` is an import cycle and will not build.
- **depguard**, in `.golangci.yml`. The import bans in the region table, stated
  as rules.
- **An architecture test**, for the path rules depguard cannot state — that only
  `published/` crosses a context boundary, that it is translated in `adapters`,
  and that `platform` depends on no context.
- **A review agent**, for what a tool cannot see — whether a type is in the right
  region at all, whether a port is named for its caller, whether something in
  `domain` is really a domain concept, and the one failure no import graph
  reveals: **a cross-context join**.

The full arrangement, with the `.golangci.yml` and the architecture test, is
[`modular-monolith/enforcement.md`](./modular-monolith/enforcement.md).

## Departing from this page

A project may depart from any rule here. The departure is recorded as an ADR in
that project's `docs/adr/`, naming the rule it overrules and arguing why.

**A deviation without an ADR is a defect,** not a style choice.

## Sources

**Books.** Robert C. Martin, _Clean Architecture_ (Prentice Hall, 2017,
ISBN 978-0-134-49416-6), Part V, for the dependency rule. Evans, ch. 4, for the
layered architecture it replaces. Vernon, ch. 4, which is the best treatment of
hexagonal architecture inside a DDD book.

**Online.** Every link below was reachable when this page was written.

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
  — Cockburn's own page. `port` and `adapter` mean what he says they mean
- [Hexagonal Architecture explained](https://jmgarridopaz.github.io/content/hexagonalarchitecture.html)
  — Garrido de Paz, written with Cockburn's involvement; the clearest account of
  what a port actually is, and of why "one port per adapter" is wrong
- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  — Martin, 2012
- [Solid Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html)
  — Martin, 2020, on which of these principles he still considers load-bearing
- [Organizing a Go module](https://go.dev/doc/modules/layout) — the Go team's
  own guidance on layout, which is deliberately thin
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — the
  mechanism the nested `internal/` layout on this page depends on
- [Package names](https://go.dev/blog/package-names) — why `domain/order` is a
  better package than `domain/models`
