# Modular monolith

The default architecture of every Go project held to this standard: **one
module, one binary, one database instance — and bounded contexts that are
separated as strictly as if they were separate services.**

This page is the entry point and the ruling on what a module is; the rules are
one page each under [`modular-monolith/`](./modular-monolith/).

**Authorities.** Evans, ch. 14, for the boundary being a model boundary and not
a process boundary. Vernon, ch. 2, for the architecture that boundary implies.
Sam Newman, _Monolith to Microservices_ (2019), ch. 1 and 3 — which argues for
this shape more forcefully than most microservices books do, and supplies the
extraction patterns. Martin Fowler, _MonolithFirst_ (2015). Kamil Grzybek's
_Modular Monolith: A Primer_ is the clearest single write-up of the pattern and
is cited throughout; it is not a book and it does not bind.

## Why this is the default

A bounded context is a **model** boundary. A process is a **deployment**
boundary. Conflating them is the single most expensive mistake in this space,
and it runs in both directions:

- **Contexts collapsed into one model** because they ship in one binary. That is
  the big ball of mud, and it is what the rest of this corpus prevents.
- **Contexts split into services** to get a boundary. That buys a compiler-free
  boundary at the price of network partitions, partial failure, distributed
  transactions, version skew and an operational budget — to obtain something the
  Go compiler will enforce for nothing.

The modular monolith takes the boundary and refuses the bill. You get the
enforcement **at compile time**, which is stricter than what a network gives
you: a service can be called by anyone who can reach its port, but a package
under `internal/` cannot be imported by anyone who is not inside.

> **"Modular" is a property of the source. "Monolith" is a property of the
> deployment. They are independent.** This standard makes the first mandatory
> and the second the default. A project that is modular may become distributed
> later; a project that is not modular cannot, at any price it will want to pay.

## The ruling: a module is a bounded context

**One to one. No exceptions without an ADR.**

Most writing about modular monoliths leaves "module" undefined, and the word
immediately fills with whatever the team already had: a `notifications` module,
an `auth` module, a `common` module, a `shared` module. Within a year the top
level of the repository is a list of technical concerns and the boundary is
decorative.

So the word is pinned:

| Candidate | Is it a module? |
|---|---|
| `ordering`, `shipping`, `billing` — its own language, its own invariants, its own glossary | **Yes.** This is a bounded context |
| `notifications` — with a `Notification` aggregate, delivery rules, retry invariants, a `CONTEXT.md` | **Yes.** It earned it by having a model |
| `notifications` — a function that calls SendGrid | **No.** It is an outbound adapter in the module that needs it |
| `auth` — issuing and verifying tokens, no business rules | **No.** Platform. See [platform](./modular-monolith/platform.md) |
| `identity` — users, organisations, membership, the rules about who may join what | **Yes.** A context |
| `shared`, `common`, `core`, `utils` | **No**, and it is not a directory either |
| `api`, `handlers`, `services`, `repositories` | **No.** These are regions inside a module, not modules |

**The test is the glossary.** A module has a `CONTEXT.md` with terms whose
meanings are contested elsewhere in the business. If you cannot write one, you
do not have a module — you have a package, or you have platform.

### The word is taken twice, so the directory is `contexts/`

`module` already means two other things in scope here, and this standard does
not coin a synonym to dodge a collision — it maps, and it picks one word to
write:

| Who says it | What they mean |
|---|---|
| **Go** | The unit `go.mod` declares. A project held to this standard has exactly **one** |
| **`/codebase-design`** | A Go package — see [`vocabulary.md`](./vocabulary.md) |
| **This page** | A bounded context, deployed in the same binary as the others |

Because two of the three were there first, **the directory is
`internal/contexts/`**, the word written in code and in review is **context**,
and "module" is used only when talking about the architecture as a shape. A
repository with `internal/modules/` in it is right in spirit and wrong in this
standard.

## The six properties

A monolith is modular when all six hold. **With five of them it is a monolith.**

1. **A module is a bounded context, one to one.**
   → [modules](./modular-monolith/modules.md)
2. **A module's interior is private at compile time** — not by convention, not
   by lint, by `internal/`.
   → [enforcement](./modular-monolith/enforcement.md)
3. **A module publishes exactly two things:** a facade for the composition root,
   and `published/` for other modules. Nothing else is reachable.
   → [modules](./modular-monolith/modules.md)
4. **Every cross-module call leaves through an adapter on the caller's side,**
   even when the callee is a function call away in the same process.
   → [communication](./modular-monolith/communication.md)
