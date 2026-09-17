# Aggregates

A cluster of objects treated as one unit for the purpose of data changes, with
one entity as its root. The aggregate is the **consistency boundary**: the rule
it exists to protect is true before every transaction and true after it, with no
instant in between where it is false.

**Authority.** Evans, ch. 6. Vernon, ch. 10, and his "Effective Aggregate
Design" essays, which revise Evans and are what binds here.

## Why it exists

An aggregate answers one question: **what must be true at the same instant?**

Everything else about aggregates follows from that. It is not a way to group
related data, not a mapping of a database table, and not an object graph. It is
the answer to "which facts are allowed to disagree with each other, and which
are not."

If you cannot state the rule in a sentence, you do not have an aggregate. You
have a cluster of objects, and it will grow until it is the whole model.

Examples of a real invariant:

- "An order's total equals the sum of its lines." Lines and total must change
  together, so they are one aggregate.
- "A draft order becomes placed exactly once." The status transition is atomic
  with whatever else the placing changes.
- "A shipment's parcels weigh no more than the carrier permits." Parcels and the
  limit are one aggregate.

Examples of something that looks like an invariant but is not:

- "An order belongs to a customer that exists." That is a cross-aggregate
  reference, enforced elsewhere and eventually — not an invariant.
- "A product's price is current." Price is another aggregate's business; the
  order captured the price at the moment it was placed.

## Vernon's four rules

These are rules here, not guidance.

### 1. Model true invariants in consistency boundaries

Only put things in an aggregate that must be transactionally consistent. If two
pieces of state may legally disagree for a second, they belong to two
aggregates. Most state may legally disagree for a second; people badly
underestimate how much.

### 2. Design small aggregates

A root plus the value objects it needs, plus the minimum entities. The
temptation is always to pull in the neighbours "because we'll need them", and
the cost arrives later as contention, lost updates, and loading a graph to
change one field.

The heuristic: **most aggregates are a root and some value objects.** An
aggregate with three levels of nested entities is a design that has not found
its boundary yet.

### 3. Reference other aggregates by identity

Never hold another aggregate's root. Hold its identifier.

This is the rule Vernon spends the most effort on, because holding the object
looks so much more convenient. What it actually buys you is: a loading problem
(how deep?), a consistency problem (is that copy current?), and a transaction
problem (you can now modify two aggregates in one transaction, which is rule 4's
violation waiting to happen).

### 4. Use eventual consistency outside the boundary

Anything outside the aggregate is updated in another transaction, driven by a
domain event. "But they must be consistent" is almost always "somebody would be
mildly annoyed if they were inconsistent for 200 milliseconds", and it is worth
asking the business which one it is.

### And the rule that follows: one aggregate per transaction

A use case that modifies two aggregates in one transaction has drawn at least
one boundary wrong. This is a finding, not a trade-off — and it has an exception
worth naming: a genuinely spanning rule (a uniqueness constraint across
aggregates, say) is a deliberate departure, recorded as an ADR, with the
concurrency control it needs made explicit.

## In Go: an aggregate is a package

The class is the encapsulation boundary in Java. In Go it is the **package** —
a struct's unexported fields are visible to everything in the same package, and
nothing outside it. So:

> **One aggregate, one package.** The root, its entities, its value objects and
> its errors live together, and nothing else lives there.

```text
internal/contexts/ordering/internal/domain/order/
    order.go       the root: state, invariant, acts
    line.go        the Line entity
    money.go       Money, Currency
    sku.go         SKU, Quantity
    status.go      the closed status set
    events.go      OrderPlaced, OrderCancelled
    errors.go      the typed domain errors
```

### The root

```go
// Package order is the Order aggregate. The invariant it exists to protect:
// an order's total always equals the sum of its lines, and an order becomes
// placed exactly once.
package order

import "time"

type Order struct {
	id         OrderID
	customerID CustomerID // another aggregate, by identity only (rule 3)
	lines      []Line
	total      Money
	status     Status
	placedAt   time.Time

	events []Event // produced here, published elsewhere
}

// New starts a draft order for a customer. It returns an error rather than a
// half-built order, so an Order in an invalid state does not exist.
func New(id OrderID, customer CustomerID, currency Currency) (*Order, error) {
	if id.IsZero() {
		return nil, ErrOrderIDRequired
	}
	if customer.IsZero() {
		return nil, ErrCustomerRequired
	}
	zero, err := NewMoney(0, currency)
	if err != nil {
		return nil, err
	}
	return &Order{
		id:         id,
		customerID: customer,
		status:     StatusDraft,
		total:      zero,
	}, nil
}
```

