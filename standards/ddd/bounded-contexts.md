# Bounded contexts

A boundary inside which one model applies and one language is spoken. Outside
it, the same words mean different things and the model does not travel.

**Authority.** Evans, ch. 14. Vernon, ch. 2.

## Why it exists

A single model of "Order" that serves ordering, shipping, billing and support
becomes a type with forty fields, most of them irrelevant to any given caller
and many of them nullable because they only apply in one phase. Every change to
it risks four teams. This is the failure that the rest of DDD exists to prevent,
and every tactical pattern below it is worthless if this boundary is wrong.

The insight is that **the same word means different things to different parts of
the business, and that is not a problem to be resolved.** It is a boundary to be
drawn.

- In `ordering`, an Order is a set of lines with agreed prices, and the
  interesting question is whether it may be placed.
- In `shipping`, an Order is a destination and a list of things with weights and
  dimensions. Prices are irrelevant.
- In `billing`, an Order is an amount owed by a party. Dimensions are
  irrelevant.

Three models, three types, three packages, no sharing.

## The rules

1. **One model per context, one glossary per context.** `CONTEXT.md` lives with
   the context.
2. **No context imports another context's domain types.** Not the aggregate,
   not its entities, not its value objects. See
   [context mapping](./context-mapping.md) for what crosses instead.
3. **A context owns its own persistence.** No shared tables, no foreign keys
   across contexts, no joins across contexts. A context that reads another's
   tables has no boundary, whatever the directory structure says.
4. **A context is named for the part of the business it serves,** not for a
   layer or a technology: `ordering`, `shipping`, `billing` — not `core`,
   `common`, `services`, `api`.
5. **There is no `shared` or `common` context.** See below.

## Where to draw the boundary

Draw it where the **language changes**. Concretely, you have crossed a boundary
when any of these is true:

- The same noun means something materially different on each side.
- The invariants differ — a rule that must hold on one side is meaningless on
  the other.
- The lifecycles differ — one side's object is finished while the other's is
  just beginning.
- Different people are the authority on what is correct.

You have **not** crossed a boundary merely because:

- The code is getting large. Size is a module problem, not a context problem.
- The data lives in a different table.
- It would be convenient to deploy separately. That is a deployment decision;
  see below.

## Context ≠ deployable

A bounded context is a **model boundary**, not a process boundary. Several
contexts in one binary is a normal, correct arrangement, and it is the default
this standard scaffolds — the **modular monolith**, which has a corpus of its
own: [`modular-monolith.md`](../modular-monolith.md).

That corpus answers the question this page deliberately does not: once you have
decided two things are two contexts, **how they are packaged, surfaced, wired,
kept apart in the database, and eventually extracted**. This page decides
_whether_; that one decides _how_.

The advantage of one deployable is that the boundary is enforced by the
compiler rather than by discipline. The advantage of separate deployables is
independent scaling and deployment. Take the second only when you want the
second; taking it for the boundary is paying a distributed-systems price for
something a compiler does for free.

## In Go

A context is a directory with a compiler-enforced boundary:

```text
internal/contexts/ordering/ordering.go               the only public surface: wiring
internal/contexts/ordering/published/                what other contexts may see
internal/contexts/ordering/internal/domain/order/    the Order aggregate
internal/contexts/ordering/internal/application/command/
internal/contexts/ordering/internal/application/query/
internal/contexts/ordering/internal/adapters/
```

The full tree is
[`modular-monolith/layout.md`](../modular-monolith/layout.md).

Go permits a package under `a/internal/b` to be imported only from within `a`.
So this **does not compile**:

```go
// in internal/contexts/shipping/internal/application/command/create_shipment.go
import "myapp/internal/contexts/ordering/internal/domain/order" // compile error
```

That is the point. The boundary fails the build rather than failing review.

### The same noun, three times, correctly

```go
// internal/contexts/ordering/internal/domain/order/order.go
package order

type Order struct {
	id         OrderID
	customerID CustomerID // another context's aggregate, by identity only
	lines      []Line
	status     Status
}
```

