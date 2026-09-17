# Domain-Driven Design

How the model is expressed. This page is the entry point and the precedence
rule; the building blocks are one page each under [`ddd/`](./ddd/).

**Authorities.** Eric Evans, _Domain-Driven Design: Tackling Complexity in the
Heart of Software_ (2003) — the blue book. Vaughn Vernon, _Implementing
Domain-Driven Design_ (2013) — the red book.

## Precedence

The two books disagree, and an unstated disagreement is resolved by averaging,
which produces a model that is neither.

- **Vernon wins on tactical design** — aggregate size, transaction scope,
  references between aggregates, repositories, domain events, factories. His
  "Effective Aggregate Design" is a deliberate revision of Evans and it is the
  one that binds here.
- **Evans wins on strategic design** — bounded contexts, context maps,
  ubiquitous language, distillation, the shape of the whole. Vernon defers to
  him on these and so does this standard.
- **Where DDD's names collide with _Clean Architecture_'s, DDD's names win.**
  You write `Aggregate` and `Application Service`. You never write `Entity` in
  Martin's sense (his innermost layer) and you never write `Interactor`.

## The building blocks

Strategic — the shape of the whole:

| Page | Covers |
|---|---|
| [Ubiquitous language](./ddd/ubiquitous-language.md) | The glossary, and why code spells it exactly |
| [Bounded contexts](./ddd/bounded-contexts.md) | What a context is, where one ends |
| [Context mapping](./ddd/context-mapping.md) | Relationships between contexts, anti-corruption layers, published language |

Tactical — the shape of the model inside one context:

| Page | Covers |
|---|---|
| [Value objects](./ddd/value-objects.md) | The default building block |
| [Entities](./ddd/entities.md) | Identity, and typed identifiers |
| [Aggregates](./ddd/aggregates.md) | Consistency boundaries, Vernon's four rules |
| [Domain events](./ddd/domain-events.md) | Facts, produced not published |
| [Domain services](./ddd/domain-services.md) | Behaviour belonging to no aggregate |
| [Repositories](./ddd/repositories.md) | Collections of aggregates |
| [Factories](./ddd/factories.md) | When construction is its own concept |
| [Specifications](./ddd/specifications.md) | Named rules, as predicates you can ask |
| [Application services](./ddd/application-services.md) | The thin layer that orchestrates |
| [Read models](./ddd/read-models.md) | Queries that are not aggregates |
| [Errors](./ddd/errors.md) | A broken rule, expressed as a Go value |
| [Anti-patterns](./ddd/anti-patterns.md) | The failures this standard exists to prevent |

## Scope of this standard

This page and the pages under `ddd/` are the whole of the model. A modelling
rule not written on one of them does not bind, and a rule written on two of them
is a bug in the split.

- **Where code goes inside a context** is [`structure.md`](./structure.md).
- **How the contexts are packaged, wired and kept apart at runtime** is
  [`modular-monolith.md`](./modular-monolith.md) and the eight pages under
  [`modular-monolith/`](./modular-monolith/) — including the canonical project
  layout, the schema-per-context rule, and why an event still goes through the
  outbox when the consumer is in the same process.
- **What a word means**, when another standard uses it differently, is
  [`vocabulary.md`](./vocabulary.md).
- **How code reads** is [`clean-code.md`](./clean-code.md) and the eleven pages
  under [`clean-code/`](./clean-code/) — naming, functions, comments, errors
  outside the model, tests and doubles, and the list of _Clean Code_ rules that
  are **deliberately not applied in Go**. A reviewer may not report idiomatic Go
  as a finding; that page says so explicitly and names each case.

## The running example

Every page uses the same domain, so the examples compose rather than each
inventing a world:

- **`ordering`** — an `Order` aggregate with `OrderLine` entities, `Money`,
  `SKU` and `Quantity` value objects. Produces `OrderPlaced`, `OrderCancelled`.
- **`shipping`** — a `Shipment` aggregate, built from `OrderPlaced` through an
  anti-corruption layer.
- **`billing`** — an `Invoice` aggregate.

Three contexts, because the rules that matter most are the ones about what
happens between them.

## Departing from this standard

A project may depart from any rule under `ddd/`. The departure is recorded as an
ADR in that project's `docs/adr/`, naming the rule it overrules and arguing why.

**A deviation without an ADR is a defect,** not a style choice.

A reviewer treats an ADR-backed departure as settled and does not report it as a
finding. A departure without one is a finding every time it is seen.

## Sources

### The books this standard binds to

- Eric Evans, _Domain-Driven Design: Tackling Complexity in the Heart of
  Software_. Addison-Wesley, 2003. ISBN 978-0-321-12521-7. The blue book.
- Vaughn Vernon, _Implementing Domain-Driven Design_. Addison-Wesley, 2013.
  ISBN 978-0-321-83457-7. The red book.

Also cited, but not binding:

- Martin Fowler, _Patterns of Enterprise Application Architecture_.
  Addison-Wesley, 2002. ISBN 978-0-321-12742-6. Cited for Repository, Unit of
  Work, Data Mapper and Transaction Script — the patterns DDD's tactical
  building blocks are built on top of.
- Vaughn Vernon, _Domain-Driven Design Distilled_. Addison-Wesley, 2016.
  ISBN 978-0-134-43442-1. A short introduction; it adds no rules this standard
  takes from it.

### Primary material, free and online

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own distillation of every pattern definition, published 2015 under
  Creative Commons. It is the closest thing to a normative text and it is the
  only place Evans himself defines Domain Events.
  ([Direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
- [Effective Aggregate Design](https://www.dddcommunity.org/library/vernon_2011/)
  — Vernon's three-part essay, 2011. The source of the aggregate rules, and a
  deliberate revision of Evans. Where this standard says "Vernon wins on
  tactical design", this is largely what it means.
- [Specifications](https://martinfowler.com/apsupp/spec.pdf) — Evans & Fowler,
  1997. The Specification pattern before it reached the blue book.
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
  — Cockburn. The origin of `port` and `adapter`, which this standard uses in
  his sense and not in any framework's.
- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  — Martin, 2012. The dependency rule, which this standard takes and whose
  naming it rejects.

### Community material

Useful, and explicitly not authoritative — where any of these disagree with
Evans or Vernon, the books win.

- [DDD Crew](https://github.com/ddd-crew/ddd-starter-modelling-process) — the
  modelling process, with the canvases linked from it
- [martinfowler.com/tags/domain driven design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
  — Fowler's short definitions, useful for settling an argument quickly
- [microservices.io patterns](https://microservices.io/patterns/data/aggregate.html)
  — Richardson; the distributed-systems reading of the same patterns

### Go

The Go rules in these pages are not DDD, and they are not invented here:

- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments)
- [Google Go Style Guide](https://google.github.io/styleguide/go/) — and its
  [decisions](https://google.github.io/styleguide/go/decisions) and
  [best practices](https://google.github.io/styleguide/go/best-practices) pages
- [The Go Programming Language Specification](https://go.dev/ref/spec)
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — the
  visibility rule that makes a bounded context boundary a compile error
