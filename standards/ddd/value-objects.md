# Value objects

A concept defined entirely by its attributes, with no identity of its own. Two
value objects with equal attributes are the same value. `Money{10, "EUR"}` is
`Money{10, "EUR"}` in the way that two `10`s are the same 10.

**Authority.** Evans, ch. 5. Vernon, ch. 6.

## Why it exists

**The value object is the default building block, and everything else is the
exception.** This is the single highest-leverage rule on any of these pages,
because a model built from primitives cannot state its own rules.

Consider a signature built from primitives:

```go
func Ship(orderID string, weight float64, quantity int, destination string) error
```

Every parameter admits values the domain does not: an empty `orderID`, a
negative `weight`, a `quantity` of zero, a `destination` that is a customer's
name because someone passed the arguments in the wrong order. The compiler
approves all of it. Every function that receives these values must re-validate
them, and one that forgets is the bug.

Now the same signature built from value objects:

```go
func Ship(orderID OrderID, weight Weight, quantity Quantity, destination Address) error
```

Nothing here can be constructed invalid, the arguments cannot be transposed, and
no function downstream validates anything, because validity was established once
at construction and is now a property of the type.

This is what "make invalid states unrepresentable" means in practice, and it is
mostly achieved with value objects rather than with clever types.

## The rules

1. **Immutable.** No method mutates; a change returns a new value.
2. **Compared by value.** Equality is attribute equality.
3. **Constructed by a function returning `(T, error)`.** Validation lives there
   and nowhere else.
4. **Fields unexported.** A struct literal must not be able to bypass the
   constructor.
5. **A closed set is not a `string`.** See below — this is the most common
   violation and it is worth its own rule.
6. **Self-validating, and total.** Once constructed, every method works. No
   method returns an error because the value might be malformed.
7. **Behaviour belongs on the value.** `Money.Add`, `Quantity.Times`,
   `DateRange.Overlaps` — not free functions taking two values.
8. **Side-effect free.** A method returns a result; it does not change anything.

## In Go

### The basic shape

```go
package order

import (
	"errors"
	"fmt"
	"strings"
)

var (
	ErrSKUEmpty     = errors.New("sku is empty")
	ErrSKUMalformed = errors.New("sku must be three letters, a dash, and four digits")
)

// SKU identifies a sellable product. The format is the vendor's and is fixed:
// three uppercase letters, a dash, four digits.
type SKU struct {
	value string
}

// NewSKU is the only way to obtain a SKU. Every SKU in the program has passed
// through here, so no other code validates one.
func NewSKU(s string) (SKU, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return SKU{}, ErrSKUEmpty
	}
	if !skuPattern.MatchString(s) {
		return SKU{}, fmt.Errorf("%w: %q", ErrSKUMalformed, s)
	}
	return SKU{value: s}, nil
}

// String returns the SKU as the vendor writes it.
func (s SKU) String() string { return s.value }
```

`value` is unexported, so `SKU{value: "nonsense"}` is impossible outside the
package and `SKU{}` outside the package is impossible too. Inside the package it
is possible, which is why the package is small and is the aggregate's package —
see [aggregates](./aggregates.md).

### A closed set is not a `string`

```go
// Wrong. Admits every string in the language; a typo compiles and ships.
type Status string

const (
	StatusDraft  Status = "draft"
	StatusPlaced Status = "placed"
)

var s Status = "drfat"       // compiles
var s Status = someUserInput // compiles
```

```go
// Correct. The set is closed: the zero value is invalid, construction from
// outside is impossible, and the only values in existence are the constants.
type Status struct {
	name string
}

var (
	StatusDraft     = Status{"draft"}
	StatusPlaced    = Status{"placed"}
	StatusCancelled = Status{"cancelled"}
)

func (s Status) String() string { return s.name }

// ParseStatus converts a stored or transmitted value back into a Status. It is
// the boundary between strings and the closed set, and it is the only one.
func ParseStatus(s string) (Status, error) {
	switch s {
	case StatusDraft.name:
		return StatusDraft, nil
	case StatusPlaced.name:
		return StatusPlaced, nil
	case StatusCancelled.name:
		return StatusCancelled, nil
	default:
		return Status{}, fmt.Errorf("%w: %q", ErrUnknownStatus, s)
	}
}
```

The cost is `ParseStatus` and a little ceremony. The return is that an invalid
status cannot exist anywhere in the program, including in data read from the
database by a migration that ran badly six months ago.

This rule is mechanically checked — see [`structure.md`](../structure.md).

### Behaviour on the value

```go
// Money is an amount in a single currency. Arithmetic across currencies is an
// error rather than a silent conversion.
type Money struct {
	amount   int64 // minor units; never a float
	currency Currency
}

func NewMoney(amount int64, c Currency) (Money, error) {
	if c.IsZero() {
		return Money{}, ErrCurrencyRequired
	}
	return Money{amount: amount, currency: c}, nil
}

// Add returns the sum. It does not mutate either operand.
func (m Money) Add(other Money) (Money, error) {
	if m.currency != other.currency {
		return Money{}, fmt.Errorf("%w: %s and %s", ErrCurrencyMismatch, m.currency, other.currency)
	}
	return Money{amount: m.amount + other.amount, currency: m.currency}, nil
}

// Times returns the amount multiplied by a quantity — the only multiplication
// the domain performs, since money times money is not a thing.
func (m Money) Times(q Quantity) Money {
	return Money{amount: m.amount * int64(q.value), currency: m.currency}
}

func (m Money) IsZero() bool             { return m.amount == 0 }
func (m Money) GreaterThan(o Money) bool { return m.currency == o.currency && m.amount > o.amount }
```