5. **A module owns its data exclusively.** Its own schema, its own migrations,
   no cross-module join, no cross-module foreign key, **no cross-module
   transaction.**
   → [data](./modular-monolith/data.md)
6. **There is one composition root.** One `go.mod`, one binary, one file where
   modules are constructed and wired, and nothing else knows the module list.
   → [composition](./modular-monolith/composition.md)

### The test that actually matters

Not how the repository looks. This:

> **If one module had to become a separate service on Monday, what would
> change?**
>
> The correct answer is **the composition root, plus one outbound adapter per
> cross-module call, plus deployment.** No domain file. No application service.
> No aggregate. No test of the model.
>
> Any other answer means the modularity was decorative — and you will discover
> that during the extraction, which is the most expensive moment available.

Every rule in this corpus exists to keep that answer true.
See [extraction](./modular-monolith/extraction.md).

## The pages

| Page | Covers |
|---|---|
| [Layout](./modular-monolith/layout.md) | **The canonical project tree**, directory by directory — what goes in each, and what never does |
| [Modules](./modular-monolith/modules.md) | The module's public surface, the facade, sizing, when to add one and when to merge two |
| [Communication](./modular-monolith/communication.md) | In-process events, the outbox that still applies, and the narrow case for a synchronous cross-module call |
| [Data](./modular-monolith/data.md) | Schema per module, migrations, the transaction rule, and cross-module reads |
| [Composition](./modular-monolith/composition.md) | `main`, the module registry, lifecycle and shutdown, config, run modes |
| [Platform](./modular-monolith/platform.md) | `internal/platform/` — what is allowed in it, and why it is the most dangerous directory in the tree |
| [Enforcement](./modular-monolith/enforcement.md) | The compiler, depguard, an architecture test in Go, CI — and what none of them catch |
| [Extraction](./modular-monolith/extraction.md) | Turning a module into a service, mechanically. And the argument for not doing it |

## What this page owns

The split is strict, because a rule written twice drifts.

| Question | Page |
|---|---|
| Where a file goes **inside one module**, and which way its dependencies point | [`structure.md`](./structure.md) — the four regions |
| Where the modules go, and the shape of the whole repository | [layout](./modular-monolith/layout.md) |
| **Whether** two things are one context or two | [`ddd/bounded-contexts.md`](./ddd/bounded-contexts.md) |
| **How** a context is packaged, surfaced and wired once you have decided | [modules](./modular-monolith/modules.md) |
| Which relationship pattern two contexts have, and what an ACL does | [`ddd/context-mapping.md`](./ddd/context-mapping.md) |
| The mechanics of getting a message from one module to another in one process | [communication](./modular-monolith/communication.md) |
| What a domain event is, and the outbox rule | [`ddd/domain-events.md`](./ddd/domain-events.md) |

Where a page here and a page under `ddd/` both apply, **the `ddd/` page is the
more specific rule and a finding cites it.**

## What "modular monolith" does not mean here

Every item below is something the phrase is used for elsewhere, and every one is
rejected in this standard. They are listed once, here, so no review re-argues
them.

| Claimed as modular-monolith practice | This standard |
|---|---|
| One `go.mod` per module, in a workspace | **No.** One `go.mod`. Multi-module workspaces buy independent versioning, which is the cost of distribution without the benefit → [layout](./modular-monolith/layout.md) |
| A runtime plugin system — modules registered by reflection or a DI container | **No.** Modules are constructed by hand in one file. If you cannot read the wiring, you cannot review the dependency direction → [composition](./modular-monolith/composition.md) |
| A top level of `handlers/`, `services/`, `repositories/`, `models/` | **No.** That is layering the whole application by technical concern; the boundary that matters never appears → [layout](./modular-monolith/layout.md) |
| `pkg/` for the "public" half and `internal/` for the private half | **No.** Everything is under `internal/`. A product has no external importers, and `pkg/` is not a Go convention → [layout](./modular-monolith/layout.md) |
| A mediator or command bus in front of every use case | **No.** An application service is called directly. A bus buys indirection and loses the call graph → [composition](./modular-monolith/composition.md) |
| "Microservices-ready" modules that call each other's services directly | **No.** That is the direct-import failure with an aspirational name. Cross-module calls leave through an adapter → [communication](./modular-monolith/communication.md) |
| Modules deployable independently | **No.** That is the definition of not being a monolith. The value here is one deployment; claiming both pays both prices → [extraction](./modular-monolith/extraction.md) |
| Synchronous in-process calls between modules because "it is the same process anyway" | **Narrow and conditional**, never the default, and never a write → [communication](./modular-monolith/communication.md) |
| One shared schema with a table-name prefix per module | **No.** A prefix is a naming convention; a schema is a permission boundary → [data](./modular-monolith/data.md) |
| A `shared` or `common` module | **No.** There is `internal/platform/`, it holds nothing with domain meaning, and adding to it takes an ADR → [platform](./modular-monolith/platform.md) |

