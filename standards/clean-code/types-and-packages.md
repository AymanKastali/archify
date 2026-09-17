# Types and packages

_Clean Code_ chapters 6 and 10 — "Objects and Data Structures" and "Classes" —
re-seated on the two things Go actually has.

**Authority.** Martin, _Clean Code_, ch. 6 and ch. 10 — both bind, with the unit
changed. Martin, _Clean Architecture_, Part III, for SRP, which is on its own
page: [SOLID](./solid.md). Fowler, [Tell Don't
Ask](https://martinfowler.com/bliki/TellDontAsk.html) and [Anemic Domain
Model](https://martinfowler.com/bliki/AnemicDomainModel.html).

## Why it exists

Go has no classes. It has structs, which are data with methods attached, and
packages, which are the only place `unexported` means anything. Chapter 10's
rules are all about classes, and transplanting them onto structs produces the
wrong answer, because **in Go the struct is not the encapsulation boundary. The
package is.**

```go
package order

type Order struct {
	lines []Line // unexported: invisible outside `order`
}

func (l Line) discount() Money { ... }   // and so is this
```

Everything in `package order` can reach `Order.lines` directly. Nothing outside
it can. So "make the class small" is the wrong instruction; the correct one is
**make the package's exported surface small**, and then let the types inside it
cooperate as closely as the model requires. This is exactly why
[aggregates](../ddd/aggregates.md) makes the aggregate a package rather than a
struct.

## Chapter 6: objects and data structures

Martin's anti-symmetry is the most useful idea in either chapter, and it
transfers to Go untouched:

> Objects hide their data behind abstractions and expose functions that operate
> on that data. Data structures expose their data and have no meaningful
> functions.

And the corollary he draws immediately after:

> Hybrids … are the worst of both worlds.

A hybrid is a struct with exported fields **and** business methods. In DDD that
has a name — the [anaemic domain model](../ddd/anti-patterns.md) — and it is the
failure this whole standard is built to prevent.

The rule is therefore not "prefer objects". It is: **decide which one each type
is, by region, and never build one that is both.**

| Region | Kind | Shape |
|---|---|---|
| `domain` — aggregates, entities, value objects | **Object** | All fields unexported. Behaviour only. No setters |
| `application` — commands, queries, results | **Data structure** | Exported fields, no methods, primitives at the edge |
| `adapters` — row types, wire DTOs, request/response bodies | **Data structure** | Exported fields, struct tags, no behaviour |
| `application`/`domain` — ports and repository interfaces | **Behaviour, no data** | An interface. Named for the caller's need |
| `platform` | Either, consistently | Whatever the technical concern is |

A row type and an aggregate are never the same type. Mapping between them is
the adapter's job, and it is the price of keeping the model clean — see
[value objects](../ddd/value-objects.md) for the `toRow`/`fromRow` pattern.

### Tell, don't ask

```go
// Wrong. The caller pulls state out, decides, and pushes state back. The rule
// now lives in `application`, and every other caller must repeat it.
if o.Status() == order.StatusDraft && len(o.Lines()) > 0 {
	o.SetStatus(order.StatusPlaced)
	o.SetPlacedAt(time.Now())
}
```

```go
// Correct. The caller states intent; the aggregate owns the decision and the
// transition, and there is exactly one place the rule is written.
if err := o.Place(uc.clock.Now()); err != nil {
	return err
}
```

The wrong version is the anaemic model in three lines, and it is arrived at by
adding one getter at a time. That is why
[aggregates](../ddd/aggregates.md) bans exported fields and setters outright
rather than discouraging them.

### The Law of Demeter, and train wrecks

Martin's statement: a method should only call methods on itself, its parameters,
objects it creates, and its own fields. Not on objects returned by other calls.

```go
// Wrong. A train wreck, and worse: `shipping` is now coupled to the internal
// shape of `ordering`'s Order, four levels deep.
country := shipment.Order().Customer().Address().Country()
```

```go
// Correct within one context: ask the thing you have for what you need.
country := shipment.DestinationCountry()
```

```go
// Correct across contexts: you do not hold the other aggregate at all. You hold
// its identity, and the data you were given in the event that told you about it.
type Shipment struct {
	orderID     ordering.OrderID // identity only
	destination Address          // copied at construction, from the event
}
```

This is Fowler's **Message Chains** smell, and where it overlaps this standard,
the archify rule is stricter and more specific: [aggregates](../ddd/aggregates.md)
requires other aggregates to be referenced **by identity**, which makes a chain
past the first `.` impossible to write. A review finding cites that page.

Two exceptions that are not violations:

- **Fluent construction on a value you own** — a builder returning itself, a
  `strings.Builder`. The chain is one object, not four.
- **A data structure.** Demeter is about objects hiding data. Reaching into a
  row type or a decoded JSON body is fine; that type exists to be read.

## Chapter 10: classes, re-seated on the package

| Martin says | In Go |
|---|---|
| Classes should be small | **Packages should have a small exported surface.** Ten exported identifiers is a lot. A package exporting thirty is two packages |
| Small means responsibilities, not lines | Unchanged, and now measured on the package |
| The Single Responsibility Principle | One package, one reason to change — see [SOLID](./solid.md) |
| Cohesion: methods should use the instance variables | **Cohesion: every file in the package should need the package's unexported types.** A file that could compile alone belongs in another package |
| Maintaining cohesion produces many small classes | Produces many small packages, which Go supports better than most languages |
| Organising for change | Unchanged — a new requirement should add a file, not edit five |
| Isolating from change (DIP) | Ports. Already structural here — see [`structure.md`](../structure.md) |

### The cohesion test

Ask of every package: **if I deleted one file, would the rest still make
sense?** If yes, that file was a lodger.

```text
Good — one aggregate, every file needs the others:
    order/{order,line,id,money,status,events,errors,repository}.go

Bad — four unrelated things sharing a package because they were all "domain":
    domain/{order,customer,invoice,shipment,utils}.go
```

The bad version cannot enforce anything: `Invoice` can reach into `Order`'s
unexported fields, so the aggregate's invariant is enforced by discipline rather
than by the compiler. One aggregate per package is what makes the encapsulation
real.

## Interfaces

Go's interfaces are structural, which changes where they should be declared, and
this is the single most common structural error in Go DDD codebases.

1. **An interface is declared by the consumer, not the producer.** The package
   that *calls* `Publish` declares `Publisher`. The package that implements it
   imports nothing and does not know the interface exists. This is what makes
   the dependency rule work; see [`structure.md`](../structure.md).
2. **Accept interfaces, return structs.** A constructor returns its concrete
   type so callers can use everything it offers; parameters are interfaces so
   callers can substitute.
3. **Keep them small.** One to three methods. A five-method port is usually two
   ports — this is ISP, and it is on [SOLID](./solid.md).
4. **Do not write an interface until there is a caller that needs one.** In Go,
   adding one later is a non-event: no implementation has to change. Speculative
   interfaces are the "hypothetical seam" `/codebase-design` warns about — see
   [`vocabulary.md`](../vocabulary.md) for why a repository port is not one.
5. **No `any` in a domain signature.** It defeats every guarantee the rest of
   this corpus is built on. The one tolerated use is the event slice an
   aggregate releases, which is a language limitation, not a design choice.

```go
// Wrong. Interface declared beside the implementation, in adapters, and the
// application now imports outward to name it.
package postgres

type OrderStore interface { // nobody in `postgres` calls this
	ByID(context.Context, order.OrderID) (*order.Order, error)
}

type orderStore struct{ db *sql.DB }      // returning an interface, too
func NewOrderStore(db *sql.DB) OrderStore { return &orderStore{db} }
```

```go
// Correct. The interface lives with its caller; the adapter names the concrete
// type and knows nothing about the interface it happens to satisfy.
package order // domain

type Repository interface {
	ByID(ctx context.Context, id OrderID) (*Order, error)
	Save(ctx context.Context, o *Order) error
}
```

```go
package postgres // adapters/outbound

type OrderRepository struct{ db *sql.DB }

func NewOrderRepository(db *sql.DB) *OrderRepository { return &OrderRepository{db: db} }
```

## Embedding is not inheritance

```go
// Wrong. Embedding used to share implementation, which promotes every method of
// BaseAggregate into Order's public API — including ones that break it.
type BaseAggregate struct {
	ID      string
	Version int
}

func (b *BaseAggregate) SetID(id string) { b.ID = id }

type Order struct {
	BaseAggregate // Order now has SetID. The invariant is gone
	lines         []Line
}
```

```go
// Correct. Composition by a named, unexported field. Nothing is promoted;
// Order exposes exactly what Order chooses to.
type Order struct {
	id      OrderID
	version version
	lines   []Line
}
```

Embedding is for **interface satisfaction and delegation**, not for reuse. A
`Base…` type in `domain` is a Java instinct, and the methods it promotes are
almost always setters — which [aggregates](../ddd/aggregates.md) bans.

## Zero values

Go initialises every struct to its zero value, and there are exactly two
positions a type may take:

- **The zero value is usable and documented.** `bytes.Buffer`, `sync.Mutex`, a
  read model, an `application` command. Say so in the doc comment.
- **The zero value is invalid and construction is mandatory.** Every value
  object, entity and aggregate in this standard. Enforced by unexported fields,
  so the zero value cannot be produced outside the package.

What is forbidden is the third position: a type whose zero value is *sometimes*
usable and whose constructor is *optional*. That is what turns "the invariant
holds" into "the invariant usually holds". Martin's "don't return null, don't
pass null" lands here — Go's answer is not null-object wrappers, it is making
the zero value either meaningful or unreachable.

## Common mistakes

| Mistake | What it looks like | Consequence |
|---|---|---|
| Hybrid type | Exported fields plus business methods | The anaemic model; the invariant is advisory |
| One `domain` package | Four aggregates sharing unexported fields | Encapsulation is discipline, not compilation |
| Interface beside its implementation | `postgres.OrderStore` | Dependency points outward; the port is untestable in isolation |
| Returning an interface from a constructor | `func New() Store` | Callers lose access to the concrete type for no gain |
| Five-method port | `type Infra interface { … }` | Every fake implements five methods to test one |
| `Base…` embedding | `BaseAggregate` | Promotes setters into the aggregate's API |
| Train wreck | `a.B().C().D()` | Couples the caller to a structure it does not own |
| Row type used as the aggregate | `json:` tags in `domain` | Persistence in the model; see [anti-patterns](../ddd/anti-patterns.md) |
| `any` in a domain signature | `func Apply(e any) error` | Type safety abandoned at the one place it mattered |
| Package exporting thirty identifiers | `package core` | Not a module; a namespace |

## Checklist

- [ ] Every type is an object or a data structure; none is both
- [ ] `domain` types have no exported fields and no setters
- [ ] Row types and DTOs live in `adapters`, never in `domain`
- [ ] One aggregate per package
- [ ] Each package's exported surface is small and deliberate
- [ ] Every file in a package needs that package's unexported types
- [ ] Interfaces are declared by their consumers and have one to three methods
- [ ] Constructors return concrete types; parameters are interfaces
- [ ] No embedding for reuse; no `Base…` types in `domain`
- [ ] Every type's zero value is either documented as usable or unreachable
- [ ] No chained calls past the object you were handed

## Sources

**Books.** Martin, _Clean Code_, ch. 6 — "Objects and Data Structures", for the
anti-symmetry and the Law of Demeter, and ch. 10 — "Classes", for cohesion and
organising for change. Martin, _Clean Architecture_, Part III, for SRP and DIP,
which are treated on [SOLID](./solid.md). Fowler, _Refactoring_ (2nd ed.), ch. 3,
for Message Chains, Middle Man and Feature Envy — and
[`vocabulary.md`](../vocabulary.md) for the two of those this standard
overrides.

**Online.** Every link below was reachable when this page was written.

- [Tell Don't Ask](https://martinfowler.com/bliki/TellDontAsk.html) — Fowler,
  including the caveat that it is a heuristic and not an absolute
- [Anemic Domain Model](https://martinfowler.com/bliki/AnemicDomainModel.html)
  — Fowler, on what the hybrid type costs
- [The Law of Demeter](https://www.ccs.neu.edu/home/lieber/LoD.html) — Lieberherr
  and Holland's own page for the principle Martin cites
- [Effective Go: embedding](https://go.dev/doc/effective_go#embedding) — what
  embedding is for, from the Go team, and what it is not
- [Effective Go: interfaces](https://go.dev/doc/effective_go#interfaces_and_types)
  — structural typing, and why the consumer declares the interface
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the
  "interfaces" section, which states the accept-interfaces/return-structs rule
  and the rule against defining an interface before there is a user
- [Go Proverbs](https://go-proverbs.github.io/) — "The bigger the interface, the
  weaker the abstraction"
