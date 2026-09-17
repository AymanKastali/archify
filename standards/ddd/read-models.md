# Read models

A shape built for a reader. Not an aggregate, never loaded through a repository,
and holding no rules.

**Authority.** Vernon, ch. 4 and ch. 14 (CQRS). Evans has no name for this; it
is the gap his repositories get bent to fill.

## Why it exists

Aggregates are designed for **writing** — small, guarding one invariant,
reachable only through their root. Almost every screen wants something else: a
list, a total across many aggregates, a joined shape, a summary.

Serving those from aggregates does real damage:

- The aggregate grows fields it does not need for its invariant, violating rule
  2 of [aggregates](./aggregates.md).
- The repository grows query methods and becomes a data-access layer, violating
  [repositories](./repositories.md) rule 3.
- Listing a hundred aggregates loads a hundred object graphs to render a table.

The resolution is to stop pretending one model serves both. **Write through
aggregates. Read through read models.** This is CQRS at its smallest and
cheapest — two models, not two databases, not event sourcing, not a message bus.

## The rules

1. **A read model is a plain struct of values**, built for one reader.
2. **It has no behaviour and no invariant.** It is data; that is the one place
   in this standard where that is the correct answer.
3. **It is never a specification.** A rule that feeds a decision may be a
   [specification](./specifications.md); a shape that feeds a screen is this.
4. **It is never loaded through a repository** and never turns back into an
   aggregate.
5. **It is read-only.** Nothing writes through it, ever.
6. **The query interface is declared by the use case that needs it**, in
   `application/query`, in the same file as the query that calls it, and
   implemented in `adapters/outbound`.
   → [application services](./application-services.md)
7. **It may join across aggregates within its own context.** It may not read
   another context's tables — see [bounded contexts](./bounded-contexts.md).
8. **It may be denormalised and may be stale**, and if it can be stale, the type
   should say so.

## In Go

### Declared by its consumer

```go
// internal/contexts/ordering/internal/application/query/list_customer_orders.go
package query

// OrderSummary is what the orders list screen shows. It is shaped for that
// screen and for nothing else; another screen gets another type.
type OrderSummary struct {
	OrderID      string
	CustomerName string
	LineCount    int
	TotalMinor   int64
	Currency     string
	Status       string
	PlacedAt     time.Time
}

// OrderSummaries reads the summary list. It is declared here because this is
// what needs it, and implemented in adapters/outbound with one SQL statement.
type OrderSummaries interface {
	ForCustomer(ctx context.Context, customerID string, page Page) ([]OrderSummary, error)
}
```

### Implemented as one query

```go
// internal/contexts/ordering/internal/adapters/outbound/postgres/order_summaries.go
package postgres

// ForCustomer answers the list screen in one statement. No aggregates are
// constructed, because none are needed to render a table.
func (q *OrderSummaries) ForCustomer(
	ctx context.Context, customerID string, page query.Page,
) ([]query.OrderSummary, error) {
	rows, err := q.queries.ListOrderSummaries(ctx, sqlc.ListOrderSummariesParams{
		CustomerID: customerID,
		Limit:      int32(page.Limit),
		Offset:     int32(page.Offset),
	})
	if err != nil {
		return nil, fmt.Errorf("listing summaries for customer %s: %w", customerID, err)
	}

	out := make([]query.OrderSummary, 0, len(rows))
	for _, r := range rows {
		out = append(out, query.OrderSummary{
			OrderID:      r.ID,
			CustomerName: r.CustomerName,
			LineCount:    int(r.LineCount),
			TotalMinor:   r.TotalMinor,
			Currency:     r.Currency,
			Status:       r.Status,
			PlacedAt:     r.PlacedAt,
		})
	}
	return out, nil
}
```

Note that the read model carries **primitives**, not value objects. It is not
going to be reasoned about; it is going to be rendered. Converting to `Money`
and back to a string on the way out is ceremony with no invariant behind it.

### A query use case

```go
// Same file, immediately below them: a query use case has no transaction, no
// repository, and no aggregate.
type ListCustomerOrders struct {
	summaries OrderSummaries
}

func (q *ListCustomerOrders) Handle(
	ctx context.Context, qry ListCustomerOrdersQuery,
) ([]OrderSummary, error) {
	return q.summaries.ForCustomer(ctx, qry.CustomerID, qry.Page)
}
```