### An act, and the invariant it holds

```go
// AddLine adds a quantity of a SKU at the price agreed now. Adding a SKU the
// order already has increases that line rather than creating a second one,
// because the business considers those the same line.
//
// The total is recalculated here rather than on read, because the invariant is
// that the stored total equals the sum of the lines — a total computed on
// demand would make the invariant unobservable and therefore unbreakable in a
// way that hides errors rather than preventing them.
func (o *Order) AddLine(id LineID, sku SKU, qty Quantity, unitPrice Money) error {
	if o.status != StatusDraft {
		return ErrOrderNotDraft
	}
	if unitPrice.Currency() != o.total.Currency() {
		return ErrCurrencyMismatch
	}

	if existing := o.lineBySKU(sku); existing != nil {
		existing.changeQuantity(existing.quantity.Plus(qty))
	} else {
		o.lines = append(o.lines, newLine(id, sku, qty, unitPrice))
	}

	return o.recalculateTotal()
}

func (o *Order) recalculateTotal() error {
	sum, err := NewMoney(0, o.total.Currency())
	if err != nil {
		return err
	}
	for _, l := range o.lines {
		sum, err = sum.Add(l.Subtotal())
		if err != nil {
			return err
		}
	}
	o.total = sum
	return nil
}
```

### A transition, producing a fact

```go
// Place makes the order binding. It is the single place the draft-to-placed
// transition can happen, which is why the rule about it has somewhere to live.
func (o *Order) Place(now time.Time) error {
	if o.status != StatusDraft {
		return ErrAlreadyPlaced
	}
	if len(o.lines) == 0 {
		return ErrNoLines
	}
	if o.total.IsZero() {
		return ErrZeroTotal
	}

	o.status = StatusPlaced
	o.placedAt = now
	o.record(OrderPlaced{
		OrderID:    o.id,
		CustomerID: o.customerID,
		Total:      o.total,
		PlacedAt:   now,
	})
	return nil
}

// record appends a fact. The aggregate produces events; it does not publish
// them — publishing is infrastructure, and an aggregate that knows how to
// publish has imported the outside world.
func (o *Order) record(e Event) { o.events = append(o.events, e) }

// ReleaseEvents hands over what happened and clears the buffer, so the same
// fact is not published twice.
func (o *Order) ReleaseEvents() []Event {
	released := o.events
	o.events = nil
	return released
}
```

### Reading state

```go
// Accessors return copies or value objects. There is no accessor that hands out
// something the caller could mutate.
func (o *Order) ID() OrderID    { return o.id }
func (o *Order) Status() Status { return o.status }
func (o *Order) Total() Money   { return o.total }

// Lines returns a copy of the slice. Returning o.lines would hand the caller a
// window into the aggregate's interior, and Go slices share their backing array.
func (o *Order) Lines() []Line {
	out := make([]Line, len(o.lines))
	copy(out, o.lines)
	return out
}
```

That `Lines` copy is not pedantry. `return o.lines` lets a caller write
`order.Lines()[0].changeQuantity(...)` — or simply hold the slice while the
aggregate mutates underneath them. In Go, encapsulation of a slice field
requires the copy.

## Wrong, and why

```go
// Wrong (rule 3): holds another aggregate, not its identity.
type Order struct {
	customer *customer.Customer // now: how deep do we load? is it current?
	products []*catalog.Product // and both can be modified in this transaction
}
```

```go
// Wrong (rule 2): an aggregate that has become the model.
type Order struct {
	customer     Customer
	shipments    []Shipment
	invoices     []Invoice
	payments     []Payment
	supportCases []SupportCase
}

// Loading an order to change its address now loads the customer's entire
// history, and two users touching unrelated parts of it collide.
```

