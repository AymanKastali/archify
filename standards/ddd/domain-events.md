# Domain events

A fact that has already happened, expressed in the ubiquitous language, named in
the past tense. `OrderPlaced`, not `PlaceOrder`, not `OrderPlaceEvent`, not
`OrderStatusChangedToPlaced`.

**Authority.** Vernon, ch. 8. Evans's 2003 book has no Domain Event pattern —
he added it later, in the 2015 _Domain-Driven Design Reference_. Vernon is the
primary text here, and the outbox rule below comes from neither book.

## Why it exists

Two reasons, and they are different.

**Inside a context**, events let one aggregate react to another without either
one knowing about the other — the mechanism that makes "one aggregate per
transaction" livable.

**Across contexts**, events are the only thing that crosses the boundary, which
is what makes the boundary real. See
[context mapping](./context-mapping.md).

A third, quieter reason: an event names something the business cares about that
otherwise has no name. "The status field went from 2 to 3" is not a business
concept. "The order was placed" is, and once it has a name it can be reasoned
about, subscribed to, audited and tested.

## The rules

1. **Past tense, in the glossary's words.** The event is a fact; facts have
   already happened and cannot be rejected.
2. **Immutable.** All fields set at construction; no methods that change
   anything.
3. **Produced by the aggregate, published by infrastructure.** The aggregate
   records; the application service releases; an adapter publishes.
4. **Carries identifiers and facts, never live objects.** No aggregate
   references, no pointers into the model.
5. **Carries what happened, not what to do.** `OrderPlaced`, not
   `SendConfirmationEmail`. If a consumer needs to do something, that is the
   consumer's decision.
6. **A domain event is not a message.** The published, cross-context form is a
   separate type in `published/` — see below.
7. **Published atomically with the state change it describes.** Otherwise you
   have an event describing something that did not happen, or a change nobody
   was told about. This is what the transactional outbox is for.

## In Go

### Defining events

```go
// internal/contexts/ordering/internal/domain/order/events.go
package order

import "time"

// Event is a fact produced by this aggregate. The interface is deliberately
// tiny: it exists so the aggregate can hold a slice of them, not so callers can
// treat events polymorphically.
type Event interface {
	isOrderEvent()
	OccurredAt() time.Time
}

// OrderPlaced is the fact that a draft order became binding.
type OrderPlaced struct {
	OrderID    OrderID
	CustomerID CustomerID
	Total      Money
	PlacedAt   time.Time
}

func (OrderPlaced) isOrderEvent()           {}
func (e OrderPlaced) OccurredAt() time.Time { return e.PlacedAt }

// OrderCancelled is the fact that a placed order will not be fulfilled.
type OrderCancelled struct {
	OrderID     OrderID
	Reason      CancellationReason
	CancelledAt time.Time
}

func (OrderCancelled) isOrderEvent()           {}
func (e OrderCancelled) OccurredAt() time.Time { return e.CancelledAt }
```

The unexported `isOrderEvent()` marker is how Go states "this is a closed set of
events belonging to this aggregate" — no other package can implement `Event`.

Fields are exported here, unlike in an aggregate, because an event is a fact
being handed to somebody. It is immutable by having no mutating methods, and
because every field is a value object or a scalar.

### Producing and releasing

```go
// In the aggregate: record the fact as part of the transition.
func (o *Order) Place(now time.Time) error {
	if o.status != StatusDraft {
		return ErrAlreadyPlaced
	}
	o.status = StatusPlaced
	o.placedAt = now
	o.record(OrderPlaced{OrderID: o.id, CustomerID: o.customerID, Total: o.total, PlacedAt: now})
	return nil
}
```

```go
// In the application service: release and hand on, inside the transaction that
// persisted the change.
func (s *PlaceOrder) Handle(ctx context.Context, cmd PlaceOrderCommand) error {
	return s.tx.Run(ctx, func(ctx context.Context) error {
		o, err := s.orders.ByID(ctx, cmd.OrderID)
		if err != nil {
			return err
		}
		if err := o.Place(s.clock.Now()); err != nil {
			return err
		}
		if err := s.orders.Save(ctx, o); err != nil {
			return err
		}
		// Same transaction as the Save above. See "Atomicity" below.
		return s.events.Record(ctx, o.ReleaseEvents())
	})
}
```

### Atomicity: the outbox

The write and the event must land together or not at all.

```go
// Wrong: publishes after the transaction. If the process dies between the two
// lines, the order is placed and nobody will ever be told.
if err := s.tx.Run(ctx, saveOrder); err != nil {
	return err
}
return s.bus.Publish(ctx, events)
```

```go
// Wrong: publishes inside the transaction, to a broker. The broker is not
// transactional with the database — if the transaction then rolls back, an
// event describing something that never happened is already in flight.
return s.tx.Run(ctx, func(ctx context.Context) error {
	s.orders.Save(ctx, o)
	return s.bus.Publish(ctx, events)
})
```

```go
// Correct: the event is written to a table in the same transaction as the
// aggregate, and a separate process relays it to the broker afterwards.
return s.tx.Run(ctx, func(ctx context.Context) error {
	if err := s.orders.Save(ctx, o); err != nil {
		return err
	}
	return s.outbox.Record(ctx, o.ReleaseEvents()) // same *sql.Tx
})
```

