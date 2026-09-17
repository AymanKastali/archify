# Specifications

A specification is a **predicate expressed as a domain object**: a named,
immutable thing that answers one yes/no question about one kind of domain
object, in the language the business uses to ask it.

**Authority.** Evans, ch. 9 ("Making Implicit Concepts Explicit"). Evans &
Fowler, _Specifications_ (1997) — the source paper, and the place the three uses
are named. Vernon, ch. 12, for its use as query criteria.

## Why it exists

A rule like "an invoice is overdue" starts life as an `if` in three places: the
dunning job, the account screen, and a SQL `WHERE` clause. The concept has no
name, three implementations, and they drift.

Evans's point is not that predicates need objects. It is that **a rule the
business has a word for is a modelling concept**, and a concept with no home
in the model ends up scattered across the code that happens to need it.

A specification gives it one home, one name, and one definition.

## The three uses

Evans names three, and the distinction matters because the first is nearly
always worth it and the third nearly never is.

| Use | Question | Frequency |
|---|---|---|
| **Validation** | Does this object satisfy the rule? | Common |
| **Selection** | Which stored objects satisfy it? | Common, and the hard one |
| **Construction to order** | Build me something that satisfies it | Rare |

## When it is warranted

All of:

1. **The business has a name for the rule** — "overdue", "eligible for free
   shipping", "high risk". If you cannot name it without describing it, it is
   an `if`.
2. **The rule is asked from more than one place**, or is asked from outside the
   object it is about.
3. **The answer is genuinely yes/no.** A rule that must explain itself is an
   [error](./errors.md), not a specification.

If only (1) holds, it is a method on the aggregate. **An invariant is not a
specification** — invariants live inside the aggregate and are enforced by it.
A specification is a question asked *about* an object, usually from outside it.

## The rules

1. **A specification is a value object.** Immutable, constructed valid, compared
   by value, no identity. See [value objects](./value-objects.md).
2. **It lives in `domain`,** in the package of the type it is about.
3. **Named as the business names the rule** — `OverdueInvoice`,
   `EligibleForFreeShipping`. Not `InvoiceSpec`, not `OrderRule`,
   not `Validator`.
4. **It answers `bool`, and nothing else.** No error, no reason, no side effect.
5. **Its criteria are its fields.** `OverdueInvoice{AsOf: t}` — the parameters
   of the question are data on the specification, which is what makes it a value
   rather than a closure.
6. **It takes no `context.Context`, loads nothing, and calls no port.** A rule
   needing collaborators is a [domain service](./domain-services.md).
7. **Used for selection, it must be translatable.** See below — this is the rule
   that decides whether specifications help or wreck the persistence layer.

## In Go

### Validation — the common case

```go
// internal/contexts/billing/internal/domain/invoice/specifications.go
package invoice

// Overdue is the business's definition of an overdue invoice, in one place.
// Before this type existed the definition was an `if` in the dunning job and a
// slightly different `if` on the account screen.
//
// AsOf is a field rather than a parameter because "overdue as of when" is part
// of the question, and making it data is what lets the same specification be
// held, passed and compared.
type Overdue struct {
	AsOf time.Time
}

func (s Overdue) IsSatisfiedBy(i *Invoice) bool {
	return i.status == StatusIssued &&
		i.dueDate.Before(s.AsOf) &&
		!i.balance.IsZero()
}
```

```go
// Used from an application service. The rule is not re-stated here; it is asked.
if (invoice.Overdue{AsOf: s.clock.Now()}).IsSatisfiedBy(inv) {
	...
}
```

### The aggregate may ask the specification too

When the same rule is both enforced inside and queried outside, the aggregate
delegates rather than duplicating:

```go
package order

// EligibleForFreeShipping is the rule, named as the business names it.
type EligibleForFreeShipping struct {
	Threshold Money
}

func (s EligibleForFreeShipping) IsSatisfiedBy(o *Order) bool {
	return o.total.GreaterThanOrEqual(s.Threshold) && o.destination.IsDomestic()
}

// ApplyShipping is the aggregate enforcing the rule. It asks the specification
// rather than restating the condition, so there is exactly one definition.
func (o *Order) ApplyShipping(policy ShippingPolicy) error {
	if (EligibleForFreeShipping{Threshold: policy.FreeAbove}).IsSatisfiedBy(o) {
		o.shipping = Zero(o.total.Currency())
		return nil
	}
	...
}
```

### Selection — the rule that decides everything

An `IsSatisfiedBy` that takes a loaded aggregate cannot be evaluated by the
database. So a specification used for selection must be **translatable to the
query language**, and the only way to keep that honest is to make the set of
specifications a repository accepts **closed**:

```go
// internal/contexts/billing/internal/domain/invoice/repository.go
package invoice

// Criteria is the closed set of questions this collection can be asked.
// It is a struct of optional criteria, not an open predicate interface,
// precisely so that every question it can express is one the adapter can
// translate into a query.
type Criteria struct {
	CustomerID  *CustomerID
	OverdueAsOf *time.Time
	Limit       int
}

type Repository interface {
	ByID(ctx context.Context, id InvoiceID) (*Invoice, error)
	Matching(ctx context.Context, c Criteria) ([]*Invoice, error)
	...
}
```

