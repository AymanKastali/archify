# Vocabulary

archify is not the only standard in the room.

The engineering workflow is [Matt Pocock's skills][skills] — `/grill-with-docs`,
`/to-spec`, `/to-tickets`, `/implement`, `/tdd`, `/code-review`. archify is the
standard that workflow applies when the project is Go with DDD and hexagonal
architecture. The two overlap in subject matter and use different words for
some of the same things.

This page is the mapping and the precedence. Read it once; it prevents the
argument where two correct standards look like they contradict each other.

## Precedence

**The workflow owns process words. archify owns model words. Neither renames
the other's.**

| Kind of word | Owner | Examples |
|---|---|---|
| How work moves | `/ask-matt`'s flow | spec, ticket, blocking edge, triage role, phase boundary, frontier |
| How a module is shaped | `/codebase-design` | module, interface, depth, seam, adapter, leverage, locality |
| How the glossary is kept | `/domain-modeling` | `CONTEXT.md`, ADR, term, `_Avoid_` |
| What is being modelled | archify | aggregate, entity, value object, repository, domain event, port, bounded context, region |
| How the whole repository is shaped | archify | modular monolith, context, facade, published language, platform, composition root |

When a word appears in both columns, the table below says which meaning is
live. There is no third meaning, and archify never invents a synonym to dodge
a collision.

## The mapping

| `/codebase-design` says | archify says | Relationship |
|---|---|---|
| **Module** | Go package | Same idea. archify is stricter: the package, not the struct, is the encapsulation unit, so `domain/order` is one module however many types it holds. **The word is contested three ways — see below** |
| **Interface** — everything a caller must know | **Port**, when the interface crosses a region | Every port is an interface in Matt's sense. Not every interface is a port: an interface inside one region is a module interface, not a port |
| **Seam** — where behaviour can be altered without editing in place | The region edge where a port sits | Ports are seams. Seams inside `domain` are not ports and get no adapter |
| **Adapter** — a concrete thing satisfying an interface at a seam | **Adapter**, Cockburn's sense | Same word, archify narrower: only code in the `adapters` region, plus the test fakes that stand in for it |
| **Depth** — behaviour per unit of interface | An aggregate's method set | An aggregate is the deepest module in the codebase by construction: every invariant behind a handful of business-named methods and no exported fields |
| **Boundary** — *avoided*, as overloaded with DDD | **Bounded context**, and nothing else | `/codebase-design` gives the word up deliberately, so DDD keeps it. Use **seam** for the test/interface location, **bounded context** for the model edge. Never "layer boundary" — say **region** |
| **Locality**, **Leverage** | no archify term | Adopt as-is. Nothing here competes |

### "Module" means three things, so archify writes "context"

| Who says it | What they mean |
|---|---|
| **Go** | The unit `go.mod` declares. A project held to this standard has exactly one |
| **`/codebase-design`** | A Go package, as in the row above |
| **The modular-monolith literature** | A bounded context deployed in the same binary as the others |

The third is what
[`modular-monolith.md`](./modular-monolith.md) is about, and because the first
two were there first, **archify writes _context_ and the directory is
`internal/contexts/`.** "Module" is used only when naming the architecture as a
shape — "a modular monolith" — never for a directory, a type, or a review
finding. A repository with `internal/modules/` in it is right in spirit and
wrong in this standard.

The same discipline applies to the facade type: not `ordering.Module`, and not
`ordering.Context` either — that one collides with `context.Context`. See
[`modular-monolith/modules.md`](./modular-monolith/modules.md).

Two words carry a meaning archify refuses outright:

- **Entity.** In DDD an entity is a thing with identity and a lifecycle. In
  _Clean Architecture_ it is the innermost layer. **DDD's meaning is the live
  one** — see [entities](./ddd/entities.md). Martin's sense is never written.
- **Service.** Unqualified, it means nothing. Write **domain service** or
  **application service**; they are different things with different rules.

## Two rules that look like they collide and do not

### "One adapter means a hypothetical seam"

`/codebase-design` says: _one adapter means a hypothetical seam, two adapters
means a real one — don't introduce a seam unless something actually varies
across it._

A repository port in `domain` has exactly one production adapter, so this looks
like a violation. It is not, for two reasons:

1. **The port exists for direction, not variation.** Without it, `domain`
   imports a driver and the dependency rule is broken at the innermost region.
   Matt's rule is about interfaces added speculatively; this one is load-bearing
   the day it is written. See [structure](./structure.md).
2. **There are two adapters.** Postgres in production, an in-memory fake under
   test. The seam is real the moment the first test uses it.

A port with one adapter and no fake *is* the hypothetical seam Matt is warning
about. Delete it or write the test.

### "Middle Man"

The Fowler smell baseline in `/code-review` flags **Middle Man** — a module
that mostly delegates onward — and says to cut it and call the real target
direct.

An application service is mostly delegation. That is its job: load the
aggregate, call one business method, save, release events. Behaviour in it
would be the defect. See
[application services](./ddd/application-services.md).

`/code-review`'s own rule settles this: _the repo overrides; a documented repo
standard always wins._ archify is the documented standard, so the application
service is not reported.

The same override applies to **Repeated Switches**, which the baseline says to
replace with polymorphism. A type switch over a closed set of domain events in
a dispatcher is idiomatic Go and stays.

The baseline collisions run one way only. **Primitive Obsession**, **Data
Clumps**, **Message Chains** and **Feature Envy** are all things archify
already forbids more strictly — where they agree, both bind, and the finding
cites the archify page because it is the more specific rule.

## Sources

**Books.** John Ousterhout, _A Philosophy of Software Design_, ch. 4 — modules
should be deep; the source of `/codebase-design`'s depth idea. Michael
Feathers, _Working Effectively with Legacy Code_, ch. 4 — the seam model, the
source of the word. Martin Fowler, _Refactoring_ (2nd ed.), ch. 3 — the smell
catalogue `/code-review` uses as its baseline. Eric Evans, _Domain-Driven
Design_, ch. 14 — Bounded Context, the reason `/codebase-design` gives up the
word "boundary".

**Online.**

- [mattpocock/skills](https://github.com/mattpocock/skills)
  — the workflow this standard runs underneath; `/ask-matt` is its router and
    the map of how the flows connect
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
  — Cockburn's own page, the origin of `port` and `adapter`
- [A Philosophy of Software Design](https://web.stanford.edu/~ouster/cgi-bin/book.php)
  — Ousterhout's book page; deep modules, and why a thin interface is the goal
- [Refactoring catalog](https://refactoring.com/catalog/)
  — Fowler's smells and their named remedies, free and canonical
- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  — Martin's original post, including the Entity naming this page overrules
- [BoundedContext](https://martinfowler.com/bliki/BoundedContext.html)
  — Fowler's short definition, useful when the word is the argument

[skills]: https://github.com/mattpocock/skills
