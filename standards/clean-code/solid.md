# SOLID

The five principles, re-expressed for a language with no inheritance, and mapped
onto the places this standard already enforces them.

**Authority.** Martin, _Clean Architecture_, Part III. Not _Clean Code_ — SOLID
is barely mentioned in that book, and treating it as one of its chapters is a
common enough error to be worth stating.

## Why this page is short on theory

Four of the five principles are already structural rules elsewhere in this
corpus. SOLID is not a separate discipline to apply on top of the model; it is
the reasoning behind rules you are already following, and this page exists so a
reviewer can say *which* principle a finding rests on when the argument gets
abstract.

| Principle | In this standard it is | Enforced by |
|---|---|---|
| **S**ingle Responsibility | One package, one reason to change; one aggregate per package | [types and packages](./types-and-packages.md), [aggregates](../ddd/aggregates.md) |
| **O**pen–Closed | A new adapter is a new file, not an edit to `application` | [`structure.md`](../structure.md), [boundaries](./boundaries.md) |
| **L**iskov Substitution | Every adapter honours its port's contract, including its errors | [tests](./tests.md), [`ddd/errors.md`](../ddd/errors.md) |
| **I**nterface Segregation | Ports have one to three methods, sized by the caller | [types and packages](./types-and-packages.md) |
| **D**ependency Inversion | The dependency rule; ports point inward | [`structure.md`](../structure.md) |

Two of them change meaning in Go, and those two are where this page does real
work: **LSP**, because Go has no subtyping, and **OCP**, because Go has no
inheritance.

## S — Single Responsibility

Martin's own correction, in [The Single Responsibility
Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html),
is the part that matters and the part usually dropped:

> A module should be responsible to one, and only one, actor.

Not "do one thing" — that is the function rule, on
[functions](./functions.md). SRP is about **who asks for a change**. Two actors
who can each demand a change to the same file will eventually demand
contradictory ones, and whoever edits it second breaks the first.

```go
// Wrong. One type, three actors: the DBA owns the column names, the API team
// owns the JSON contract, and the business owns the placement rule. A rename in
// the database is now a breaking change to the public API.
type Order struct {
	ID     string `db:"order_id" json:"orderId"`
	Status string `db:"status"   json:"status"`
	Total  int64  `db:"total"    json:"total"`
}

func (o *Order) Place() error { ... }
```

```go
// Correct. Three types, three actors, three reasons to change, none of which
// can force a change on the others.
package order                            // business
type Order struct{ id OrderID; status Status; total Money }
func (o *Order) Place(now time.Time) error { ... }

package postgres                         // DBA
type orderRow struct{ ID string `db:"order_id"` ... }

package httpapi                          // API consumers
type orderResponse struct{ ID string `json:"orderId"` ... }
```

The mapping between them is the cost, and it is the price of the three
independent change histories. This is the same conclusion
[types and packages](./types-and-packages.md) reaches from Martin's ch. 6, and
the same one [`structure.md`](../structure.md) reaches from the dependency rule.
Three routes, one answer, which is usually a sign the answer is right.

**Applied to packages:** a package has one reason to change. A package named for
a layer — `models`, `services`, `handlers` — has as many reasons as it has
files, which is why [naming](./naming.md) bans them.

## O — Open–Closed

Open for extension, closed for modification: adding behaviour should mean adding
code, not editing code that already works.

In Java the mechanism is inheritance. Go has none, so the mechanism is
**interface satisfaction plus composition**, and it turns out to be the stronger
version because a new implementation cannot reach into the old one.

```go
// The port. Written once.
type PaymentGateway interface {
	Authorise(ctx context.Context, id order.OrderID, amount order.Money) (AuthCode, error)
}
```

Adding Adyen alongside Stripe:

- `adapters/outbound/adyen/gateway.go` — new file
- `composition/wire.go` — one line changes which one is constructed
- `application` — **untouched**
- `domain` — **untouched**

Nothing that worked yesterday was edited, so nothing that worked yesterday can
break. That is the whole principle, and in this standard it falls out of the
region layout rather than being pursued separately.

**The counter-rule, which matters more than the principle.** OCP is the most
over-applied idea in the set. A codebase that is open for every conceivable
extension is a codebase of interfaces with one implementation each, and
`/codebase-design` is right to call that a hypothetical seam.

