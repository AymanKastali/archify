# Modules

A module is a bounded context, packaged. This page is about the packaging: what
a context exposes, what constructs it, and what must never leave it.

**Whether** two things are one context or two is
[`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md). **Where the
directories go** is [layout](./layout.md). This page is what happens at the
edge once those are decided.

**Authorities.** Evans, ch. 14. Vernon, ch. 2. Parnas, _On the Criteria To Be
Used in Decomposing Systems into Modules_ (1972) — the original statement that a
module boundary hides a decision, which is the whole argument in two pages.
Ousterhout, ch. 4, for the shape the facade below is aiming at.

## A context exposes two packages and no more

```text
internal/contexts/ordering/ordering.go        the facade  — for the composition root
internal/contexts/ordering/published/         the language — for other contexts
internal/contexts/ordering/internal/...       unreachable from outside. Compile error
```

That is the entire surface. Everything else the context contains is behind the
nested `internal/`, and the restriction is enforced by `go build` rather than by
review. → [enforcement](./enforcement.md)

`migrations/` is the fourth directory and is not a counter-example: it holds
`.sql` files, not a Go package, and it leaves the context as bytes through the
facade. → [data](./data.md)

**The two audiences are different and must not be merged.** The composition root
constructs; other contexts integrate. A type that both need is a published type
the facade happens to return, never a facade method another context calls
directly.

## The rules

1. **The facade is the only non-published export.** One file, `<context>.go`,
   in package `<context>`.
2. **The facade constructs; it does not decide.** Its body is `New`, wiring, and
   thin delegation. A conditional in it that reads business state is a rule that
   escaped the model.
3. **The facade returns behaviour, never internals.** No repository, no
   `*sql.DB`, no `*sql.Tx`, no application-service pointer, no domain type.
4. **Nothing in `published/` is a domain type.** It is data with JSON tags,
   importing nothing from this context. A rename inside the model must not
   change it.
   → [`../ddd/context-mapping.md`](../ddd/context-mapping.md), rule 4
5. **`published/` is append-only.** A breaking change is a new type —
   `OrderPlacedV2` — carried alongside the old one until every consumer moved.
   The compiler will not tell you; the consumers are in the same repository and
   you must check them by hand.
6. **A context never imports another context's facade package.** It declares the
   slice of behaviour it needs as its own interface, and the composition root
   satisfies it. See below — this is the rule extraction depends on.
7. **A context may import another context's `published/`** in exactly two
   places: its `adapters/`, where the ACL translates, and its **facade**, where
   it declares the interface rule 6 requires. **Never in `domain` or
   `application`** — a published type named in a use case is an upstream
   contract that reached the model.
   → [communication](./communication.md)
8. **One `CONTEXT.md` per context**, living in the context directory. If you
   cannot write one, this is not a context.
9. **A context owns its schema and its migrations.** → [data](./data.md)
10. **A context has no global state.** No package-level `var` holding a
    connection, a registry, a logger or a singleton. Everything arrives through
    `New`.

## The facade

```go
// Package ordering is the ordering bounded context.
//
// This file is the context's entire non-published surface. Everything else is
// under internal/ and cannot be imported from outside this directory — that is
// a compile error rather than a convention.
//
// Other contexts integrate through ordering/published and through interfaces
// they declare themselves. They do not import this package; it exists for the
// composition root.
package ordering

// Component is the assembled ordering context. The composition root builds one
// and holds it for the life of the process.
type Component struct {
	place   *command.PlaceOrder
	cancel  *command.CancelOrder
	summary *query.SummariseOrder
	relay   *outbox.Relay
	routes  http.Handler
}

// Deps is everything ordering needs from outside itself. Every field is an
// interface or a value; none is another context's type.
type Deps struct {
	DB     *pgxpool.Pool
	Bus    Publisher
	Clock  Clock
	IDs    IDs
	Logger *slog.Logger
}

// New assembles the context. It is the only constructor, and it fails rather
// than returning a half-built Component.
func New(d Deps) (*Component, error) {
	if d.DB == nil {
		return nil, errors.New("ordering: DB is required")
	}

	orders := postgres.NewOrders(d.DB)
	outboxStore := postgres.NewOutbox(d.DB)

	place := command.NewPlaceOrder(orders, outboxStore, d.Clock, d.IDs)
	cancel := command.NewCancelOrder(orders, outboxStore, d.Clock)
	summary := query.NewSummariseOrder(postgres.NewOrderReads(d.DB))

	c := &Component{
		place:   place,
		cancel:  cancel,
		summary: summary,
		relay:   outbox.NewRelay(outboxStore, d.Bus, d.Logger),
	}
	c.routes = httpin.NewRouter(place, cancel, summary)
	return c, nil
}

// Routes is ordering's HTTP surface. The composition root mounts it; it does
// not know what is inside.
func (c *Component) Routes() http.Handler { return c.routes }

// Subscriptions are the published events from other contexts this one consumes.
func (c *Component) Subscriptions() []eventbus.Subscription {
	return []eventbus.Subscription{
		{Topic: "billing.InvoiceSettled", Handle: c.onInvoiceSettled},
	}
}

// Run drives ordering's background work — here, the outbox relay — until ctx is
// cancelled. It is supervised by the composition root, not by a goroutine
// started in New.
func (c *Component) Run(ctx context.Context) error { return c.relay.Run(ctx) }

// OrderSummary answers a question another context is entitled to ask. The
// query returns this context's own view type; translating it to the published
// language here is what keeps the view free to change.
func (c *Component) OrderSummary(ctx context.Context, id string) (published.OrderSummary, error) {
	v, err := c.summary.Handle(ctx, query.SummariseOrderQuery{OrderID: id})
	if err != nil {
		return published.OrderSummary{}, err
	}
	return published.OrderSummary{
		OrderID:    v.OrderID,
		Status:     v.Status,
		TotalMinor: v.TotalMinor,
		Currency:   v.Currency,
	}, nil
}
```

### Why the type is called `Component`

Three obvious names are wrong, and the reasons are worth stating once:

| Name | Why not |
|---|---|
| `ordering.Context` | Collides with `context.Context` at every call site. A reader cannot tell which one a parameter is |
| `ordering.Module` | `module` is `go.mod`, and it is `/codebase-design`'s word for a package → [`../vocabulary.md`](../vocabulary.md) |
| `ordering.Ordering` | The anti-stutter exception in [`../clean-code/naming.md`](../clean-code/naming.md) is granted to the **aggregate root and its identifier**, because those are glossary words. A facade is not a glossary word and does not get it |

The name is written twice — in `New`'s signature and in the composition root's
`Deps` — because everything else uses `:=`. Pick the unambiguous word and move
on.

## The rule that makes extraction mechanical

**Rule 6 is the load-bearing one.** When `shipping` needs to ask `ordering`
something, it does not import `ordering`. It declares the question:

```go
// internal/contexts/shipping/shipping.go
package shipping

// OrderQueries is the slice of the ordering context shipping actually uses.
// Declared here, satisfied structurally by *ordering.Component today and by an
// HTTP client the day ordering becomes a service.
type OrderQueries interface {
	OrderSummary(ctx context.Context, id string) (orderingpub.OrderSummary, error)
}

type Deps struct {
	DB     *pgxpool.Pool
	Orders OrderQueries
	Logger *slog.Logger
}
```

```go
// internal/composition/contexts.go — the only file that names both contexts.
ord, err := ordering.New(ordering.Deps{DB: pool, Bus: bus, Clock: clock, IDs: ids, Logger: log})
if err != nil {
	return nil, err
}

shp, err := shipping.New(shipping.Deps{DB: pool, Orders: ord, Logger: log})
if err != nil {
	return nil, err
}
```

Two consequences:

- **The import graph shows no edge from `shipping` to `ordering`** except to
  `orderingpub`, which is data. Go's structural interfaces mean the coupling is
  satisfied without being declared.
- **Extraction is one line.** `Orders: ord` becomes
  `Orders: orderingclient.New(cfg.OrderingURL)`. Nothing in `shipping` changes,
  including its tests, which were already using a fake.
  → [extraction](./extraction.md)

## `published/`

```go
// Package published is ordering's contract with every other context. These
// types are versioned, they are not the domain model, and a change here is a
// breaking change even when the compiler stays silent.
package published

// Topic names are part of the contract too. They are constants so a consumer
// subscribes to a symbol rather than to a string literal.
const (
	TopicOrderPlaced    = "ordering.OrderPlaced"
	TopicOrderCancelled = "ordering.OrderCancelled"
)

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

// OrderSummary answers what other contexts may ask about an order. It is
// deliberately less than the aggregate: no internal status, no pricing policy,
// no audit trail.
type OrderSummary struct {
	OrderID    string `json:"order_id"`
	CustomerID string `json:"customer_id"`
	Status     string `json:"status"`
}
```

Note what is absent: no `order.OrderID`, no `Money`, no `Status` type. Published
types are primitives and other published types, because the consumer is going to
turn them into **its own** value objects at its ACL, and because the day this
crosses a network it has to survive being JSON.

## Wrong, and why

```go
// Wrong: the facade hands out its internals. Every caller is now coupled to
// ordering's persistence, and the transaction boundary has left the context.
func (c *Component) Orders() order.Repository { return c.orders }
func (c *Component) DB() *pgxpool.Pool        { return c.db }
```

```go
// Wrong: the facade decides. This is a business rule in the composition layer
// of a context, where no test of the model will ever reach it.
func (c *Component) PlaceOrder(ctx context.Context, cmd Cmd) error {
	if cmd.Total > 10_000 {
		return errors.New("needs approval")
	}
	return c.place.Handle(ctx, cmd)
}
```

```go
// Wrong: shipping imports ordering's facade package. It compiles, and it is
// still the defect rule 6 exists to prevent — the day ordering moves, every
// file that named it changes.
import "myapp/internal/contexts/ordering"

func NewShipmentPlanner(ord *ordering.Component) *ShipmentPlanner { ... }
```

```go
// Wrong: package-level state. Two tests in one binary now share a connection,
// and construction order became invisible.
package ordering

var db *pgxpool.Pool

func Init(pool *pgxpool.Pool) { db = pool }
```

```go
// Wrong: a published type that is the domain type.
package published

type OrderPlaced struct {
	Order order.Order // renaming a private field is now a contract break
}
```

## How many contexts

**When in doubt, one.** The asymmetry is real:

- One context that should have been two is a refactor inside one compile unit,
  with the compiler checking every move.
- Two contexts that should have been one are coupled through a published
  language, an ACL, an event, eventual consistency and two schemas — forever,
  and every change touches all of it.

So a second context is added when the **language has already diverged** — the
same noun means two things, the invariants differ, the lifecycles differ, a
different person is the authority.
→ [`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md)

