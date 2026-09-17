# Repositories

A collection-like interface over aggregates of one type, hiding the fact that
they are stored anywhere.

**Authority.** Evans, ch. 6. Vernon, ch. 12.

## Why it exists

The model should be able to say "the order with this id" without saying "select
from a table". Two reasons, and the second is the important one:

- The model stays testable and free of persistence vocabulary.
- **The aggregate stays the consistency boundary.** A repository that returns
  parts of aggregates, or rows, or joined shapes, is a hole in the boundary — it
  lets code work with fragments of an aggregate without the aggregate's rules
  being involved.

The illusion to maintain is that the aggregate collection is **in memory**. Add
one, ask for one by id, remove one. That is the whole interface.

## The rules

1. **One repository per aggregate root.** Never for a non-root entity, never
   one repository for several aggregates.
2. **The interface lives in `domain`.** Vernon and Evans both place it in the
   model; the implementation lives in `adapters/outbound`. See
   [`structure.md`](../structure.md).
3. **It deals in aggregates only.** Every method takes and returns the aggregate
   type or its identifier. A method returning a row, a projection, a partial
   object or a joined shape is not a repository method — it is a
   [read model](./read-models.md).
4. **Selection criteria are a closed set, not an open predicate.** A repository
   may answer "which of my aggregates match this?", but only through a criteria
   type the adapter can translate into a query. See
   [specifications](./specifications.md).
5. **Named like a collection, not like a database.** `Add`, `Save`, `ByID`,
   `Remove`. Not `Insert`, `SelectByID`, `Update`, `Delete`, `FindAll`.
6. **No leaking of the persistence technology.** No `*sql.Tx`, no `*gorm.DB`,
   no SQL strings, no driver errors escaping.
7. **Returns a typed domain error for "not found".** Not `nil, nil`, not
   `sql.ErrNoRows`.
8. **Saves the whole aggregate.** No partial updates of one field; the aggregate
   is the unit.

## In Go

### The interface, in the aggregate's package

```go
// internal/contexts/ordering/internal/domain/order/repository.go
package order

import "context"

// Repository is the collection of Orders. It reads like a collection because,
// as far as the model is concerned, that is what it is.
//
// context.Context appears here and nowhere else in `domain`: the interface is
// the seam where the model meets the outside, and cancellation belongs to the
// outside. Implementations need it; the aggregate never sees it.
type Repository interface {
	// ByID returns the order, or ErrOrderNotFound.
	ByID(ctx context.Context, id OrderID) (*Order, error)

	// Save persists the whole aggregate. It returns ErrConcurrentModification
	// if the order changed since it was read.
	Save(ctx context.Context, o *Order) error

	// Add stores a new order.
	Add(ctx context.Context, o *Order) error

	// Remove deletes it. Most domains never need this; do not add it by habit.
	Remove(ctx context.Context, id OrderID) error
}
```

```go
// internal/contexts/ordering/internal/domain/order/errors.go
var (
	ErrOrderNotFound          = errors.New("order not found")
	ErrConcurrentModification = errors.New("order was modified concurrently")
)
```

### The implementation, in adapters

```go
// internal/contexts/ordering/internal/adapters/outbound/postgres/order_repository.go
package postgres

// OrderRepository implements order.Repository over PostgreSQL. Every driver
// concern stops at this file: no sql types, no query strings and no pq errors
// leave it.
type OrderRepository struct {
	db DB // an interface satisfied by both *sql.DB and *sql.Tx
}

func (r *OrderRepository) ByID(ctx context.Context, id order.OrderID) (*order.Order, error) {
	row, err := r.queries(ctx).GetOrder(ctx, id.String())
	switch {
	case errors.Is(err, sql.ErrNoRows):
		return nil, fmt.Errorf("order %s: %w", id, order.ErrOrderNotFound)
	case err != nil:
		return nil, fmt.Errorf("loading order %s: %w", id, err)
	}

	lines, err := r.queries(ctx).ListOrderLines(ctx, id.String())
	if err != nil {
		return nil, fmt.Errorf("loading lines for order %s: %w", id, err)
	}

	// Rebuild through the aggregate's rehydration constructor. Every stored
	// value goes back through its value-object constructor: a row that has been
	// in the table for a year is untrusted input.
	return toAggregate(row, lines)
}

func (r *OrderRepository) Save(ctx context.Context, o *order.Order) error {
	affected, err := r.queries(ctx).UpdateOrder(ctx, toRow(o))
	if err != nil {
		return fmt.Errorf("saving order %s: %w", o.ID(), err)
	}
	if affected == 0 {
		// The version in the WHERE clause did not match.
		return fmt.Errorf("order %s: %w", o.ID(), order.ErrConcurrentModification)
	}
	return r.replaceLines(ctx, o)
}
```

### Rehydration

Loading an aggregate is not construction — the rules that applied when it was
created do not apply again, and the stored state may predate a rule that exists
now. Give the aggregate an explicit rehydration entry point rather than letting
the repository reach into its fields:

