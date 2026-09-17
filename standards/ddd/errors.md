# Errors

A broken domain rule is a value the caller can act on, not a string it can only
log.

**Authority.** No DDD text covers this; Go has no exceptions, so Vernon's
assumption that a rule violation unwinds the stack does not survive the
crossing. This page is the replacement, and it is a departure from Martin's
*Clean Code* ch. 7 ("prefer exceptions to returning error codes"), which is void
in Go.

## Why it exists

An aggregate refusing an act is a domain outcome, not a failure. "This order has
already been placed" is something the business says, and the caller needs to
distinguish it from "the database is down" — one is a 409 and the other is a
503, one is the user's problem and the other is yours.

If both arrive as `errors.New("something went wrong")`, the adapter can only
guess, and it will guess by matching on strings.

## The rules

1. **Domain errors are declared in the aggregate's package**, as package-level
   variables or types. Never at a call site, never in `application`.
2. **Sentinel for a simple refusal; a type when the caller needs the details.**
3. **Wrap with `%w`** so `errors.Is` and `errors.As` work all the way out.
4. **Wrap with context as it crosses a boundary** — which aggregate, which
   identifier — so a log line locates the failure without a stack trace.
5. **Infrastructure errors never reach `domain`.** They are wrapped in
   `adapters` and, if the model must know something happened, they arrive as a
   domain error.
6. **Inbound adapters map domain errors to their protocol** with `errors.Is` and
   `errors.As`, never by matching on message text.
7. **No panics for domain outcomes.** A panic is for a programming error — an
   impossible state the type system could not express.

## In Go

### Declaring them

```go
// internal/contexts/ordering/internal/domain/order/errors.go
package order

import "errors"

// Sentinels: the caller needs to know which rule was broken and nothing more.
var (
	ErrAlreadyPlaced          = errors.New("order has already been placed")
	ErrNoLines                = errors.New("order has no lines")
	ErrOrderNotDraft          = errors.New("order is not a draft")
	ErrOrderNotFound          = errors.New("order not found")
	ErrConcurrentModification = errors.New("order was modified concurrently")
)
```

```go
// A type, when the caller needs the details to act — here, to tell the customer
// exactly how much short they are.
type InsufficientFundsError struct {
	Required  Money
	Available Money
}

func (e InsufficientFundsError) Error() string {
	return fmt.Sprintf("insufficient funds: need %s, have %s", e.Required, e.Available)
}

// Is lets errors.Is(err, ErrInsufficientFunds) work for callers that only need
// the category, while errors.As still gets the detail.
func (e InsufficientFundsError) Is(target error) bool {
	return target == ErrInsufficientFunds
}
```

### Returning them

```go
func (o *Order) Place(now time.Time) error {
	if o.status != StatusDraft {
		return ErrAlreadyPlaced
	}
	if len(o.lines) == 0 {
		return ErrNoLines
	}
	...
}
```

Bare sentinels, with no wrapping. The aggregate knows which order it is; adding
"order abc123:" here duplicates what the caller will add anyway.

### Wrapping as it crosses

```go
// The repository adds the identifier, because the caller asked for an id and an
// error that does not mention it is harder to act on.
func (r *OrderRepository) ByID(ctx context.Context, id order.OrderID) (*order.Order, error) {
	row, err := r.queries(ctx).GetOrder(ctx, id.String())
	switch {
	case errors.Is(err, sql.ErrNoRows):
		// A driver error becomes a domain error at the boundary. Nothing above
		// this line has heard of database/sql.
		return nil, fmt.Errorf("order %s: %w", id, order.ErrOrderNotFound)
	case err != nil:
		// An infrastructure failure stays an infrastructure failure, with
		// enough context to find it.
		return nil, fmt.Errorf("loading order %s: %w", id, err)
	}
	return toAggregate(row)
}
```

### Mapping at the edge

```go
// internal/contexts/ordering/internal/adapters/inbound/http/errors.go

// statusFor maps a domain error to HTTP. This is the only place in the program
// that knows about status codes, and it matches on identity rather than text.
func statusFor(err error) (int, string) {
	var insufficient order.InsufficientFundsError

	switch {
	case errors.Is(err, order.ErrOrderNotFound):
		return http.StatusNotFound, "order not found"
	case errors.Is(err, order.ErrAlreadyPlaced),
		errors.Is(err, order.ErrOrderNotDraft):
		return http.StatusConflict, err.Error()
	case errors.Is(err, order.ErrNoLines),
		errors.Is(err, order.ErrZeroTotal):
		return http.StatusUnprocessableEntity, err.Error()
	case errors.As(err, &insufficient):
		return http.StatusPaymentRequired, fmt.Sprintf(
			"short by %s", insufficient.Required.Minus(insufficient.Available))
	case errors.Is(err, order.ErrConcurrentModification):
		return http.StatusConflict, "please retry"
	default:
		// Unrecognised: it is ours, not the caller's. Log the detail, return
		// nothing that describes our internals.
		return http.StatusInternalServerError, "internal error"
	}
}
```