So: **be closed against the change you have already seen twice, not against
every change you can imagine.** A port that exists for the dependency rule —
every port in this standard — is justified on that ground alone and needs no
second implementation to earn its place. A port that exists "in case we swap it"
needs one. See [`vocabulary.md`](../vocabulary.md), which settles this
collision.

## L — Liskov Substitution

Martin's statement is about subtypes: a program using a base type must work
unchanged with any derived type.

**Go has no subtyping.** A type does not extend another type; it either has the
method set or it does not. So LSP cannot be violated by a type hierarchy here —
and yet it is violated constantly, in a form specific to interfaces:

> **Every implementation of a port must honour the port's contract, including
> its errors, its nil behaviour and its guarantees — not merely its method
> signatures.**

The compiler checks the signatures. Nothing checks the contract, which is why
this is a review rule and a test rule rather than a compile-time one.

```go
// The contract, stated on the interface. This is what makes it checkable —
// see clean-code/comments.md rule 5.
type Repository interface {
	// ByID returns the order, or ErrOrderNotFound if it does not exist.
	ByID(ctx context.Context, id OrderID) (*Order, error)

	// Save persists the whole aggregate, returning ErrConcurrentModification
	// if it changed since it was read.
	Save(ctx context.Context, o *Order) error
}
```

```go
// Wrong. Satisfies the interface, violates the contract three ways: a
// different not-found signal, a nil return with a nil error, and no
// concurrency check at all. Every test that passes against this fake is
// meaningless, and production will differ.
func (m *Orders) ByID(_ context.Context, id order.OrderID) (*order.Order, error) {
	return m.byID[id], nil // nil, nil for a missing order
}

func (m *Orders) Save(_ context.Context, o *order.Order) error {
	m.byID[o.ID()] = o // last writer wins, silently
	return nil
}
```

```go
// Correct. The fake is substitutable because it honours the same contract,
// including the failure modes that matter to callers.
func (m *Orders) ByID(_ context.Context, id order.OrderID) (*order.Order, error) {
	found, ok := m.byID[id]
	if !ok {
		return nil, order.ErrOrderNotFound
	}
	return found, nil
}

func (m *Orders) Save(_ context.Context, o *order.Order) error {
	if cur, ok := m.byID[o.ID()]; ok && cur.Version() != o.Version() {
		return order.ErrConcurrentModification
	}
	m.byID[o.ID()] = o
	return nil
}
```

**This is the single most valuable reading of LSP in a Go DDD codebase**, because
an unsubstitutable fake is how a suite reaches high coverage and low confidence
at the same time. It is stated again, from the test side, on
[tests](./tests.md).

Two corollaries:

- **A port's error set is part of its signature.** Documented at the interface,
  identical across every adapter. A driver-specific error escaping is an LSP
  violation as well as a boundary violation.
- **An implementation may not strengthen a precondition.** A Postgres adapter
  that rejects an identifier the domain considers valid has narrowed the
  contract its callers were written against.

## I — Interface Segregation

Clients should not be forced to depend on methods they do not use. In Go this is
the strongest of the five, because the Go proverb states it in reverse and more
usefully:

> The bigger the interface, the weaker the abstraction.

```go
// Wrong. One "infrastructure" interface. Every fake implements nine methods to
// test a use case that calls one, and every use case depends on eight things
// it does not touch.
type Infra interface {
	ByID(context.Context, order.OrderID) (*order.Order, error)
	Save(context.Context, *order.Order) error
	Publish(context.Context, ...any) error
	Now() time.Time
	NewOrderID() order.OrderID
	SendEmail(context.Context, Address, Template) error
	Authorise(context.Context, order.Money) (AuthCode, error)
	Log(string, ...any)
	Metric(string, float64)
}
```

```go
// Correct. Each use case declares exactly what it needs, and each fake
// implements exactly that.
type PlaceOrder struct {
	orders    order.Repository // 4 methods, the aggregate's own collection
	publisher Publisher        // 1
	clock     Clock            // 1
}
```

The test for a port: **is there a caller that uses every method on it?** If not,
it is two ports that were merged for filing convenience.