```go
// internal/contexts/ordering/internal/domain/order/rehydrate.go
package order

// Rehydrate rebuilds an Order from stored state. It is for repositories only.
// It does not apply the creation rules — the order already exists — but it does
// reject state that could not have been produced by this model, because that is
// corruption rather than history.
func Rehydrate(
	id OrderID, customer CustomerID, lines []Line,
	total Money, status Status, placedAt time.Time, version int,
) (*Order, error) {
	if id.IsZero() {
		return nil, ErrOrderIDRequired
	}
	if status == StatusPlaced && placedAt.IsZero() {
		return nil, fmt.Errorf("%w: placed order without a placement time", ErrCorruptState)
	}
	return &Order{
		id: id, customerID: customer, lines: lines,
		total: total, status: status, placedAt: placedAt, version: version,
	}, nil
}
```

### Wrong, and why

```go
// Wrong: returns a row. The aggregate is no longer the way to reach this data,
// so its rules can be bypassed by reading.
func (r *OrderRepository) ByID(ctx context.Context, id string) (OrderRow, error)

// Wrong: database vocabulary, and a leaked transaction handle.
type OrderRepository interface {
	SelectByID(tx *sql.Tx, id string) (*Order, error)
	InsertOrder(tx *sql.Tx, o *Order) error
}

// Wrong: a generic repository. The compiler is satisfied and the model is not —
// every aggregate now has the same five methods regardless of what it needs,
// and nowhere to express what it actually supports.
type Repository[T any] interface {
	Get(ctx context.Context, id string) (T, error)
	Save(ctx context.Context, e T) error
	List(ctx context.Context) ([]T, error)
}

// Wrong: query methods that return non-aggregates. This is a read model
// wearing a repository's name.
type OrderRepository interface {
	ByID(ctx context.Context, id OrderID) (*Order, error)
	TotalRevenueByMonth(ctx context.Context) ([]MonthlyTotal, error)             // read model
	CustomerOrderSummaries(ctx context.Context, c CustomerID) ([]Summary, error) // read model
}

// Wrong: partial update. The aggregate is the unit; this writes around it.
func (r *OrderRepository) UpdateStatus(ctx context.Context, id OrderID, s Status) error

// Wrong: nil, nil for not found. Every caller must remember to check, and one
// of them will not.
func (r *OrderRepository) ByID(...) (*Order, error) {
	if noRows {
		return nil, nil
	}
}
```

### On generic repositories

`Repository[T]` is tempting in Go now that generics exist. It is still wrong,
for a reason that is not about types: **a repository's method set is part of the
model.** If `Order` can be looked up by customer and `Invoice` cannot, that is a
statement about the domain, and a generic interface erases it. Uniform CRUD over
every aggregate is the shape of a data-access layer, which is the thing a
repository is not.

## Transactions

A repository does not own the transaction — the
[application service](./application-services.md) does. The repository
participates in whatever transaction is in scope:

```go
// The DB interface is satisfied by both *sql.DB and *sql.Tx, and the
// transaction in scope is carried in the context by the Unit of Work. The
// repository neither opens nor commits anything.
func (r *OrderRepository) queries(ctx context.Context) *sqlc.Queries {
	if tx, ok := txFromContext(ctx); ok {
		return sqlc.New(tx)
	}
	return sqlc.New(r.db)
}
```

## Common mistakes

| Mistake | Consequence |
|---|---|
| Returns rows or projections | Aggregate rules bypassed on read paths |
| Query methods on the repository | Repository becomes a data-access layer |
| Generic `Repository[T]` | Erases what each aggregate actually supports |
| Repository for a non-root entity | Aggregate boundary bypassed |
| `*sql.Tx` in the interface | Persistence technology in `domain` |
| `nil, nil` for not found | Nil dereference in the caller who forgot |
| Partial-field updates | Writes that the aggregate never saw |
| Repository opens its own transaction | Two aggregates cannot be coordinated, and nesting breaks |

## Checklist

- [ ] One interface per aggregate root, in the aggregate's package
- [ ] Every method takes or returns the aggregate or its id
- [ ] Collection vocabulary: `Add`, `Save`, `ByID`, `Remove`
- [ ] Typed domain errors for not-found and concurrent modification
- [ ] No `*sql.Tx`, no SQL, no driver errors crossing the interface
- [ ] Implementation in `adapters/outbound`; rehydration goes through the aggregate
- [ ] Selection, if any, goes through a closed criteria type the adapter translates
- [ ] Queries that are not aggregates live as read models instead

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 6. Vernon, _Implementing
Domain-Driven Design_, ch. 12.

**Online.** Every link below was reachable when this page was written.

- [Repository](https://martinfowler.com/eaaCatalog/repository.html)
  — Fowler, PoEAA; the collection illusion in its original statement
- [Data Mapper](https://martinfowler.com/eaaCatalog/dataMapper.html)
  — Fowler, PoEAA; what the adapter implementation actually is
- [Unit of Work](https://martinfowler.com/eaaCatalog/unitOfWork.html)
  — Fowler, PoEAA; the pattern the transaction boundary on this page relies on
- [Domain Model](https://martinfowler.com/eaaCatalog/domainModel.html)
  — Fowler, PoEAA
