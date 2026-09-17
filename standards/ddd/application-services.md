# Application services

The thin layer that turns a request into one act on one aggregate. Also called
a use case. It lives in `application`, not in `domain`, and it is not a
[domain service](./domain-services.md).

**Authority.** Vernon, ch. 14. Evans, ch. 4 (as the application layer).

## Why it exists

Something must load the aggregate, call the method, persist the result, hand on
the events, and own the transaction. That is real work and it is not domain
logic, so it needs a home that is not the model and not the HTTP handler.

The discipline that makes it worth having: **it holds no business rules.** Its
job is to be boring. When it stops being boring, a rule has escaped the model,
and that is the single most common way a domain model hollows out into a bag of
data.

## The shape

Every application service is the same six steps, and if yours is not, that is
worth noticing:

1. Translate the command's primitives into value objects.
2. Begin a transaction.
3. Load the aggregate.
4. Call **one** method on it.
5. Save it, and record its events in the same transaction.
6. Commit, and return.

## Where they live

`application/` is not a package. It is two:

```text
internal/contexts/ordering/internal/application/
├── command/                  the write side
│   ├── place_order.go            the use case, its command, the ports only it needs
│   ├── place_order_test.go
│   ├── cancel_order.go
│   ├── unit_of_work.go           a port every use case needs: its own file
│   ├── outbox.go
│   ├── clock.go
│   └── ids.go
└── query/                    the read side
    ├── list_customer_orders.go   the query, its view, and the port that answers it
    └── order_detail.go
```

The flat `application/` package with a `ports.go` and a `queries.go` in it is
the default, and it is wrong twice over.

`ports.go` and `queries.go` are named for a **kind of thing** rather than for a
thing, which [`../clean-code/formatting.md`](../clean-code/formatting.md)
forbids for exactly the reason on display here: a kind-named file is where
something goes when nobody decided where it goes, so it accumulates without
limit and nobody ever reads it top to bottom.

The deeper problem is that the two halves of this layer have **disjoint
dependencies**. A command needs the repository, the transaction and the outbox.
A query needs none of the three and must not acquire them — it answers a screen
by bypassing the aggregate, on purpose, and a query that can reach the write
model eventually writes through it. Flat, that is a rule review has to notice
every time. Split, it is an import: `query` naming anything in `domain` fails
lint.
→ [`../modular-monolith/enforcement.md`](../modular-monolith/enforcement.md)

**Why not one package per use case.** That is the next subdivision down and it
buys nothing. Use cases within a context share ports, so every shared port would
need a package of its own to live in — which is the `ports.go` problem again,
one directory up. The split earns its keep at the line where the dependency set
changes, and in this layer that line occurs once.

## The rules

1. **One service per use case**, named for the use case: `PlaceOrder`,
   `CancelOrder`. Not `OrderService` with eleven methods.
2. **No business rules.** No conditional that reads aggregate state and decides
   something. If you need one, it belongs on the aggregate or in a
   [domain service](./domain-services.md).
3. **One aggregate modified per transaction.** See
   [aggregates](./aggregates.md).
4. **Owns the transaction boundary.** Repositories do not; adapters do not.
5. **Takes a command of primitives and converts them to value objects itself**,
   so the inbound adapter never constructs domain types.
6. **Returns nothing, or an identifier, or a read model.** Never an aggregate —
   handing an aggregate to an adapter lets it read state that the model intends
   to expose only through behaviour.
7. **Declares the ports it needs in its own package**: one caller, and it goes
   in that use case's file; every caller, and it goes in a file named for the
   port, as `clock.go` declares `Clock`. Never a `ports.go`, and never an
   `application/port/` package. Repository interfaces are the exception and live
   in `domain`, per [`structure.md`](../structure.md).
8. **`command/` and `query/`, and nothing else under `application/`.** No Go
   file directly in `application/`, no `application/shared/`,
   `application/dto/`, `application/common/`. A third package there is a design
   decision and needs an ADR.
9. **A port both sides need is declared twice.** A three-line interface
   duplicated across `command` and `query` costs less than a package they both
   have to import, and the two copies are then free to diverge — which is the
   whole point of a consumer-side port.
10. **Nothing groups the use cases.** No `Application` struct, no `Commands` and
    `Queries` holder. The context facade is the aggregation point, and there is
    exactly one of those.
    → [`../modular-monolith/modules.md`](../modular-monolith/modules.md)

## In Go

### A use case