## When a monolith is the wrong answer

The default is not a law. Take a separate deployable when you want something
only a separate deployable gives, and say which:

- **Independent scaling** of a genuinely different load profile — a video
  transcoder, an ML inference path — where the resource shape, not the code, is
  the reason.
- **Independent release cadence** forced by an organisational boundary: a
  different team, a different compliance regime, a different on-call rotation.
- **A different runtime.** The model is in Go and the thing is not.
- **Blast-radius isolation** that is a stated requirement, not a preference.

None of these is "the codebase is getting big", "we might need to scale later",
or "the boundary will be clearer". The first is a module problem, the second is
[`MonolithFirst`][mf], and the third is the claim this whole corpus exists to
falsify — a network call is a *worse* boundary than a compile error, because it
can be made by anyone and it fails at three in the morning instead of at
`go build`.

Taking a separate deployable is a **deviation from this page** and is recorded
as an ADR naming which of the four reasons above applies.

## Departing from this standard

A project may depart from any rule under `modular-monolith/`. The departure is
recorded as an ADR in that project's `docs/adr/`, naming the rule it overrules
and arguing why.

**A deviation without an ADR is a defect,** not a style choice. A reviewer
treats an ADR-backed departure as settled and does not report it.

## Sources

### Books

- Sam Newman, _Monolith to Microservices: Evolutionary Patterns to Transform
  Your Monolith_. O'Reilly, 2019. ISBN 978-1-492-04784-1. Chapter 1 defines the
  modular monolith and argues it is an under-used option; chapter 3 is the
  extraction pattern catalogue [extraction](./modular-monolith/extraction.md)
  draws on.
- Sam Newman, _Building Microservices_, 2nd ed. O'Reilly, 2021.
  ISBN 978-1-492-03402-5. Chapter 1, for the information-hiding argument that
  applies identically in one process.
- Eric Evans, _Domain-Driven Design_. Addison-Wesley, 2003. Chapter 14, for the
  bounded context being a boundary of meaning rather than of deployment.
- Vaughn Vernon, _Implementing Domain-Driven Design_. Addison-Wesley, 2013.
  Chapter 2 ("Domains, Subdomains, and Bounded Contexts") and chapter 4
  ("Architecture").
- Vaughn Vernon & Tomasz Jaskuła, _Strategic Monoliths and Microservices_.
  Addison-Wesley, 2021. ISBN 978-0-137-35546-4. Cited, not binding: the
  book-length version of the argument on this page.

### Online

Every link below was reachable when this page was written.

- [Modular Monolith: A Primer](https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer)
  — Grzybek. The clearest statement of the pattern and of the properties a
  module must have; the six properties above are a stricter, Go-specific reading
  of his list
- [modular-monolith-with-ddd](https://github.com/kgrzybek/modular-monolith-with-ddd)
  — the same author's full reference implementation. C#, and worth reading for
  the module-contract mechanics even so
- [MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html) — Fowler,
  2015, on why the boundaries you would draw on day one are the wrong ones
- [MicroservicePremium](https://martinfowler.com/bliki/MicroservicePremium.html)
  — Fowler, 2015. The price list this page is refusing to pay
- [PresentationDomainDataLayering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html)
  — Fowler, on why layering the *whole application* by technical concern is the
  wrong top-level split
- [Towards Modern Development of Cloud Applications](https://sigops.org/s/conferences/hotos/2023/papers/ghemawat.pdf)
  — Ghemawat et al., HotOS 2023 (Google). Argues directly that applications
  should be written as modular monoliths and the distribution decision deferred
  to deployment, with measurements
- [Deconstructing the Monolith](https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity)
  — Shopify, on adopting a modular monolith at a scale where the microservices
  argument is usually assumed to have been won
- [Modular Monoliths](https://www.youtube.com/watch?v=5OjqD-ow8GE) — Simon
  Brown's talk, which is where most current use of the term traces from
- [Pattern: Monolithic architecture](https://microservices.io/patterns/monolithic.html)
  — Richardson; the honest statement of the trade-off from the other side
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — the
  `go` command rule that makes property 2 a compile error
- [Go Modules Reference](https://go.dev/ref/mod) — for the first meaning of
  "module" in the collision table above

[mf]: https://martinfowler.com/bliki/MonolithFirst.html
