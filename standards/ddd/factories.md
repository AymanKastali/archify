# Factories

A factory encapsulates the creation of an aggregate or value object when
construction is itself complex enough to be a domain concept.

**Authority.** Evans, ch. 6. Vernon, ch. 11.

## Why it exists

Creating an aggregate must produce a **whole, valid** aggregate. When that
requires several steps, several collaborators, or a rule that does not belong to
the thing being built, putting it in a constructor hides it and putting it in a
use case scatters it.

The bar is higher than most codebases apply. **Most aggregates do not need a
factory**, and a `New` function in the aggregate's package is the factory.

## When it is warranted

All of:

1. Construction involves a rule the business would name.
2. Construction needs collaborators the aggregate should not know about.
3. There is more than one way to come into existence, and they are different
   acts in the language.

If only (1) applies, it is a `New` function. If only (2) applies, pass the
collaborator's result in as an argument.

## The rules

1. **A factory returns a whole aggregate or nothing** — `(T, error)`, never a
   partially built object.
2. **It lives in `domain`**, with the aggregate it creates.
3. **It does not persist.** Creating and storing are different acts; storing
   belongs to the application service.
4. **It does not load.** If it needs another aggregate, that aggregate is passed
   in.
5. **Named for the act in the language:** `ReorderFrom`, `SplitOut`,
   `NewFromQuote` — not `OrderFactory.Create`.

## In Go

### Usually, the constructor is enough

```go
package order

// New starts a draft order. This is the factory. It needs no type, no
// interface, and no file of its own.
func New(id OrderID, customer CustomerID, currency Currency) (*Order, error) {
	...
}
```

### When a factory earns its existence

```go
package order

// Reorder creates a new draft order from a previously placed one, at today's
// prices. "Reorder" is the business's word for this act, and the rule — which
// lines carry over and which are dropped because the SKU is no longer sold —
// is a domain rule that belongs to neither the old order nor the new one.
//
// The catalogue arrives as an argument. The factory does not fetch it, because
// fetching is not a domain concern.
func Reorder(id OrderID, previous *Order, catalogue Catalogue) (*Order, []SKU, error) {
	fresh, err := New(id, previous.customerID, previous.total.Currency())
	if err != nil {
		return nil, nil, err
	}

	var unavailable []SKU
	for _, line := range previous.lines {
		price, ok := catalogue.PriceOf(line.sku)
		if !ok {
			unavailable = append(unavailable, line.sku)
			continue
		}
		if err := fresh.AddLine(NewLineID(), line.sku, line.quantity, price); err != nil {
			return nil, nil, err
		}
	}

	if len(fresh.lines) == 0 {
		return nil, unavailable, ErrNothingToReorder
	}
	return fresh, unavailable, nil
}
```

`Catalogue` here is a small domain interface — a read of another aggregate,
resolved by the application service and handed in. The factory stays pure.

### Reconstitution is not creation

Rebuilding a stored aggregate is a different act from creating a new one, and it
must not run the creation rules. See
[repositories](./repositories.md) — the entry point is `Rehydrate`, it is
documented as being for repositories, and it validates for *corruption* rather
than for *business legality*.

Keeping these separate matters because a rule added today would otherwise make
yesterday's stored data unloadable.

## Wrong, and why

```go
// Wrong: a factory type with one method, for a construction that has no rules.
// This is a Java habit; in Go it is a function.
type OrderFactory struct{}
func (OrderFactory) Create(id, customerID string) *Order { ... }

// Wrong: persists. Creating and storing are different acts, and now nothing can
// create an order without a database.
func (f *OrderFactory) Create(ctx context.Context, ...) (*Order, error) {
	o := &Order{...}
	return o, f.repo.Add(ctx, o)
}

// Wrong: loads. Persistence has entered `domain`.
func (f *OrderFactory) Reorder(ctx context.Context, previousID OrderID) (*Order, error) {
	previous, err := f.repo.ByID(ctx, previousID)
	...
}

// Wrong: returns a partially built aggregate for the caller to finish. The
// invariant is now the caller's problem, which means it is nobody's.
func NewOrder() *Order { return &Order{} }
o := NewOrder()
o.SetCustomer(c)
o.SetCurrency(cur)
```

The last one is the builder pattern applied to an aggregate, and it is the most
common form of this mistake. A builder is acceptable for a test fixture and for
a value object with many optional parts; it is not acceptable for an aggregate,
because the whole point of the aggregate is that an invalid one never exists.

## Common mistakes

| Mistake | Consequence |
|---|---|
| A factory type where a function would do | Ceremony without encapsulation |
| Factory persists or loads | `domain` depends on infrastructure |
| Builder for an aggregate | Invalid intermediate states exist |
| Reconstitution runs creation rules | Old stored data becomes unloadable |
| Factory in `application` | The creation rule lives outside the model |

## Checklist

- [ ] The three-part bar was met; otherwise it is a `New` function
- [ ] Returns a whole aggregate or an error
- [ ] Does not load, save, or take `context.Context`
- [ ] Collaborators arrive as arguments
- [ ] Reconstitution is a separate entry point with its own rules
- [ ] Named for the act in the glossary

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 6. Vernon, _Implementing
Domain-Driven Design_, ch. 11, which is unusually explicit that most aggregates
need no factory type.

**Online.** Every link below was reachable when this page was written.

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
- [Google Go Best Practices](https://google.github.io/styleguide/go/best-practices)
  — on constructor functions, and on returning errors rather than partially
    built values
- [Effective Go](https://go.dev/doc/effective_go)
  — the `New` convention this page depends on