```go
// internal/contexts/ordering/internal/application/command/place_order.go
package command

// PlaceOrderCommand is what the outside world asks for, in primitives. The
// adapter that built it did not need to know a single domain type.
type PlaceOrderCommand struct {
	OrderID string
}

// PlaceOrder makes a draft order binding.
type PlaceOrder struct {
	orders order.Repository
	outbox Outbox
	tx     UnitOfWork
	clock  Clock
}

func NewPlaceOrder(orders order.Repository, outbox Outbox, tx UnitOfWork, clock Clock) *PlaceOrder {
	return &PlaceOrder{orders: orders, outbox: outbox, tx: tx, clock: clock}
}

func (uc *PlaceOrder) Handle(ctx context.Context, cmd PlaceOrderCommand) error {
	id, err := order.NewOrderID(cmd.OrderID)
	if err != nil {
		return err
	}

	return uc.tx.Run(ctx, func(ctx context.Context) error {
		o, err := uc.orders.ByID(ctx, id)
		if err != nil {
			return err
		}

		// The one act. Every rule about whether it is allowed lives in here.
		if err := o.Place(uc.clock.Now()); err != nil {
			return err
		}

		if err := uc.orders.Save(ctx, o); err != nil {
			return err
		}

		// Same transaction as the Save: the fact and the state change land
		// together or not at all.
		return uc.outbox.Record(ctx, o.ReleaseEvents())
	})
}
```

Read what is *not* there: no status check, no total check, no "if the order has
no lines" — those are all in `Order.Place`, and that is the whole point.

### Where a port is declared

A `command` package holds use cases and it holds interfaces, and that is the
right answer rather than a compromise: in Go an interface belongs to the code
that **calls** it, so a driven port has nowhere else to be. What decides whether
that reads as mixed is which file each one is in, and there are two cases.

**One caller — declare it in that use case's own file**, immediately above the
struct that holds it. This is most ports, and it is the case that keeps the
package legible: the reader sees the dependency and the thing that depends on it
without moving.

```go
// internal/contexts/ordering/internal/application/command/place_order.go
package command

// Payments authorises money. Only PlaceOrder needs it, so only PlaceOrder's
// file declares it, and a reader learns the dependency where it is used.
type Payments interface {
	Authorise(ctx context.Context, id order.OrderID, amount order.Money) (AuthCode, error)
}

// PlaceOrder makes a draft order binding.
type PlaceOrder struct {
	orders   order.Repository
	payments Payments
	outbox   Outbox
}
```

**Every caller — its own file, named for the port.** `unit_of_work.go` declares
`UnitOfWork`, `outbox.go` declares `Outbox`, `clock.go` declares `Clock`,
`ids.go` declares `IDs`.

```go
// internal/contexts/ordering/internal/application/command/unit_of_work.go
package command

// UnitOfWork runs fn inside one transaction, putting the transaction in the
// context so repositories join it without being handed a handle.
type UnitOfWork interface {
	Run(ctx context.Context, fn func(ctx context.Context) error) error
}
```

Note what that second set has in common: **it is the same four in every
context**, in every project, and none of them is domain vocabulary. They are the
transaction, event delivery, time and identity — the seams a use case needs to
be testable at all. Learn them once and every `command` directory in every
context reads the same way: use-case files, plus those.

Which gives the smell test. **More port files than use-case files in a
`command` package is a finding.** The ports have become a layer of their own,
and the cause is nearly always one of two things: a "use case" that is really a
[domain service](./domain-services.md) and should not be here, or a port that is
really a query on the aggregate and belongs on its
[repository](./repositories.md).

Every port here is consumer-side: declared by what uses it, named for what the
caller needs, implemented in `adapters/outbound` by a type this package never
names.

### Not a `port/` package

The obvious third option is to put them all in `application/port/` and be done
with it. It is wrong on both counts this standard cares about.

It is a package named for a **kind**, which
[`../clean-code/naming.md`](../clean-code/naming.md) forbids and for the usual
reason: nothing can ever be said about what does or does not belong in it, so
everything ends up there. And it separates each interface from its only caller,
which is precisely what a consumer-side port exists to prevent — the moment
`Clock` lives somewhere neutral, the next use case reaches for the existing
`Clock` rather than declaring the two methods it actually needs, and the
interface grows to the union of every caller.

`command` and `query` survive the same test only because their names describe a
**role with a different set of allowed imports** — a boundary, not a cabinet.
→ [`../modular-monolith/enforcement.md`](../modular-monolith/enforcement.md)

### Wrong, and why

```go
// Wrong: business rules in the use case. The aggregate is now a data holder and
// this rule is invisible to anyone reading the model.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd PlaceOrderCommand) error {
	o, _ := uc.orders.ByID(ctx, id)

	if o.Status() != order.StatusDraft {
		return ErrAlreadyPlaced
	}
	if len(o.Lines()) == 0 {
		return ErrNoLines
	}
	if o.Total().IsZero() {
		return ErrZeroTotal
	}

	o.SetStatus(order.StatusPlaced) // and so the aggregate needs a setter
	return uc.orders.Save(ctx, o)
}
```

```go
// Wrong: two aggregates in one transaction.
return uc.tx.Run(ctx, func(ctx context.Context) error {
	o, _ := uc.orders.ByID(ctx, id)
	o.Place(now)
	uc.orders.Save(ctx, o)

	c, _ := uc.customers.ByID(ctx, o.CustomerID())
	c.RecordOrder() // second aggregate
	return uc.customers.Save(ctx, c)
})
```