```go
// Wrong (rule 4): two aggregates in one transaction.
func (s *Service) PlaceOrder(ctx context.Context, id order.OrderID) error {
	return s.tx.Run(ctx, func(ctx context.Context) error {
		o, _ := s.orders.ByID(ctx, id)
		o.Place(s.clock.Now())
		s.orders.Save(ctx, o)

		c, _ := s.customers.ByID(ctx, o.CustomerID())
		c.RecordOrderPlaced() // a second aggregate, same transaction
		return s.customers.Save(ctx, c)
	})
}

// Correct: save the order, publish OrderPlaced, and let the customer aggregate
// react in its own transaction.
```

```go
// Wrong: exported fields. The invariant is a suggestion.
type Order struct {
	Status Status
	Total  Money
	Lines  []Line
}
o.Status = StatusPlaced      // from anywhere, in any state, with no lines
o.Lines = append(o.Lines, l) // total is now wrong and nothing noticed
```

```go
// Wrong: the aggregate publishing its own events.
func (o *Order) Place(now time.Time, bus EventBus) error {
	o.status = StatusPlaced
	return bus.Publish(OrderPlaced{...})   // domain now depends on infrastructure,
}                                          // and publishes before the write commits
```

```go
// Wrong: a "validate" method called by the caller. The invariant is only held
// if somebody remembers to ask.
func (o *Order) Validate() error { ... }
o.Status = StatusPlaced
if err := o.Validate(); err != nil { ... }   // too late; it is already wrong
```

## Concurrency

An aggregate is the unit of concurrency control as well as consistency. Two
transactions modifying the same aggregate must not both win.

```go
type Order struct {
	version int // incremented on every state change
}
```

The repository writes with `WHERE id = $1 AND version = $2` and treats zero
rows affected as a concurrency conflict, surfaced as a typed error the
application service can retry. Optimistic locking is the default because
aggregates are small and collisions are rare; if collisions are common, the
aggregate is too big — that is rule 2 telling you something.

## Finding the boundary

1. Write down the rule that must never be false, in one sentence, in the
   business's words.
2. The aggregate is the smallest set of state that sentence mentions.
3. Everything else the use case touches is another aggregate, reached by
   identity and updated by an event.
4. If step 1 produced several sentences, you have several aggregates.
5. If step 1 produced no sentence, you have a [read model](./read-models.md), not
   an aggregate.

## Common mistakes

| Mistake | Symptom | Rule broken |
|---|---|---|
| Aggregate mirrors a table | Named for storage, no stated invariant | 1 |
| Aggregate mirrors the object graph | Nested entities three levels deep | 2 |
| Holding other aggregates | `*Customer` field; lazy-loading questions | 3 |
| Two aggregates per transaction | `tx.Run` with two repositories | 4 |
| Exported fields | `o.Status = ...` at a call site | — |
| Publishing from the aggregate | `domain` imports a bus | — |
| `Validate()` called by callers | Invariant held on request | — |
| Returning internal slices | `return o.lines` | — |

## Checklist

- [ ] The invariant is stated in one sentence in the package comment
- [ ] The aggregate is one Go package, and nothing else lives in it
- [ ] All fields unexported; no setters; every act is a named method
- [ ] Other aggregates appear only as typed identifiers
- [ ] One aggregate is modified per transaction
- [ ] Events are recorded on the aggregate and released, never published by it
- [ ] Accessors return copies, not internal slices or maps
- [ ] A version field exists and the repository uses it

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 6 — "The Life Cycle of a Domain
Object". Vernon, _Implementing Domain-Driven Design_, ch. 10, which supersedes
Evans on sizing.

**Online.** Every link below was reachable when this page was written.

- [Effective Aggregate Design](https://www.dddcommunity.org/library/vernon_2011/)
  — Vernon's three-part essay, the source of the four rules on this page; read
    this before ch. 10 if you read only one thing
- [DDD_Aggregate](https://martinfowler.com/bliki/DDD_Aggregate.html)
  — Fowler's one-page definition
- [Aggregate Design Canvas](https://github.com/ddd-crew/aggregate-design-canvas)
  — DDD Crew, a structured way to argue about a boundary before coding it
- [Pattern: Aggregate](https://microservices.io/patterns/data/aggregate.html)
  — Richardson, on aggregates as the unit of consistency across services
