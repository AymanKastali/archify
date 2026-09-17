# Error handling

_Clean Code_ chapter 7 is void in Go. This page is what replaces it everywhere
outside the model.

**Authority.** The Go sources — [Errors are
values](https://go.dev/blog/errors-are-values), [Working with
Errors](https://go.dev/blog/go1.13-errors), [Effective
Go](https://go.dev/doc/effective_go#errors) — and nothing else. Martin,
_Clean Code_, ch. 7, is cited only to record what is rejected.

## The split with the model

[`ddd/errors.md`](../ddd/errors.md) is the authority on **domain** errors: where
a sentinel is declared, when a type is needed instead, how infrastructure errors
are kept out of `domain`, and how an inbound adapter maps a broken rule onto its
protocol. **Those rules are not restated here.**

This page covers the rest of the program: `application`, `adapters`,
`composition`, `platform`, and the mechanics of error values everywhere. When
both apply, `ddd/errors.md` is the more specific rule and the finding cites it.

## Why chapter 7 is void

Martin's chapter is built on a language feature Go does not have. Its section
headings are the argument:

> Use Exceptions Rather Than Return Codes.
> Write Your `Try-Catch-Finally` Statement First.
> Use Unchecked Exceptions.
> Don't Return Null. Don't Pass Null.

Go has no exceptions. `panic` is not one: it unwinds without a type-based
handler, it is not part of any function's signature, and recovering from it
across a package boundary is undefined behaviour as far as this standard is
concerned. **Using `panic`/`recover` as exception handling is a finding, not a
style preference.**

What survives the crossing is the one idea underneath the chapter — **a failure
must carry enough information for the caller to act on it, and must not be
silently discarded** — and Go achieves that with values rather than with
control flow.

The replacement for "don't return null" is on this page too, and it is not a
null-object wrapper. It is [usable zero values](#nil-and-the-zero-value).

## The rules

1. **An error is a value, returned last, and handled at the call site.** Never
   `(error, T)`. Never a discarded error. `_ = doThing()` requires a comment
   saying why the failure cannot matter.
2. **Handle it or return it — never both.** Logging an error and returning it
   produces the same failure in the log three times, from three layers, and the
   reader cannot tell whether it was handled. **Log where it is handled, which
   is once, at the outermost caller that makes a decision.**
3. **Wrap with `%w` and add what the caller does not already know.** The
   identifier, the operation. Never the function's own name — a stack of
   `"placeOrder: handle: doPlace: ..."` is a stack trace written by hand, badly.
4. **Never match on message text.** `errors.Is` for sentinels, `errors.As` for
   types. This is rule 6 of [`ddd/errors.md`](../ddd/errors.md) and it applies
   to every error in the program, not only domain ones.
5. **Error strings are lowercase and unpunctuated.** `"connect to postgres"`,
   not `"Failed to connect to Postgres!"`. They are fragments, because they get
   embedded in other error strings.
6. **No "failed to".** Every error is a failure; the words carry nothing and
   they compound: `"failed to place order: failed to save: failed to exec"`.
7. **Wrapping is API.** `%w` makes the wrapped error visible to every caller
   forever, so a driver error wrapped with `%w` at an adapter boundary has just
   published `*pq.Error` as part of your contract. Across a region boundary,
   translate instead: wrap with `%v`, or return a domain error. See
   [`structure.md`](../structure.md).
8. **`panic` only for a programming error that no input can produce**, and never
   across a package boundary. `recover` exists in exactly two places: a
   top-level HTTP or consumer middleware that converts a crash into a 500, and a
   goroutine supervisor that must not take the process down.
9. **Cancellation is not a failure.** `context.Canceled` and
   `context.DeadlineExceeded` are checked for and handled distinctly — logged at
   debug, not error, and never reported to a user as a fault.
10. **A deferred `Close` on a writable resource has its error checked.** On a
    read-only one it may be discarded, with `defer func() { _ = f.Close() }()`
    so the discard is visible.
11. **Sentinels are compared, not constructed at the call site.** An
    `errors.New` inside a function body produces a distinct value on every call
    and nothing downstream can match it.
12. **Errors are documented.** A function returning a matchable error says so in
    its doc comment — see [comments](./comments.md) rule 5.

## In Go

### Wrapping: what to add and where

```go
// Wrong. Four layers, each adding its own name, none adding information. The
// log line is 200 characters and says "an order failed" four times.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd Command) error {
	if err := uc.place(ctx, cmd); err != nil {
		return fmt.Errorf("PlaceOrder.Handle: failed to handle: %w", err)
	}
	return nil
}
```

```go
// Correct. One wrap per boundary, carrying the identifier the log reader needs
// and nothing that the function name already tells them.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd Command) error {
	id, err := order.NewOrderID(cmd.OrderID)
	if err != nil {
		return fmt.Errorf("place order: %w", err)
	}

	o, err := uc.orders.ByID(ctx, id)
	if err != nil {
		return fmt.Errorf("place order %s: %w", id, err)
	}
	...
}
```

The test for a wrap: **does it add a fact the caller could not have known?** An
identifier qualifies. A row count qualifies. The name of the function you are
standing in does not.

### Wrapping is API — the boundary translation

```go
// Wrong. `%w` has published lib/pq's error type to every caller of the
// application service, and to every caller of theirs. Changing driver is now a
// breaking change to the domain.
func (r *OrderRepository) Save(ctx context.Context, o *order.Order) error {
	if _, err := r.db.ExecContext(ctx, q, args...); err != nil {
		return fmt.Errorf("save order: %w", err)
	}
	return nil
}
```

```go
// Correct. The driver's error is translated at the adapter boundary. Where it
// carries domain meaning it becomes a domain error; otherwise it is wrapped
// opaquely with %v, which keeps the message and drops the type.
func (r *OrderRepository) Save(ctx context.Context, o *order.Order) error {
	res, err := r.db.ExecContext(ctx, q, args...)
	if err != nil {
		return fmt.Errorf("save order %s: %v", o.ID(), err)
	}

	n, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("save order %s: %v", o.ID(), err)
	}
	if n == 0 {
		// A domain outcome, not a driver outcome: someone else wrote first.
		return fmt.Errorf("save order %s: %w", o.ID(), order.ErrConcurrentModification)
	}
	return nil
}
```

Two different verbs in one function, deliberately. `%w` for the error the caller
is expected to match on; `%v` for the one it must never depend on.

### Handle or return, never both

```go
// Wrong. The same failure appears at three levels, and nobody can tell from the
// log whether anything was done about it.
func (r *OrderRepository) Save(ctx context.Context, o *order.Order) error {
	if err := r.exec(ctx, o); err != nil {
		log.Error("save failed", "err", err) // 1
		return err
	}
	return nil
}

func (uc *PlaceOrder) Handle(ctx context.Context, cmd Command) error {
	if err := uc.orders.Save(ctx, o); err != nil {
		log.Error("place order failed", "err", err) // 2
		return err
	}
	return nil
}

func (h *Handler) Post(w http.ResponseWriter, r *http.Request) {
	if err := h.uc.Handle(r.Context(), cmd); err != nil {
		log.Error("request failed", "err", err) // 3
		http.Error(w, "internal error", 500)
	}
}
```

```go
// Correct. The two inner layers return; the adapter that decides the outcome
// logs once, with everything the wrapping accumulated.
func (r *OrderRepository) Save(ctx context.Context, o *order.Order) error {
	if err := r.exec(ctx, o); err != nil {
		return fmt.Errorf("save order %s: %v", o.ID(), err)
	}
	return nil
}

func (h *Handler) Post(w http.ResponseWriter, r *http.Request) {
	if err := h.uc.Handle(r.Context(), cmd); err != nil {
		h.log.Error("place order", "err", err, "request_id", middleware.ID(r))
		h.respond(w, err) // maps domain errors to status, per ddd/errors.md
	}
}
```

### Cancellation

```go
// Wrong. A client that hung up is now an error-level log line and a paged
// alert, indefinitely, on every deploy that restarts the load balancer.
if err := uc.Handle(ctx, cmd); err != nil {
	h.log.Error("place order", "err", err)
}
```

```go
// Correct. Cancellation is an outcome, not a fault.
if err := uc.Handle(ctx, cmd); err != nil {
	switch {
	case errors.Is(err, context.Canceled):
		h.log.Debug("place order: client went away")
		return
	case errors.Is(err, context.DeadlineExceeded):
		h.log.Warn("place order: timed out", "err", err)
		h.respond(w, err)
		return
	default:
		h.log.Error("place order", "err", err)
		h.respond(w, err)
	}
}
```

### Multiple errors

`errors.Join` is the answer where several independent failures must all be
reported — validating a whole request, closing several resources, a fan-out
where each branch may fail. `errors.Is` and `errors.As` see through a join, so
the caller can still match.

```go
func (c Command) Validate() error {
	var errs []error
	if c.OrderID == "" {
		errs = append(errs, ErrMissingOrderID)
	}
	if c.Quantity <= 0 {
		errs = append(errs, ErrInvalidQuantity)
	}
	return errors.Join(errs...) // nil when errs is empty
}
```

What this is **not** for: accumulating errors down a call chain to report at the
end. That is exception-style flow in a different costume, and the caller gets a
pile it cannot act on.

### Panic and recover

```go
// The only legitimate recover in an application: the process edge.
func Recoverer(log *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if v := recover(); v != nil {
					log.Error("panic", "value", v, "stack", string(debug.Stack()))
					http.Error(w, "internal error", http.StatusInternalServerError)
				}
			}()
			next.ServeHTTP(w, r)
		})
	}
}
```

Never `recover` inside a package to convert a panic into an error return. It
hides a bug, it catches panics from code you did not write, and it makes the
function's contract a lie.

### `nil` and the zero value

Martin's "don't return null, don't pass null" becomes four concrete Go rules:

1. **Return a nil slice or map rather than an empty one**, and let the caller
   `range` and `len` it — both work on nil. Do not invent an empty-collection
   sentinel.
2. **Never return a nil pointer with a nil error.** A repository that finds
   nothing returns `nil, ErrOrderNotFound`, per
   [`ddd/errors.md`](../ddd/errors.md) rule 7 — not `nil, nil`, which every
   caller will eventually dereference.
3. **Never take a nil-able parameter that must not be nil.** If the function
   cannot work without it, it is a required field on a struct the caller must
   construct, and construction is where it is checked once.
4. **Never return a typed nil as an `error`.** This is Go's sharpest edge:

```go
// Wrong. `err` is a non-nil interface holding a nil *ValidationError, so
// `if err != nil` is TRUE at every call site even on success.
func validate(c Command) error {
	var err *ValidationError
	if c.Quantity <= 0 {
		err = &ValidationError{Field: "quantity"}
	}
	return err // never nil as an interface
}
```

```go
// Correct. Return the nil literal on the success path, or use the `error` type
// for the variable so there is no concrete type to smuggle.
func validate(c Command) error {
	if c.Quantity <= 0 {
		return &ValidationError{Field: "quantity"}
	}
	return nil
}
```

`go vet` catches some of these; the rule is simpler than the analysis, so
follow the rule.

## The three error strategies

Cheney's framing, and it is the decision this page most often has to make:

| Strategy | Use when | Cost |
|---|---|---|
| **Opaque** — the caller only knows it failed | Most of the program | Nothing. This is the default |
| **Sentinel** — the caller matches a known value with `errors.Is` | The caller must branch: not-found, already-exists, conflict | The sentinel is API forever |
| **Typed** — the caller extracts details with `errors.As` | The caller needs data from the failure: which field, how much short | The type and its fields are API forever |

**Start opaque.** Promote to a sentinel when a real caller needs to branch, and
to a type when a real caller needs a field. Every promotion is a permanent
addition to the package's contract, which is why
[`ddd/errors.md`](../ddd/errors.md) declares domain sentinels deliberately
rather than as they are needed.

## Common mistakes

| Mistake | Consequence |
|---|---|
| `_ = doThing()` with no comment | The one failure that mattered is invisible |
| Log and return | The same failure logged three times; nobody knows who handled it |
| `%v` where the caller must match | `errors.Is` silently returns false forever |
| `%w` on a driver error at a region boundary | The driver's type is now your public API |
| Function name in the wrap | A hand-written stack trace, at every layer |
| `"Failed to X: %w"` | Compounds into a sentence of failures |
| Message matching | Breaks on a wording change, silently |
| `recover` inside a package | Hides bugs; catches panics it does not understand |
| `panic` for invalid input | Crashes the process on a user's typo |
| Cancellation logged at error | Permanent noise; real alerts get ignored |
| `errors.New` in a function body | Nothing downstream can match it |
| Typed nil returned as `error` | `err != nil` is true on the success path |
| `nil, nil` from a lookup | Nil dereference at a call site far away |

## Checklist

- [ ] Every returned error is handled or returned, never both
- [ ] Every wrap adds a fact the caller did not have
- [ ] `%w` only where the wrapped error is intended to be matchable
- [ ] Driver, transport and framework errors are translated at the adapter edge
- [ ] No string matching anywhere
- [ ] Error strings lowercase, unpunctuated, no "failed to"
- [ ] `context.Canceled` and `DeadlineExceeded` handled distinctly
- [ ] `panic` only for unreachable programming errors; `recover` only at the edge
- [ ] Deferred `Close` on writable resources is checked
- [ ] No `nil, nil` returns, no typed nil returned as `error`
- [ ] Every matchable error is documented on the function that returns it

## Sources

**Books.** Martin, _Clean Code_, ch. 7 — "Error Handling", cited here only to
record which of its rules are rejected and why. Its one surviving idea, that an
error must carry enough for the caller to act, is the premise of this page.

**Online.** Every link below was reachable when this page was written.

- [Errors are values](https://go.dev/blog/errors-are-values) — Pike, 2015. The
  design position this page rests on
- [Working with Errors in Go 1.13](https://go.dev/blog/go1.13-errors) — the Go
  team on `%w`, `errors.Is` and `errors.As`, including the warning that wrapping
  makes the wrapped error part of your API
- [Error handling and Go](https://go.dev/blog/error-handling-and-go) — the
  original article; the `error` interface and custom error types
- [Defer, Panic, and Recover](https://go.dev/blog/defer-panic-and-recover) — what
  `panic` actually does, and why it is not an exception
- [Don't just check errors, handle them gracefully](https://dave.cheney.net/2016/04/27/dont-just-check-errors-handle-them-gracefully)
  — Cheney, the source of the opaque/sentinel/typed framing above
- [Google Go Style Decisions: errors](https://google.github.io/styleguide/go/decisions#errors)
  — error string style, error wrapping, and when to add structure
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the
  sections on error strings, indenting error flow, and handling errors