```go
// Wrong: returns the aggregate. The HTTP handler can now read anything, and
// will, and the model's encapsulation stops at this line.
func (uc *PlaceOrder) Handle(...) (*order.Order, error)

// Wrong: one service, many use cases. Grows without limit, and its dependency
// list is the union of everything any of its methods needs.
type OrderService struct{ ... }
func (s *OrderService) Place(...)  {}
func (s *OrderService) Cancel(...) {}
func (s *OrderService) Ship(...)   {}
func (s *OrderService) Refund(...) {}

// Wrong: the adapter built the domain types. Validation now lives at every
// entry point rather than at one.
func (h *Handler) Place(w http.ResponseWriter, r *http.Request) {
	id, _ := order.NewOrderID(chi.URLParam(r, "id"))   // adapter knows domain
	h.uc.Handle(r.Context(), id)
}

// Wrong: transaction opened in the adapter.
func (h *Handler) Place(w http.ResponseWriter, r *http.Request) {
	tx, _ := h.db.Begin()
	defer tx.Rollback()
	h.uc.Handle(r.Context(), cmd)
	tx.Commit()
}
```

## Commands and queries

A command use case changes state and returns nothing useful. A query use case
changes nothing and returns a [read model](./read-models.md). A method that both
mutates and returns a projection has two reasons to change and no clear
transaction story.

```go
// Command: returns an error and nothing else.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd PlaceOrderCommand) error

// Query: no transaction, no aggregate, no repository.
func (q *ListCustomerOrders) Handle(ctx context.Context, qry ListCustomerOrdersQuery) ([]OrderSummary, error)
```

They are separated by package rather than by convention because everything
about them differs:

| | `command` | `query` |
|---|---|---|
| Loads | One aggregate, through its repository | Nothing. It reads a projection |
| Transaction | Owns one | None |
| Imports `domain` | Yes — the aggregate and its value objects | **No.** A view is primitives |
| Returns | An error, or an identifier | A read model |
| Test seam | In-memory repository | A fake query port, or the real database |

The `query` row that matters is the third. It is the one rule here a tool can
check, and it only became checkable when the package split gave it a path to
match on.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Rules in the use case | Anaemic aggregate; rules invisible to the model |
| `XService` with many methods | Unbounded growth; unrelated dependencies |
| Returns the aggregate | Adapters read model internals |
| Two aggregates per transaction | Boundary is wrong; lock contention |
| Adapter builds domain types | Validation duplicated at every entry point |
| Transaction in the adapter or repository | Nesting problems; no single owner |
| Events published after commit | Lost events |
| Use case calls another use case | Nested transactions; unclear boundary. Extract a domain service instead |
| `ports.go`, `queries.go`, `handlers.go` | A file named for a kind. It is where things go when nobody decided, and it only grows |
| One flat `application` package | The read side can reach the write model, and one day writes through it |
| An `Application` struct holding every use case | A second facade, whose dependency list is the union of everything |
| `application/shared/` | The thing two use cases had in common, promoted to a place the next one will also reach for |

## Checklist

- [ ] `application/` contains `command/` and `query/`, and no Go file of its own
- [ ] One file per use case, named for the use case; the test beside it
- [ ] Every port is in a file named for the port; there is no `ports.go`
- [ ] Nothing under `query/` imports `domain` or a repository
- [ ] One type per use case, named for the use case
- [ ] No conditional reading aggregate state to make a decision
- [ ] Exactly one aggregate loaded and modified per transaction
- [ ] The use case owns the transaction; nothing below it does
- [ ] Commands take primitives and construct value objects here
- [ ] Returns nothing, an id, or a read model — never an aggregate
- [ ] Events recorded in the same transaction as the write

## Sources

**Books.** Vernon, _Implementing Domain-Driven Design_, ch. 14 — "Application".
Evans, _Domain-Driven Design_, ch. 4, where the application layer is defined as
holding no business rules.

**Online.** Every link below was reachable when this page was written.

- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  — Martin; his use-case layer is this layer under another name
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
  — Cockburn; the origin of the port terminology used here
- [Unit of Work](https://martinfowler.com/eaaCatalog/unitOfWork.html)
  — Fowler, PoEAA
- [CQRS](https://martinfowler.com/bliki/CQRS.html) — Fowler, on the separation
  the `command` / `query` split above makes structural
- [Combining DDD, CQRS, and Clean Architecture](https://threedots.tech/post/ddd-cqrs-clean-architecture-combined/)
  — Three Dots Labs; the same two packages, argued in Go, in the most complete
  published Go DDD codebase
- [wild-workouts-go-ddd-example](https://github.com/ThreeDotsLabs/wild-workouts-go-ddd-example)
  — that codebase. It groups the use cases behind an `app.Application` struct,
  which rule 10 above declines: in this standard the context facade already is
  that type