The `default` branch is the important one. An unmapped error returns 500 and a
generic message — never `err.Error()`, which is how database schema details end
up in an API response.

## Wrong, and why

```go
// Wrong: created at the call site. Two places refuse the same act with two
// different errors, and neither can be matched.
if o.status != StatusDraft {
	return errors.New("order already placed")
}

// Wrong: string matching. Breaks the day somebody improves the wording.
if strings.Contains(err.Error(), "already placed") {
	w.WriteHeader(http.StatusConflict)
}

// Wrong: loses the chain. errors.Is finds nothing above this line.
if err != nil {
	return fmt.Errorf("failed to place order: %v", err)   // %v, not %w
}

// Wrong: infrastructure error reaching the model.
func (o *Order) Place(now time.Time) error {
	if err := o.db.Ping(); err != nil {   // domain has a database
		return err
	}
}

// Wrong: panic for a domain outcome.
func (o *Order) Place(now time.Time) {
	if o.status != StatusDraft {
		panic("order already placed")
	}
}

// Wrong: an error code enum reinventing what the type system does.
type DomainError struct {
	Code    int
	Message string
}
return DomainError{Code: 1042, Message: "already placed"}

// Wrong: returning an error the function cannot produce, so every caller
// handles a case that cannot occur.
func (m Money) Times(q Quantity) (Money, error) {
	return Money{amount: m.amount * int64(q.Value())}, nil
}
```

## When to panic

Rarely, and only for a programming error — a state the type system could not
express and that no input can produce:

```go
// Acceptable: this switch covers a closed set, and the default is unreachable
// unless someone adds a status and forgets this file.
func (s Status) MustDescribe() string {
	switch s {
	case StatusDraft:
		return "draft"
	case StatusPlaced:
		return "placed"
	default:
		panic(fmt.Sprintf("unhandled status %q — a case is missing", s.name))
	}
}
```

Never panic for invalid input, a broken rule, or a failed dependency. Those are
all values.

## Common mistakes

| Mistake | Consequence |
|---|---|
| `errors.New` at the call site | Same rule, different errors; nothing matchable |
| `%v` instead of `%w` | `errors.Is`/`As` stop working at that line |
| String matching in adapters | Breaks on a wording change |
| Infrastructure errors in `domain` | Dependency rule broken |
| Panics for domain outcomes | Crashes, or recover-blocks that swallow everything |
| Error codes in a struct | Reinvents typed errors, worse |
| Returning `error` from a total function | Every caller handles the impossible |
| `err.Error()` in an HTTP body by default | Internals leak to callers |

## Checklist

- [ ] Every domain error is declared in the aggregate's package
- [ ] Sentinels for simple refusals; types where the caller needs details
- [ ] Wrapping uses `%w` everywhere
- [ ] Driver and transport errors are converted at the adapter boundary
- [ ] Inbound adapters map with `errors.Is`/`errors.As`, never string matching
- [ ] The default mapping is 500 with a generic message
- [ ] No panics except for unreachable programming errors

## Sources

**Books.** Neither DDD text covers this: both assume a language with exceptions.
The rules here come from Go's own sources, applied to the modelling distinctions
the DDD texts do make.

**Online.** Every link below was reachable when this page was written.

- [Why does Go not have exceptions?](https://go.dev/doc/faq#exceptions)
  — the Go FAQ; the reasoning that voids Clean Code's "prefer exceptions to
    error codes"
- [Error handling and Go](https://go.dev/blog/error-handling-and-go)
  — the Go team
- [Errors are values](https://go.dev/blog/errors-are-values)
  — Rob Pike
- [Working with Errors in Go 1.13](https://go.dev/blog/go1.13-errors)
  — `errors.Is`, `errors.As` and `%w`, which this page's mapping rules depend on
- [Defer, Panic, and Recover](https://go.dev/blog/defer-panic-and-recover)
  — the Go team; the basis for the "when to panic" section
- [Google Go Style Decisions](https://google.github.io/styleguide/go/decisions)
  — on error strings, sentinel errors and wrapping
