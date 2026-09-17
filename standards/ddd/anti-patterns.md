# Anti-patterns

The failures this standard exists to prevent. Each one is common, each one looks
like DDD from a distance, and each one is detectable in a diff.

## 1. The anaemic domain model

**The big one.** Every other item on this page is a way of arriving here.

Aggregates are structs of exported fields with getters and setters. All the
rules live in services. The vocabulary is DDD; the design is a transaction
script over a data model.

```go
// The symptom
type Order struct {
	ID     string
	Status string
	Total  float64
	Lines  []Line
}

type OrderService struct{ repo OrderRepository }

func (s *OrderService) PlaceOrder(ctx context.Context, id string) error {
	o, _ := s.repo.ByID(ctx, id)
	if o.Status != "draft" {
		return ErrAlreadyPlaced
	}
	if len(o.Lines) == 0 {
		return ErrNoLines
	}
	o.Status = "placed"
	return s.repo.Save(ctx, o)
}
```

**Why it happens.** It is what an ORM tutorial teaches, it is what a database
schema suggests, and it is what you get by default if nobody decides otherwise.

**Why it costs.** The rule "an order is placed exactly once" now lives in
`OrderService`. When a second path to placing an order appears — an admin tool,
a batch import, a retry — the rule is either duplicated or forgotten, and
nothing in the model prevents `o.Status = "placed"` on an empty order.

**The test.** Open the aggregate. Can you read the business rules? If it is
fields and accessors, it is anaemic.

**The fix.** Unexport the fields. Delete the setters. Move every conditional
that reads aggregate state out of the service and onto the aggregate as a named
act. See [aggregates](./aggregates.md).

## 2. The god aggregate

One aggregate that reaches everything — customer, orders, invoices, shipments,
support cases — because it was modelled from the object graph rather than from
an invariant.

**The test.** State the rule the aggregate protects in one sentence. If it takes
several, it is several aggregates.

**The fix.** Rule 2 and rule 3 of [aggregates](./aggregates.md): find the real
invariant, keep what it mentions, replace everything else with identifiers.

## 3. The repository that became a DAO

```go
type OrderRepository interface {
	ByID(ctx, id) (*Order, error)
	ListByCustomer(ctx, c) ([]OrderSummary, error)
	TotalRevenueByMonth(ctx) ([]MonthlyTotal, error)
	UpdateStatus(ctx, id, status) error
	SearchOrders(ctx, criteria) ([]OrderRow, error)
}
```

Four of those five are not repository methods. `UpdateStatus` writes around the
aggregate; the rest return things that are not aggregates.

**Why it happens.** A screen needs a list, and the repository is right there.

**The fix.** Repositories deal in aggregates only. Everything else is a
[read model](./read-models.md) declared by the use case that needs it.

## 4. Primitive obsession

```go
func Transfer(ctx context.Context, from, to string, amount float64, currency string) error
```

Transposable arguments, no validation anywhere in particular, float money.

**The fix.** [Value objects](./value-objects.md). This is the single change with
the best ratio of effort to defects removed.

## 5. Persistence in the model

```go
type Order struct {
	ID     string `gorm:"primaryKey" json:"id"`
	Status string `gorm:"index"      json:"status"`
}
```

The model now describes its storage and its wire format. The dependency rule is
broken by a struct tag, which is why this one survives so many reviews.

**Why it happens.** It removes a mapping layer, and the mapping layer feels like
duplication.

**The fix.** The mapping layer is not duplication; it is the boundary. Domain
types have no tags; `adapters/outbound` converts. See
[`structure.md`](../structure.md) and [repositories](./repositories.md).

## 6. `Manager`, `Helper`, `Util`, `Processor`

A type named for none of the business's concepts, which is therefore free to
contain anything and inevitably does.

**The test.** Would a domain expert use this word? Can you state what the type
is responsible for in one sentence without "and"?

**The fix.** Find the act it performs and name it for that, or put the behaviour
on the aggregate or value object it belongs to. See
[ubiquitous language](./ubiquitous-language.md).

## 7. The shared kernel that ate the model

One `shared` or `common` package holding types two contexts needed once. It
grows, because adding to it is always easier than translating. Eventually every
context depends on it and no boundary exists.

**The fix.** The shared kernel holds only types with no domain meaning, and
adding to it takes an ADR. Everything else is duplicated and translated. See
[bounded contexts](./bounded-contexts.md).

