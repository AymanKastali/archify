# Entities

A concept the business tracks as *the same thing* over time, even as its
attributes change. An entity is defined by identity, not by its fields.

**Authority.** Evans, ch. 5. Vernon, ch. 5.

## Why it exists

An `Order` that has its address corrected is still that order. A `Shipment`
that moves from packed to dispatched is still that shipment. If the business
would say "the same one", it has identity, and identity is the thing the model
must carry — not the attributes, which are allowed to change.

The test, run against the business rather than against the code:

> If I take two of these with identical attributes, does the business consider
> them the same thing, or two things?

Same thing → [value object](./value-objects.md). Two things → entity.

## The rules

1. **Identity is assigned at creation and never changes.** No `SetID`.
2. **Identity is a typed value object**, not `string`, not `uuid.UUID`, not
   `int64`.
3. **Equality is identity equality**, never attribute equality.
4. **An entity is reachable only through its aggregate root.** An entity that is
   not a root has no repository and is never loaded or saved on its own. See
   [aggregates](./aggregates.md).
5. **State changes go through methods named for the act.** No setters.
6. **An entity holds the rules about its own state.** A struct with fields and
   no behaviour is not an entity; it is a record, and see
   [anti-patterns](./anti-patterns.md).

## Typed identifiers

This is a small rule with a large effect.

```go
// Wrong: every identifier in the system is interchangeable.
func Transfer(fromAccount, toAccount, initiatedBy string) error
Transfer(toAccount, fromAccount, userID)   // compiles, and is a production incident
```

```go
// Correct: the compiler rejects the transposition.
func Transfer(from AccountID, to AccountID, by UserID) error
```

```go
package order

// OrderID identifies an Order. It is a value object like any other: it cannot
// be empty, and it cannot be built from outside the package without passing
// through a constructor.
type OrderID struct {
	value string
}

func NewOrderID(s string) (OrderID, error) {
	if strings.TrimSpace(s) == "" {
		return OrderID{}, ErrOrderIDEmpty
	}
	return OrderID{value: s}, nil
}

func (id OrderID) String() string { return id.value }
func (id OrderID) IsZero() bool   { return id.value == "" }
```

`from` and `to` are both `AccountID`, so the compiler cannot catch *that*
transposition — no type system can. That is what named arguments at the call
site and a test are for. What it does catch is the far more common case of
passing an identifier of the wrong *kind*, which is most of them.

### Where identity comes from

Three options, and the choice is a real one:

| Source | When | Cost |
|---|---|---|
| The application, before persisting | Default. The aggregate is whole before it is stored, and events can carry its id | Needs a generator port |
| The database (sequence, identity column) | Rarely worth it | The aggregate is incomplete until saved; events cannot be produced in the constructor |
| The domain (a natural key) | When the business already has one — an invoice number, a booking reference | Natural keys change more often than anyone expects |

**Default to application-assigned.** UUIDv7 or equivalent, generated through a
port so tests are deterministic:

```go
// internal/contexts/ordering/internal/application/command/ids.go

// IDs generates identifiers. A port, because a test that cannot predict an id
// cannot assert on the event that carries it.
type IDs interface {
	NewOrderID() order.OrderID
}
```

Database-assigned identity is the one to avoid: it means the aggregate does not
know who it is until it has been stored, which means a domain event produced
during creation cannot name it, which means the event has to be produced after
the write — and now the write and the event are not atomic. A small decision
with a long tail.

## Equality

```go
// Correct: identity is the whole of equality.
func (o *Order) SameAs(other *Order) bool {
	return o != nil && other != nil && o.id == other.id
}
```

```go
// Wrong: attribute equality on an entity. Two different orders that happen to
// match are reported as one.
func (o *Order) Equals(other *Order) bool {
	return reflect.DeepEqual(o, other)
}
```

In Go, `==` on a struct containing slices does not compile, and on one without
them it silently compares attributes. Neither is what you want for an entity, so
give it a named method and use that.

## Entities inside an aggregate

Most entities are not aggregate roots. An `OrderLine` has identity — you can
change its quantity and it is still that line — but it has no independent
existence:

```go
package order

// LineID identifies a line within one order. It is unique within the order,
// not globally, because a line is never referred to from outside.
type LineID struct{ value string }

// Line is an entity: its quantity changes and it remains the same line.
// Unexported constructor, because a Line is only ever created by its Order.
type Line struct {
	id        LineID
	sku       SKU
	quantity  Quantity
	unitPrice Money
}

func newLine(id LineID, sku SKU, q Quantity, price Money) Line {
	return Line{id: id, sku: sku, quantity: q, unitPrice: price}
}

// Subtotal is the line's contribution to the order total.
func (l Line) Subtotal() Money { return l.unitPrice.Times(l.quantity) }

// changeQuantity is unexported: the Order decides whether a quantity may
// change, because the rule about it belongs to the Order, not the Line.
func (l *Line) changeQuantity(q Quantity) { l.quantity = q }
```

`newLine` and `changeQuantity` are unexported. That is the aggregate boundary
expressed in Go: outside this package, a `Line` can be read but never
constructed or changed, so the `Order` cannot be bypassed.

## Wrong, and why

```go
// Wrong: mutable identity.
func (o *Order) SetID(id string) { o.id = id }

// Wrong: primitive identity, interchangeable with every other id.
type Order struct {
	ID         string
	CustomerID string
}

// Wrong: an entity that is a bag of exported fields. Every rule about this
// order now lives in whatever service happens to touch it.
type Order struct {
	ID       string
	Status   string
	Total    float64
	PlacedAt *time.Time
}
order.Status = "placed"   // anybody, from anywhere, in any state

// Wrong: a non-root entity with its own repository. The aggregate is no longer
// the consistency boundary, because lines can be changed without the order
// looking.
type LineRepository interface {
	Save(ctx context.Context, l Line) error
}
```

## Common mistakes

| Mistake | Consequence |
|---|---|
| `string` identifiers | Transposed arguments compile |
| Database-assigned identity | Aggregate is incomplete before saving; events cannot be atomic with the write |
| Exported mutable fields | Any code, in any state, can break any invariant |
| Setters | The act is unnameable, so the rule about the act has no home |
| Repository for a non-root entity | The aggregate boundary is bypassed |
| Attribute equality | Two distinct entities compare equal |
| Entity with no behaviour | An anaemic model; see [anti-patterns](./anti-patterns.md) |

## Checklist

- [ ] Every identifier is a typed value object, not a primitive
- [ ] Identity is assigned at construction and has no setter
- [ ] Equality is identity equality, via a named method
- [ ] Non-root entities have unexported constructors and mutators
- [ ] No repository exists for a non-root entity
- [ ] Every state change is a method named for the act

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 5. Vernon, _Implementing
Domain-Driven Design_, ch. 5.

**Online.** Every link below was reachable when this page was written.

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
- [EvansClassification](https://martinfowler.com/bliki/EvansClassification.html)
  — Fowler on the entity/value split and why it is the first question to ask
    about a type
- [Identity Map](https://martinfowler.com/eaaCatalog/identityMap.html)
  — Fowler, PoEAA; the problem typed identifiers and a repository together avoid