```go
// internal/contexts/shipping/internal/domain/shipment/shipment.go
package shipment

// Shipment is shipping's view. It has no prices, because shipping has no
// opinion about money, and it has an address, because ordering has no opinion
// about geography.
type Shipment struct {
	id          ShipmentID
	orderRef    OrderRef // an identifier from ordering, not ordering's type
	destination Address
	parcels     []Parcel
	status      Status
}
```

```go
// internal/contexts/billing/internal/domain/invoice/invoice.go
package invoice

type Invoice struct {
	id       InvoiceID
	orderRef OrderRef
	payer    PartyID
	total    Money
	status   Status
}
```

Three `Status` types, three meanings, no relationship between them. A single
shared `OrderStatus` enum covering draft, packed, shipped, invoiced and paid
would be the whole failure in one declaration.

### Wrong, and why

```go
// Wrong: a context named for a layer.
internal/contexts/services/
internal/contexts/core/

// Wrong: a dumping ground that becomes a fourth, accidental model.
internal/contexts/shared/domain/order.go

// Wrong: shipping reaching into ordering's storage.
func (r *ShipmentRepo) ByOrder(ctx context.Context, id string) (...) {
	// SELECT ... FROM ordering.orders JOIN shipping.shipments ...
}
```

The last one is the most common and the hardest to see in review, because
nothing in the import graph reveals it — it is the whole subject of
[`modular-monolith/data.md`](../modular-monolith/data.md). A context that joins
to another context's tables has deleted its boundary at runtime while appearing
to have one at compile time. **Each context owns a schema, and nothing else reads it.**

## On `shared` and `common`

There is no shared context. There is a narrow exception, and it is narrow on
purpose: **types with no domain meaning** may be shared — `Money` as arithmetic,
identifier generation, clock abstractions, time helpers.

The test: if the type would need to change because a business rule changed, it
is not shareable. `Money` as "an amount and a currency with correct arithmetic"
is shareable. `Money` as "the amount owed, which excludes tax before invoicing"
is billing's and nobody else's.

Adding to the shared kernel requires an ADR, because in every codebase that has
one, it grows until it is the model.

## Common mistakes

| Mistake | Why it happens | Consequence |
|---|---|---|
| One `Order` type for all contexts | It looks like duplication to have three | Forty fields, most nullable, every change is cross-team |
| A `shared` domain package | Two contexts needed the same thing once | Becomes a fourth model nobody owns |
| Contexts split by layer (`api`, `services`, `data`) | Layers are visible, language is not | No boundary at all; just a directory rename |
| Cross-context foreign keys | The database made it easy | Boundary exists only in the code, not at runtime |
| Splitting because a package got big | Size is the visible symptom | Two contexts speaking one language, coupled forever |

## Checklist

- [ ] Each context has its own `CONTEXT.md`
- [ ] No context imports another context's domain packages
- [ ] Each context owns its own schema; no cross-context joins or foreign keys
- [ ] Contexts are named for the business, not for layers or technology
- [ ] Nothing in a shared package would change because a business rule changed
- [ ] Where the same noun appears in two contexts, it is two types

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 14 — "Maintaining Model
Integrity". Vernon, _Implementing Domain-Driven Design_, ch. 2.

**Online.** Every link below was reachable when this page was written.

- [BoundedContext](https://martinfowler.com/bliki/BoundedContext.html)
  — Fowler's short statement of the idea, including the point that a context is
    a boundary of *meaning*
- [DomainDrivenDesign](https://martinfowler.com/bliki/DomainDrivenDesign.html)
  — Fowler's overview, useful for where bounded contexts sit in the whole
- [Bounded Context Canvas](https://github.com/ddd-crew/bounded-context-canvas)
  — DDD Crew, a workshop tool for deciding where one context ends
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages)
  — the `go` command's rule that makes a context boundary a compile error