The relay is a separate process, it never shares a transaction with the writer,
and delivery is at-least-once — so every consumer must be idempotent. The full
obligations belong on the transactional outbox pattern page rather than here.

### Domain event vs published event

These are two different types and conflating them is the most common error on
this page.

```go
// Domain event: internal, uses this context's value objects, free to change.
package order

type OrderPlaced struct {
	OrderID    OrderID
	CustomerID CustomerID
	Total      Money
	PlacedAt   time.Time
}
```

```go
// Published event: the contract with other contexts. Primitives, explicit
// serialisation, versioned, and changing it is a breaking change.
package published

type OrderPlacedV1 struct {
	Type       string    `json:"type"` // "ordering.order.placed.v1"
	OrderID    string    `json:"order_id"`
	CustomerID string    `json:"customer_id"`
	TotalMinor int64     `json:"total_minor"`
	Currency   string    `json:"currency"`
	PlacedAt   time.Time `json:"placed_at"`
}
```

```go
// The translation lives in adapters/outbound, not in the domain.
func toPublished(e order.OrderPlaced) published.OrderPlacedV1 {
	return published.OrderPlacedV1{
		Type:       "ordering.order.placed.v1",
		OrderID:    e.OrderID.String(),
		CustomerID: e.CustomerID.String(),
		TotalMinor: e.Total.MinorUnits(),
		Currency:   e.Total.Currency().Code(),
		PlacedAt:   e.PlacedAt,
	}
}
```

Without this split, renaming a private field breaks three other contexts and a
JSON tag lives in your domain package.

Not every domain event is published. Most are internal. Publishing is a
deliberate decision to add to the contract.

## Wrong, and why

```go
// Wrong: imperative. This is a command dressed as an event — the producer is
// telling the consumer what to do, so the coupling it was supposed to remove
// is still there, now with indirection.
type SendOrderConfirmation struct{ ... }

// Wrong: present tense. Reads as a request that might be refused.
type PlaceOrder struct{ ... }

// Wrong: named for the mechanism, not the fact.
type OrderStatusChanged struct {
	From Status
	To   Status
}
// A consumer must now switch on From/To to work out what actually happened,
// which is the business meaning the event failed to carry.

// Wrong: carries the aggregate.
type OrderPlaced struct {
	Order *Order   // mutable, unserialisable, and couples every consumer to the model
}

// Wrong: mutable event.
func (e *OrderPlaced) SetTotal(m Money) { e.Total = m }

// Wrong: events as an audit log of field changes.
type FieldChanged struct {
	Entity, Field, Old, New string
}
// This is a changelog. It carries no business meaning, so nothing can subscribe
// to anything meaningful.
```

## Naming

| Good | Bad | Why |
|---|---|---|
| `OrderPlaced` | `OrderCreated` | "Created" is technical; the business places orders |
| `OrderCancelled` | `OrderStatusChanged` | Names the fact, not the field |
| `ShipmentDispatched` | `ShipmentUpdated` | "Updated" carries no meaning |
| `PaymentFailed` | `HandlePaymentFailure` | An event is a fact, not a handler |
| `CustomerMovedHouse` | `AddressUpdated` | The business event, not its data effect |

`Created` deserves a note. It is occasionally right — a `CustomerRegistered` is
genuinely a creation — but it is usually a sign that nobody asked what the
business calls the act. Ask; there is nearly always a better word.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Publishing from the aggregate | `domain` depends on infrastructure; publishes before commit |
| Publishing outside the transaction | Lost events, or events for changes that rolled back |
| One type for domain and published event | Internal renames break consumers; JSON tags in `domain` |
| `Changed`/`Updated` names | Consumers reverse-engineer meaning from field diffs |
| Event carries an aggregate | Consumers couple to the producer's model |
| Command named as an event | The coupling remains, with added indirection |
| Consumers assume exactly-once | Duplicates on redelivery, because it is at-least-once |

## Checklist

- [ ] Past tense, in the glossary's words
- [ ] Immutable; no mutating methods
- [ ] Recorded by the aggregate, released by the application service, published by an adapter
- [ ] Carries identifiers and value objects, never aggregates
- [ ] Written in the same transaction as the state change it describes
- [ ] Published form is a separate versioned type in `published/`
- [ ] Every consumer is idempotent

## Sources

**Books.** Vernon, _Implementing Domain-Driven Design_, ch. 8. Not in Evans,
_Domain-Driven Design_ (2003) — Evans added the pattern in the 2015
_Domain-Driven Design Reference_.

**Online.** Every link below was reachable when this page was written.

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf)), where the
    Domain Event definition Evans wrote later appears
- [Domain Event](https://martinfowler.com/eaaDev/DomainEvent.html) and [Event Narrative](https://martinfowler.com/eaaDev/EventNarrative.html)
  — Fowler, on events as records of the past
- [What do you mean by "Event-Driven"?](https://martinfowler.com/articles/201701-event-driven.html)
  — Fowler, on the four distinct things people call event-driven; worth reading
    before choosing one
- [Pattern: Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)
  — Richardson; the atomicity rule on this page in its canonical form
- [Pattern: Domain event](https://microservices.io/patterns/data/domain-event.html)
  — Richardson