## 8. Events that are commands

```go
type SendConfirmationEmail struct{ OrderID string }
```

The producer is telling the consumer what to do. The coupling the event was
supposed to remove is intact, with a message broker added.

**The fix.** Publish `OrderPlaced`. What to do about it is the consumer's
decision. See [domain events](./domain-events.md).

## 9. The distributed monolith

Contexts split into services that call each other synchronously, share a
database, or require a distributed transaction. All the operational cost of
distribution and none of the independence.

**The test.** Can one service be deployed while another is down? If not, they
are one system with network calls between its parts.

**The fix.** Events over synchronous calls, a schema per context, eventual
consistency across boundaries — and prefer one deployable until a specific
scaling or team constraint demands otherwise. See
[context mapping](./context-mapping.md).

## 10. Layers without dependency inversion

A tree with `domain/`, `application/` and `infrastructure/` directories — and
`domain` imports `infrastructure`. The layout is DDD; the dependency graph is
not.

**The test.** Not a reading exercise: a lint rule. See
[`structure.md`](../structure.md).

## 11. DDD applied to everything

A CRUD admin screen modelled with an aggregate, three value objects, a
repository and two domain events, to save a form with no rules.

DDD is for domains with complexity worth managing. A part of the system that is
genuinely a form over a table should be written as one, in its own context, and
labelled as such.

**The fix.** Ask what invariant the aggregate protects. If the answer is "none",
this is not a domain model. That is a legitimate finding, not a failure.

## 12. The mapped-database model

Aggregates that mirror tables one-to-one, named for tables, with a repository
per table and foreign keys as object references. Every join in the schema
becomes a field, and the invariant is whatever the constraints happen to be.

**The test.** Was the model derived from the schema or from a conversation about
rules?

**The fix.** Model the invariant first, then decide how to store it. The schema
is an adapter concern; two aggregates may share a table and one aggregate may
span three.

## 13. The specification that filters in memory

```go
// The repository takes an arbitrary predicate, so the adapter has no choice:
invoices, _ := repo.Matching(ctx, spec) // SELECT * FROM invoices; then filter
```

An open predicate interface at the repository boundary cannot be translated into
a query, so the adapter loads the table and filters in Go. It passes every test,
because the test fixture has four rows.

Its mirror image is the `Specification` type written for a rule the business has
no word for — a type per `if`, which is Java ceremony rather than modelling.

**The test.** Can the adapter turn every question this interface can express
into a `WHERE` clause, without reflection?

**The fix.** A closed criteria type the adapter translates, or a
[read model](./read-models.md) if the answer feeds a screen rather than a
decision. See [specifications](./specifications.md).

## Review heuristics

A diff is suspect when it contains:

- A setter on a domain type
- An exported field on an aggregate
- A struct tag in `domain`
- `interface{}` / `any` in a domain signature
- `context.Context` in a domain method that is not a repository interface
- A service whose name ends in `Service`, `Manager`, `Processor` inside `domain`
- A repository method returning anything but its aggregate
- Two `Save` calls in one transaction
- `errors.New` inside a function body in `domain`
- A `float64` holding money
- `type X string` for a closed set
- A conditional in `application` reading aggregate state
- A predicate or function passed to a repository method
- A `Specification` type for a rule with no name in the glossary

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 5, for the model these failures
depart from. Vernon, _Implementing Domain-Driven Design_, ch. 10, for aggregate
sizing. Fowler, _Patterns of Enterprise Application Architecture_ (2002), for
the catalogue entries the anti-patterns are degenerate forms of.

**Online.** Every link below was reachable when this page was written.

- [AnemicDomainModel](https://martinfowler.com/bliki/AnemicDomainModel.html)
  — Fowler; anti-pattern 1, in the original
- [TransactionScript](https://martinfowler.com/eaaCatalog/transactionScript.html)
  — Fowler, PoEAA; a legitimate pattern, and what an anaemic model is pretending
    not to be
- [Effective Aggregate Design](https://www.dddcommunity.org/library/vernon_2011/)
  — Vernon; anti-pattern 2 in detail
- [Pattern: Saga](https://microservices.io/patterns/data/saga.html)
  — Richardson; the alternative to the two-aggregate transaction behind
    anti-pattern 9
- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  — Martin; anti-pattern 10 is this article's rule broken