```go
// The adapter translates. This is the whole trick: the translation exists in
// exactly one place, and the compiler tells you when a criterion is unhandled.
func (r *InvoiceRepository) Matching(ctx context.Context, c invoice.Criteria) ([]*invoice.Invoice, error) {
	where := []string{"1 = 1"}
	args := []any{}

	if c.CustomerID != nil {
		args = append(args, c.CustomerID.String())
		where = append(where, fmt.Sprintf("customer_id = $%d", len(args)))
	}
	if c.OverdueAsOf != nil {
		args = append(args, *c.OverdueAsOf)
		where = append(where, fmt.Sprintf(
			"status = 'issued' AND due_date < $%d AND balance_minor <> 0", len(args)))
	}

	rows, err := r.db.QueryContext(ctx,
		`SELECT `+invoiceColumns+` FROM invoices WHERE `+strings.Join(where, " AND ")+
			` ORDER BY due_date LIMIT $`+strconv.Itoa(len(args)+1),
		append(args, limitOr(c.Limit, 100))...)
	...
}
```

Hand-written SQL, because the criteria set is closed: there are two branches
here and there will never be an unbounded number of them. A query builder is
what you reach for when the criteria set is open, and an open criteria set is
the thing this design exists to prevent.

**The duplication here is real and it is the price.** `Overdue.IsSatisfiedBy`
and the SQL above state the same rule twice. Accept it, keep them adjacent in
review, and test them against each other — a table-driven test that runs both
over the same fixtures is the standard way to hold them together.

The alternative — a specification that renders its own SQL — puts the query
language in `domain` and is worse.

**And most of the time, you do not need selection at all.** If the answer feeds
a screen or a report rather than a decision, it is a
[read model](./read-models.md), the query lives in `application` as a port, and
no specification is involved.

### Construction to order

Evans's third use: a specification as the spec for building something.

```go
// Rare, and only when the business genuinely asks for it this way.
func BuildTo(s ShipmentSpec, available []Package) (*Shipment, error)
```

Do not build this speculatively. Write it when a use case actually asks "give me
one that satisfies this", and not before.

### Composition

Go has no natural home for a `Specification[T]` interface with `And`/`Or`/`Not`
combinators, and importing one from Java is the usual mistake. Introduce it only
when composition happens **at runtime** — user-defined rules, configurable
policies, a rules engine:

```go
// Justified only when the combination is not known at compile time.
type Specification[T any] interface{ IsSatisfiedBy(T) bool }

type and[T any] struct{ a, b Specification[T] }

func (s and[T]) IsSatisfiedBy(t T) bool { return s.a.IsSatisfiedBy(t) && s.b.IsSatisfiedBy(t) }
```

When the combination is known at compile time, `a.IsSatisfiedBy(x) && b.IsSatisfiedBy(x)`
is the composition, and it is better.

## Wrong, and why

```go
// Wrong: not a domain concept, just an `if` wearing a type. No business ever
// said "non-empty order specification".
type NonEmptyOrderSpecification struct{}

// Wrong: the name is from the pattern catalogue, not the glossary.
type InvoiceSpec struct{ ... }
type OrderValidator struct{ ... }

// Wrong: returns why. A specification answers yes or no; a rule that explains
// its refusal is an error, and belongs on the aggregate.
func (s Overdue) IsSatisfiedBy(i *Invoice) (bool, string)

// Wrong: loads. `domain` now depends on persistence, and a predicate has become
// a query. If the rule needs another aggregate, pass it in or make it a domain
// service.
func (s HighRisk) IsSatisfiedBy(ctx context.Context, c *Customer) bool {
	history, _ := s.orders.ByCustomer(ctx, c.ID())
	...
}

// Wrong: renders SQL. The query language is now in the model, and the
// specification is coupled to one database.
func (s Overdue) ToSQL() string { return "status = 'issued' AND due_date < ?" }

// Wrong: an open predicate interface at the repository boundary. The adapter
// cannot translate an arbitrary function, so it loads every invoice and filters
// in memory. This works in development and falls over in production.
type Repository interface {
	Matching(ctx context.Context, spec Specification[*Invoice]) ([]*Invoice, error)
}

// Wrong: the aggregate's invariant extracted into a specification. Now an
// Invoice can be constructed violating it, because nothing enforces it at the
// boundary — it is only checked where someone remembers to ask.
type InvoiceMustHaveLines struct{}
```

The open-predicate repository is the most damaging one, because it reads like
the textbook and it is the reason so many codebases have a `FindAll` followed by
a filter loop.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Specification for a rule the business has no word for | Ceremony, and a type per `if` |
| Named `…Spec`, `…Rule`, `…Validator` | The glossary is not the source of names |
| Returns a reason as well as a bool | It is an error, modelled as a predicate |
| Loads or takes `context.Context` | Persistence in `domain` |
| Renders SQL | The query language is in `domain` |
| Open predicate at the repository boundary | Load-everything-and-filter |
| An aggregate invariant moved into a specification | The invariant stops being enforced |
| Java-style `And`/`Or`/`Not` hierarchy built up front | Machinery with no runtime composition to justify it |

## Checklist

- [ ] The business has a name for this rule, and the type uses it
- [ ] It is a value object: immutable, criteria as fields, compared by value
- [ ] It returns `bool` only
- [ ] It loads nothing and takes no `context.Context`
- [ ] It is not an aggregate invariant in disguise
- [ ] If used for selection, the criteria set is closed and the adapter
      translates it — nothing filters in memory
- [ ] Combinators exist only if composition happens at runtime
- [ ] If the answer feeds a screen rather than a decision, it is a read model

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 9 — "Making Implicit Concepts
Explicit". Vernon, _Implementing Domain-Driven Design_, ch. 12, where
Specification appears as query criteria.

**Online.** Every link below was reachable when this page was written.

- [Specifications](https://martinfowler.com/apsupp/spec.pdf)
  — Evans & Fowler, 1997 (PDF); the source paper, and where validation,
    selection and construction-to-order are named
- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
- [Repository](https://martinfowler.com/eaaCatalog/repository.html)
  — Fowler, PoEAA; §Specification is where the translation problem is first
    acknowledged