Note `int64` minor units rather than `float64`. Floating point money is a defect
in every domain that has money, and it is the kind of thing a value object
exists to decide once.

Note also that `Add` returns an error and `Times` does not. `Times` is total —
there is no quantity that makes it fail — so it does not pretend otherwise. A
method returning an error it can never produce forces every caller to handle a
case that cannot happen.

### Wrong, and why

```go
// Wrong: mutable. Two holders of the same Money now affect each other, and the
// value has quietly acquired identity.
func (m *Money) Add(o Money) { m.amount += o.amount }

// Wrong: exported fields. The constructor is advisory.
type Money struct {
	Amount   int64
	Currency string
}
m := Money{Amount: -5, Currency: "XXX"}   // compiles

// Wrong: validation outside the type, repeated at every call site.
func PlaceOrder(sku string) error {
	if !isValidSKU(sku) {   // and the next caller forgets
		return ErrBadSKU
	}
}

// Wrong: a method that can fail because the value might be malformed. It can't
// be — that was settled at construction.
func (s SKU) Prefix() (string, error) {
	if len(s.value) < 3 {
		return "", ErrMalformed
	}
	return s.value[:3], nil
}

// Wrong: primitive obsession restated as a type alias. No constructor, no
// validation, no encapsulation — just a new spelling of string.
type SKU = string
```

The type alias deserves a note because it looks like progress. `type SKU =
string` is *identical* to `string` to the compiler: every string is a SKU and
every SKU is a string. Use a **defined type** (`type SKU struct{...}`, or at
minimum `type SKU string` with a constructor and unexported use), never an alias.

### Serialising a value object

Value objects have unexported fields, so `encoding/json` cannot see them. That
is correct and should not be fixed by exporting the fields. Serialisation is an
adapter concern and lives in `adapters/outbound`:

```go
// internal/contexts/ordering/internal/adapters/outbound/postgres/order.go

// toRow flattens the aggregate into the columns the table has. Mapping lives
// here so the model never grows a tag for a technology.
func toRow(o *order.Order) orderRow {
	return orderRow{
		ID:       o.ID().String(),
		SKU:      o.SKU().String(),
		Amount:   o.Total().MinorUnits(),
		Currency: o.Total().Currency().Code(),
		Status:   o.Status().String(),
	}
}

// fromRow rebuilds it, and every value passes back through its constructor —
// data that has been sitting in a table for a year is untrusted input.
func fromRow(r orderRow) (*order.Order, error) { ... }
```

## When is it an entity instead?

Ask: **if two of these have identical attributes, are they the same thing?**

- Two `Money{10, "EUR"}` — the same. Value object.
- Two `Address` with identical street and postcode — the same. Value object.
- Two `Order` with identical lines placed by the same customer at the same
  instant — still two orders, and the business can tell them apart. Entity.

If you need to track *which one it is* over time, it has identity. See
[entities](./entities.md).

## Common mistakes

| Mistake | What it looks like | Consequence |
|---|---|---|
| Primitive obsession | `func Ship(id, dest string, w float64)` | Transposable arguments; validation everywhere or nowhere |
| `type X string` for a closed set | `type Status string` | Any string is a valid status |
| Exported fields | `Money{Amount: -5}` | Constructor is optional, invariant is decorative |
| `float64` money | `Amount float64` | Rounding errors in financial figures |
| Mutating methods | `func (m *Money) Add(...)` | Shared state; the value has identity now |
| JSON tags on domain values | `` `json:"amount"` `` | Persistence has entered the model |
| Anaemic value object | Struct with a constructor and no behaviour | Logic that belongs on the value is scattered across services |

## Checklist

- [ ] Every domain concept with rules about its valid values is a value object
- [ ] All fields unexported
- [ ] One constructor, returning `(T, error)`, holding all validation
- [ ] No mutating methods
- [ ] Closed sets are defined types with unexported construction, not `string`
- [ ] Money is integer minor units plus a currency
- [ ] No serialisation tags anywhere in `domain`
- [ ] Behaviour over the value lives on the value

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 5 — "A Model Expressed in
Software". Vernon, _Implementing Domain-Driven Design_, ch. 6, which is the
strongest argument anywhere for preferring value objects to entities.

**Online.** Every link below was reachable when this page was written.

- [ValueObject](https://martinfowler.com/bliki/ValueObject.html)
  — Fowler, on equality by value
- [Go spec: type definitions](https://go.dev/ref/spec#Type_definitions)
  — why a defined type and a type alias are not the same tool
- [Constants](https://go.dev/blog/constants)
  — the Go team on the type system behind untyped constants, which is why `type
    Currency string` accepts any string literal
- [Google Go Style Decisions](https://google.github.io/styleguide/go/decisions)
  — on receiver types and when a value type is the right choice
