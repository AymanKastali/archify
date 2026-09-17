# Domain services

A domain operation that belongs to no single aggregate, expressed as a
stateless object in the model.

**Authority.** Evans, ch. 5. Vernon, ch. 7.

## Why it exists

Some behaviour is genuinely domain logic but has no natural home on one
aggregate:

- It needs two or more aggregates to decide something.
- It is a calculation belonging to the domain but owned by no entity.
- It is a policy the business names but does not attach to a thing.

Forcing such behaviour onto an aggregate is worse than a service: it makes that
aggregate reach for state it does not own, which is how rule 3 of
[aggregates](./aggregates.md) gets broken.

**But this is the most abused pattern in DDD**, because "domain service" is
where behaviour goes when nobody wanted to find its real home. A codebase with
many domain services and thin aggregates is an
[anaemic model](./anti-patterns.md) wearing DDD vocabulary.

## The test, before you write one

Ask in order, and stop at the first yes:

1. **Is this about one aggregate's own state?** → It is a method on that
   aggregate. Not a service.
2. **Is it about the values, not the entity?** → It is a method on a
   [value object](./value-objects.md).
3. **Is it orchestration — loading, saving, transaction boundaries, calling
   external systems?** → It is an
   [application service](./application-services.md), which lives outside
   `domain` and is a different thing entirely despite the similar name.
4. **Does it express a domain rule that spans aggregates or belongs to none?**
   → A domain service. Write it.

Most candidates stop at 1 or 3.

## The rules

1. **Stateless.** No fields except other domain collaborators. Never a
   repository, never a clock, never a client.
2. **Named for the operation in the ubiquitous language** — a verb or a named
   policy: `PricingPolicy`, `TransferFunds`, `AllocateStock`. Never
   `OrderService`, `OrderManager`, `OrderHelper`.
3. **Lives in `domain`** and obeys `domain`'s import rule: standard library and
   its own context only.
4. **Takes aggregates and value objects as arguments and returns values or
   events.** It does not load, does not save, does not publish.
5. **No `context.Context`.** That is cancellation and request scope —
   infrastructure.

## In Go

### A spanning rule

```go
// internal/contexts/ordering/internal/domain/pricing/policy.go

// Package pricing holds the rule for what a customer pays, which depends on the
// order and on the customer's agreement — two aggregates, so the rule belongs
// to neither.
package pricing

// Policy prices an order under a customer's agreement. It is stateless: the
// same inputs always produce the same output, which is what makes it testable
// without any infrastructure at all.
type Policy struct{}

// Quote returns what the customer pays for this order under this agreement.
// Both aggregates arrive as arguments — the policy does not fetch them, because
// fetching is not a domain concern.
func (Policy) Quote(o *order.Order, a agreement.Agreement) (order.Money, error) {
	subtotal := o.Total()

	discount, err := a.DiscountFor(subtotal)
	if err != nil {
		return order.Money{}, err
	}

	return subtotal.Subtract(discount)
}
```

### A named policy, stated as domain vocabulary

```go
// OverdraftPolicy decides whether an account may go below zero. The business
// names this policy, argues about it, and changes it — so it is a domain
// concept with a name, not an if-statement inside a use case.
type OverdraftPolicy struct {
	limit Money
}

func NewOverdraftPolicy(limit Money) (OverdraftPolicy, error) {
	if limit.IsNegative() {
		return OverdraftPolicy{}, ErrNegativeLimit
	}
	return OverdraftPolicy{limit: limit}, nil
}

func (p OverdraftPolicy) Permits(balance, withdrawal Money) bool {
	after, err := balance.Subtract(withdrawal)
	if err != nil {
		return false
	}
	return after.GreaterThanOrEqual(p.limit.Negated())
}
```

### Wrong, and why

```go
// Wrong: a repository in a domain service. This is an application service that
// has been put in the wrong region, and it drags persistence into `domain`.
type OrderService struct {
	repo  OrderRepository
	clock Clock
}

func (s *OrderService) PlaceOrder(ctx context.Context, id OrderID) error {
	o, err := s.repo.ByID(ctx, id)
	...
}
```

```go
// Wrong: behaviour that is the aggregate's own, moved out of it. The Order can
// answer this from its own state, so this service exists only to keep the
// aggregate anaemic.
type OrderTotalCalculator struct{}

func (OrderTotalCalculator) Calculate(o *Order) Money {
	var sum Money
	for _, l := range o.Lines() {
		sum, _ = sum.Add(l.Subtotal())
	}
	return sum
}
```

```go
// Wrong: named for a layer, not for an operation. A type named "Service" tells
// you nothing about what it does, so everything ends up inside it.
type OrderService struct{}

func (s *OrderService) Validate(...)  {}
func (s *OrderService) Calculate(...) {}
func (s *OrderService) Process(...)   {}
```

```go
// Wrong: stateful. A domain service with mutable state is an entity that has
// not admitted it.
type AllocationService struct {
	allocated map[SKU]Quantity // where does this live? who owns it?
}
```

## Domain service vs application service

They share a word and share nothing else.

| | Domain service | Application service |
|---|---|---|
| Region | `domain` | `application` |
| Holds | Domain rules | Orchestration |
| May load/save | No | Yes |
| Knows about transactions | No | Yes, owns them |
| `context.Context` | No | Yes |
| Named for | A domain operation or policy | A use case |
| Example | `PricingPolicy` | `PlaceOrder` |

If you find yourself writing "service" without being able to say which of these
two it is, that is the signal to stop and use the four-question test above.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Service holds a repository | Persistence in `domain`; dependency rule broken |
| Service does what an aggregate could | Anaemic aggregate; rules scattered |
| Named `XService` / `XManager` | No stated responsibility, so it accretes |
| Stateful service | Hidden entity, untestable, unsafe under concurrency |
| `context.Context` in the signature | Infrastructure in the model |
| One service per aggregate, by habit | Every aggregate ends up anaemic by convention |

## Checklist

- [ ] The four-question test was run and produced answer 4
- [ ] Stateless; no repository, clock, client or mutable field
- [ ] Named for the operation or policy in the glossary, never `XService`
- [ ] Aggregates and values arrive as arguments
- [ ] No `context.Context`, no I/O, no logging
- [ ] It could not have been a method on an aggregate or value object

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 5, where Service is introduced
alongside Entity and Value Object. Vernon, _Implementing Domain-Driven Design_,
ch. 7.

**Online.** Every link below was reachable when this page was written.

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
- [AnemicDomainModel](https://martinfowler.com/bliki/AnemicDomainModel.html)
  — Fowler; over-reaching domain services are how a model becomes anaemic
- [TransactionScript](https://martinfowler.com/eaaCatalog/transactionScript.html)
  — Fowler, PoEAA; the pattern a misused domain service collapses into