## Wrong, and why

```go
// Wrong: query methods on the repository. The repository is now a data-access
// layer and the aggregate is no longer the only way in.
type OrderRepository interface {
	ByID(ctx context.Context, id OrderID) (*Order, error)
	ListSummaries(ctx context.Context, c CustomerID) ([]Summary, error)
}

// Wrong: loading aggregates to render a list. A hundred object graphs for a
// hundred table rows, and N+1 queries for the lines nobody is going to show.
func (q *ListOrders) Handle(ctx context.Context, c CustomerID) ([]View, error) {
	ids, _ := q.repo.IDsForCustomer(ctx, c)
	views := make([]View, 0, len(ids))
	for _, id := range ids {
		o, _ := q.repo.ByID(ctx, id) // N queries, each loading lines
		views = append(views, toView(o))
	}
	return views, nil
}

// Wrong: the aggregate grew a field for a screen. CustomerName is not part of
// the invariant, it belongs to another aggregate, and now it can go stale
// inside a consistency boundary that claims to guarantee it.
type Order struct {
	customerID   CustomerID
	customerName string // for the list screen
}

// Wrong: writing through a read model.
func (q *OrderSummaries) UpdateStatus(ctx context.Context, id string, s string) error

// Wrong: reading another context's tables to build a read model.
//   SELECT o.*, c.name FROM ordering.orders o
//     JOIN crm.customers c ON c.id = o.customer_id
// The boundary is gone at runtime even though the import graph looks clean.
```

That last case is the one that needs a positive answer rather than just a
prohibition. When a read model genuinely needs another context's data, the
options are: **(a)** the consuming context keeps its own copy, fed by the other
context's events — a denormalised projection it owns; **(b)** the caller
composes two queries above both contexts; **(c)** accept that this view belongs
to a third context whose job is reporting. Not a join.

## Staleness

A read model fed by events is eventually consistent, and hiding that produces
bug reports rather than trust:

```go
// The type says what it is. A caller can decide what to do about it, and a
// reviewer can see the decision was made.
type OrderSummary struct {
	OrderID string
	Status  string
	AsOf    time.Time // when the projection last saw an event for this order
}
```

A read model queried directly from the same database as the aggregates is not
stale, and does not need this. One fed by a projection is, and does.

## When a read model is *not* the answer

- **The reader needs to make a decision that changes state.** Load the
  aggregate; decisions are made against the write model, always.
- **The rule it would encode is a domain rule.** A read model has no rules. If
  you are computing "is this order overdue" for a screen, ask whether the
  business means something by "overdue", and if so it belongs on the aggregate
  or a domain service.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Query methods on repositories | Repository becomes a DAO; aggregate bypassed |
| Aggregates loaded for lists | N+1 queries; graphs loaded to render text |
| Aggregate grows display fields | Invariant covers data it cannot guarantee |
| Read model with behaviour | Rules duplicated between read and write models |
| Cross-context joins | Boundary deleted at runtime |
| Value objects in read models | Ceremony with no invariant |
| Undeclared staleness | Bug reports about "wrong" data that is merely late |

## Checklist

- [ ] No repository method returns a non-aggregate
- [ ] Read models are plain structs of primitives, declared by their consumer
- [ ] Query use cases take no transaction and load no aggregates
- [ ] No aggregate carries a field that exists only for a screen
- [ ] No query joins across context boundaries
- [ ] Anything that can be stale says so in its type

## Sources

**Books.** Vernon, _Implementing Domain-Driven Design_, ch. 4 and ch. 14. Not in
Evans, _Domain-Driven Design_ — CQRS postdates the 2003 book.

**Online.** Every link below was reachable when this page was written.

- [CQRS](https://martinfowler.com/bliki/CQRS.html)
  — Fowler, including his warning that it is the wrong default for most systems
- [CQRS pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
  — Microsoft Azure Architecture Center, with the consistency trade-offs spelled
    out
- [Pattern: CQRS](https://microservices.io/patterns/data/cqrs.html)
  — Richardson