Never add one because a package got large, because a directory would be tidier,
or because it might be a service one day.

### The cost of a context, stated

So the decision is made with the price visible:

| You gain | You pay |
|---|---|
| A compile-enforced boundary | A schema, its migrations, and no joins across it |
| A model free to diverge | A published language and an ACL per consumer |
| A unit that can be extracted | Eventual consistency between the two halves |
| An independently reviewable surface | A `CONTEXT.md`, an entry in `CONTEXT-MAP.md`, a facade |

### Merging two contexts

Legitimate, and usually the right correction when the boundary was wrong. It is
also mostly deletion: remove the published types, remove the ACL, remove one
schema by migrating its tables, collapse the two facades into one. Do it in that
order, and record it as an ADR — a context that appeared in `CONTEXT-MAP.md` and
then vanished without one reads as an accident.

## Checklist

- [ ] The context directory has exactly `CONTEXT.md`, `<name>.go`, `published/`, `migrations/`, `internal/`
- [ ] The facade exposes only construction, routes, subscriptions, `Run`, and published-type queries
- [ ] No facade method returns a domain type, a repository, or a database handle
- [ ] No conditional in the facade reads business state
- [ ] No context imports another context's facade package
- [ ] `published/` imports nothing from this context and carries no behaviour
- [ ] No package-level variable holds state
- [ ] `New` returns an error rather than a partially built `Component`