`io.Reader` is the canonical example and is worth the comparison — one method,
implemented by files, sockets, buffers, archives, encrypted streams and test
fixtures. Its power is precisely that it asks for nothing else.

## D — Dependency Inversion

High-level policy must not depend on low-level detail; both depend on
abstractions. In this standard it is not a principle to apply — it is the layout
itself:

- `domain` declares `Repository`; `postgres` implements it.
- `application` declares `Publisher`, `Clock`, `PaymentGateway`; `adapters`
  implement them.
- `composition` is the only place that knows both sides.

The rule that operationalises it is on [`structure.md`](../structure.md): **the
interface belongs to the region that calls it, never to the region that
satisfies it.** An interface declared in `adapters` and consumed inward is DIP
inverted back to the wrong way round, and it is pass 2 of
[`archify:review-passes`](../../skills/review-passes/SKILL.md).

One clarification, because it causes arguments: **dependency inversion is not
dependency injection.** Injection is how the concrete thing arrives at runtime —
a constructor parameter, wired in `composition`. Inversion is the direction the
source-level import points. You can inject a concrete type and still have the
dependency pointing the wrong way; the import is what matters.

## What is not adopted

- **No DI container, no reflection-based wiring, no service locator.**
  `composition` constructs things with `New…` functions in a function you can
  read. A container turns a compile error into a runtime one.
- **No "SOLID" as a review vocabulary on its own.** A finding cites the specific
  rule — a page and a rule number — and may name the principle as the reasoning.
  "Violates SRP" alone is not a finding, because nobody can act on it.
- **Not every principle, everywhere.** Martin's own
  [Solid Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html)
  narrows the claim considerably twelve years on; the mechanical application of
  all five to every type is how a codebase acquires forty interfaces with one
  implementation each.

## Common mistakes

| Mistake | Principle | Consequence |
|---|---|---|
| One struct with `db:` and `json:` tags and business methods | S | Three actors own one file |
| A package named for a layer | S | As many reasons to change as it has files |
| Editing `application` to add an adapter | O | The thing that worked is now in the diff |
| An interface per type, speculatively | O | Forty hypothetical seams; see [`vocabulary.md`](../vocabulary.md) |
| A fake with different error behaviour | L | Green tests, broken production |
| Driver error escaping an adapter | L | The port's contract differs per implementation |
| One `Infra` interface | I | Every fake implements nine methods to test one |
| Interface declared beside its implementation | D | Dependency points outward |
| A DI container | D | Compile-time wiring becomes a runtime failure |
| "Violates SOLID" as a review finding | — | Unactionable; cite the page and rule |

## Checklist

- [ ] Each package has one actor who can demand a change to it
- [ ] Domain types, row types and wire types are distinct
- [ ] Adding an adapter touches only `adapters` and `composition`
- [ ] Every port's contract — errors included — is documented at the interface
- [ ] Every fake honours that contract, including failure modes
- [ ] No port has a method its caller does not use
- [ ] Every interface is declared by its consumer
- [ ] Wiring is explicit constructor calls in `composition`
- [ ] Findings cite a page and a rule, not a principle

## Sources

**Books.** Robert C. Martin, _Clean Architecture_, Part III — "Design
Principles", chapters 7–11, one per principle. Part V for the dependency rule
that DIP produces, which is cited by [`structure.md`](../structure.md) rather
than restated here. Ousterhout, _A Philosophy of Software Design_, ch. 4, for
the deep-module argument that ISP arrives at from the other direction.

**Online.** Every link below was reachable when this page was written.

- [The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html)
  — Martin's own correction: responsibility means an actor, not a task
- [Solid Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html)
  — Martin, 2020, on what he still claims for these principles
- [A Little Architecture](https://blog.cleancoder.com/uncle-bob/2016/01/04/ALittleArchitecture.html)
  — the clearest short statement of why dependency direction is the decision
  that outlives every other one
- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  — the dependency rule as originally published
- [Go Proverbs](https://go-proverbs.github.io/) — "The bigger the interface, the
  weaker the abstraction", which is ISP in nine words
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the
  interfaces section: declare interfaces where they are used
- [Effective Go: interfaces](https://go.dev/doc/effective_go#interfaces_and_types)
  — structural typing, and why Go has no subtype relationship to violate
