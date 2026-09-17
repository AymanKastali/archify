# Context mapping

How contexts relate, and what is allowed to cross the boundary between them.

**Authority.** Evans, ch. 14–17. Vernon, ch. 3.

## Why it exists

Drawing the boundary is half the work; the other half is deciding what passes
through it and who absorbs the cost when one side changes. Left undecided, the
answer becomes "whatever was convenient in the moment", and the boundary erodes
one import at a time.

A context map names, for each pair of contexts, **which direction the dependency
runs and who bears the cost of change.**

## The relationship patterns

| Pattern | Meaning | Use when |
|---|---|---|
| **Partnership** | Two contexts succeed or fail together; teams coordinate releases | Rare, and expensive. Prefer to merge or separate |
| **Shared kernel** | A small shared model, changed only by agreement | Only for types with no domain meaning |
| **Customer–Supplier** | Downstream's needs influence upstream's plans | Both sides are yours, and the upstream will negotiate |
| **Conformist** | Downstream accepts upstream's model as-is | Upstream is external and won't negotiate, and its model is tolerable |
| **Anticorruption Layer (ACL)** | Downstream translates upstream's model into its own | The default for everything not the above |
| **Open Host Service** | Upstream publishes a defined protocol for all comers | Many downstreams |
| **Published Language** | A shared interchange format, owned by neither model | Pairs with Open Host Service |
| **Separate Ways** | No integration at all | Integration costs more than duplication |

**The default here is Anticorruption Layer over Published Language.** Every
other choice needs an argument.

This page says **what** crosses and **who** absorbs the change. The mechanics of
getting it across when both contexts are in the same binary — the outbox that
still applies, the in-process bus, idempotency, and the narrow synchronous
read — are
[`modular-monolith/communication.md`](../modular-monolith/communication.md).

## The rules

1. **Reference by identity only.** A context holds another context's identifier
   and nothing else. Never its aggregate, entity, or value objects.
2. **Contexts communicate by domain events** carrying a published language.
   Synchronous cross-context calls are a departure and need an ADR.
3. **The consuming side translates.** An anti-corruption layer belongs to the
   downstream context. The upstream does not shape its events for a consumer.
4. **The published language is not the domain model.** It is a separate,
   deliberately stable set of types in `published/`. Renaming a domain field
   must not change a published event.
5. **Eventual consistency across contexts is assumed.** A rule that requires two
   contexts to be consistent at one instant is a sign the boundary is wrong.

## In Go

### The published language

```go
// internal/contexts/ordering/published/events.go
//
// Published language. These types are ordering's contract with every other
// context. They are versioned, they are not the domain model, and a change
// here is a breaking change even when the compiler is silent.
package published

// OrderPlaced is the fact that an order became binding.
type OrderPlaced struct {
	OrderID    string    `json:"order_id"`
	CustomerID string    `json:"customer_id"`
	PlacedAt   time.Time `json:"placed_at"`
	Lines      []Line    `json:"lines"`
}

type Line struct {
	SKU      string `json:"sku"`
	Quantity int    `json:"quantity"`
}
```

Note what is absent: no prices, no internal status, no `Order` type. The
published language carries the facts other contexts have a legitimate need for,
and no more. Prices are ordering's business; if billing needs them, that is a
deliberate addition to the contract, argued once.

### The anti-corruption layer

The ACL lives in the **consuming** context, in `adapters/inbound`, and its job
is to turn the other context's words into this context's words.

```go
// internal/contexts/shipping/internal/adapters/inbound/ordering/translate.go
//
// The anti-corruption layer for ordering. Nothing below this file knows that
// ordering exists, what it calls things, or that Kafka carried the message.
package ordering

import (
	orderingpub "myapp/internal/contexts/ordering/published"
	"myapp/internal/contexts/shipping/internal/application/command"
)

// ToShipmentRequest translates ordering's OrderPlaced into shipping's own
// vocabulary. Ordering says "Line"; shipping says "Parcel Item". Ordering says
// "CustomerID"; shipping does not care who the customer is, only where it goes.
func ToShipmentRequest(e orderingpub.OrderPlaced) (command.PrepareShipment, error) {
	items := make([]command.Item, 0, len(e.Lines))
	for _, l := range e.Lines {
		sku, err := shipment.NewSKU(l.SKU)
		if err != nil {
			return command.PrepareShipment{}, fmt.Errorf("translating order %s: %w", e.OrderID, err)
		}
		qty, err := shipment.NewQuantity(l.Quantity)
		if err != nil {
			return command.PrepareShipment{}, fmt.Errorf("translating order %s: %w", e.OrderID, err)
		}
		items = append(items, command.Item{SKU: sku, Quantity: qty})
	}

	return command.PrepareShipment{
		OrderRef: shipment.OrderRef(e.OrderID),
		Items:    items,
	}, nil
}
```