## Sources

**Books.** David Parnas, "On the Criteria To Be Used in Decomposing Systems into
Modules", _Communications of the ACM_ 15(12), December 1972, pp. 1053–1058,
doi:10.1145/361598.361623 — the origin of information hiding, and still the
shortest correct statement of why rule 3 exists. Evans, ch. 14. Vernon, ch. 2
and ch. 3. Ousterhout, _A Philosophy of Software Design_, ch. 4, for narrow
interfaces over deep implementations. Sam Newman, _Building Microservices_, 2nd
ed., ch. 1, for information hiding as the actual point of a service boundary —
an argument that never mentions the network and therefore applies here unchanged.

**Online.** Every link below was reachable when this page was written.

- [Modular Monolith: A Primer](https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer)
  — Grzybek, for the module-contract idea this page's facade is the Go reading of
- [modular-monolith-with-ddd](https://github.com/kgrzybek/modular-monolith-with-ddd)
  — his reference implementation, where the module contract is explicit
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — what
  makes "unreachable from outside" true
- [Package names](https://go.dev/blog/package-names) — the naming argument
  behind the `Component` table above
- [Go Code Review Comments: interfaces](https://go.dev/wiki/CodeReviewComments#interfaces)
  — the Go team's statement that the **consumer** declares the interface, which
  is rule 6 arrived at from the language side
- [Anti-corruption Layer pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer)
  — a compact statement of what the consuming side owes itself