Two things are happening here and both matter:

- **Translation.** Ordering's words become shipping's words at exactly one file.
  When ordering renames something, one file changes.
- **Validation at the boundary.** The upstream's strings become this context's
  value objects, and a malformed message is rejected here rather than being
  carried inward as a `string` that everything downstream must re-check.

### Wrong, and why

```go
// Wrong: importing the upstream's domain. Does not compile under the nested
// internal/ layout, which is why that layout exists.
import "myapp/internal/contexts/ordering/internal/domain/order"

func Handle(o order.Order) { ... }
```

```go
// Wrong: no translation. The upstream's shape has leaked all the way in, and
// shipping's use case now speaks ordering's language.
func Handle(e orderingpub.OrderPlaced) error {
	return app.PrepareShipment(e) // application now depends on ordering's contract
}
```

```go
// Wrong: the upstream shaping its event for one consumer.
type OrderPlaced struct {
	OrderID           string
	ShippingLabelHint string // shipping asked for this
	BillingTaxCode    string // billing asked for this
}
```

The third is how a published language decays into a union of everyone's needs.
When shipping needs something ordering does not have, the answer is that
shipping derives it, not that ordering carries it.

### Reference by identity

```go
// Correct: shipping holds ordering's identifier as its own typed reference.
package shipment

// OrderRef is an order in the ordering context. Shipping knows the identifier
// and deliberately nothing else.
type OrderRef string

type Shipment struct {
	orderRef OrderRef
}
```

```go
// Wrong: shipping holds ordering's aggregate.
type Shipment struct {
	order order.Order // now shipping's invariants depend on ordering's model
}
```

## Choosing a pattern

```text
Is the other side external and unchangeable?
├── Yes → is its model tolerable as-is?
│         ├── Yes → Conformist (rare; document the decision)
│         └── No  → Anticorruption Layer
└── No  → do both sides change together, always?
          ├── Yes → the boundary is probably wrong. Merge them, or find the
          │         seam that lets them change apart
          └── No  → Published Language + Anticorruption Layer (the default)
```

## Common mistakes

| Mistake | Consequence |
|---|---|
| Publishing the domain type as the event | Every internal rename is a breaking change to every consumer |
| Translating in the upstream | Upstream accumulates consumer-specific fields until it models nothing |
| No ACL — consuming the upstream contract directly in `application` | The boundary exists in the import graph but not in the model |
| Synchronous call where an event would do | Two contexts now share an availability budget |
| Sharing an enum across contexts | The one type every context must agree on, forever |
| Cross-context transaction | Guarantees that cannot be kept, discovered under load |

## Checklist

- [ ] Every cross-context reference is an identifier, typed in the consuming context
- [ ] Events are published-language types in `published/`, not domain types
- [ ] Every consumed event passes through an ACL in the consumer's `adapters/inbound`
- [ ] The ACL converts primitives to this context's value objects and rejects bad input there
- [ ] No published event carries a field that exists only for one consumer
- [ ] Synchronous cross-context calls have an ADR

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 14–17 — the whole of Part IV.
Vernon, _Implementing Domain-Driven Design_, ch. 3, and ch. 13 for the
integration mechanics.

**Online.** Every link below was reachable when this page was written.

- [Strategic Domain Driven Design with Context Mapping](https://www.infoq.com/articles/ddd-contextmapping/)
  — Brandolini, the article that made the relationship patterns legible
- [Context Mapping](https://github.com/ddd-crew/context-mapping)
  — DDD Crew, the patterns with notation and worked examples
- [DDD Starter Modelling Process](https://github.com/ddd-crew/ddd-starter-modelling-process)
  — where mapping sits in the order of work
- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
