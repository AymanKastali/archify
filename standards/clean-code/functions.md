# Functions

What a function is allowed to do, how many things it does, and the rule from
_Clean Code_ that this standard refuses.

**Authority.** Martin, _Clean Code_, ch. 3 — for "do one thing", command–query
separation and the argument against flag arguments, all of which bind. Its size
rules do not bind; [Effective Go](https://go.dev/doc/effective_go) and the
[Google Go Style Guide](https://google.github.io/styleguide/go/best-practices)
replace them.

## Why it exists

Chapter 3 opens with a rule that has done more damage in Go than any other
sentence in the book:

> Functions should hardly ever be 20 lines long.

And, two paragraphs later, that they should be "rarely" more than four.

That is a reasonable heuristic for Java, where a line is usually one operation
and control flow is implicit in exception propagation. In Go it is wrong,
because Go's explicit error handling costs three lines per fallible call and
those three lines add **no abstraction whatsoever**:

```go
// Six operations, twenty-one lines, and exactly one thing done: place an order.
// Extracting any of this into a named helper would make it longer and worse.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd PlaceOrderCommand) error {
	id, err := order.NewOrderID(cmd.OrderID)
	if err != nil {
		return fmt.Errorf("place order: %w", err)
	}

	o, err := uc.orders.ByID(ctx, id)
	if err != nil {
		return fmt.Errorf("place order %s: %w", id, err)
	}

	if err := o.Place(uc.clock.Now()); err != nil {
		return fmt.Errorf("place order %s: %w", id, err)
	}

	if err := uc.orders.Save(ctx, o); err != nil {
		return fmt.Errorf("place order %s: %w", id, err)
	}

	return uc.publisher.Publish(ctx, o.ReleaseEvents()...)
}
```

Count the *concepts*, not the lines: parse the id, load, apply the rule, save,
publish. Five, in sequence, at one level of abstraction. That is a clean
function by Martin's own definition, and it violates his own line count by a
factor of five.

**So the count is dropped and the definition is kept.** Measure a function by
how many things it does and at how many levels of abstraction, never by `wc
-l`. A reviewer who reports "this function is 30 lines" has reported nothing.

## The rules

1. **A function does one thing.** The test is not length. It is whether you can
   describe what it does in one sentence with no "and" in it, and whether you
   can extract a meaningful named function from the middle of it. If you can,
   it was doing two things.
2. **One level of abstraction per function.** A function that opens a database
   connection and also decides a pricing rule is mixing levels. This is the rule
   that makes the dependency rule visible inside a single body.
3. **No line limit.** Not four, not twenty, not fifty. Error handling, struct
   literals, table definitions and switch bodies are all long by construction
   and cost nothing to read.
4. **Arguments: zero is best, three is normal, five is a signal.** Not a limit —
   a signal. Past three, ask whether several of them are one missing value
   object, per [value objects](../ddd/value-objects.md). Martin's "more than
   three requires very special justification" is sound reasoning applied to a
   language without value semantics; in Go the remedy is usually a new type, not
   a builder.
5. **No boolean arguments.** `Ship(o, true)` cannot be read at the call site. A
   flag argument is a function doing two things with a switch in the signature;
   write two functions, or take a named option type.
6. **The name states everything the function does.** A function named
   `Validate` that also persists is a lie, and a lie in a name is worse than a
   vague name because the reader stops looking.
7. **Command–query separation.** A function either changes state or answers a
   question. `o.Place(now)` changes and returns only an error; `o.Total()`
   answers and changes nothing. One exception, idiomatic in Go: the
   comma-ok/`Pop`-style function that removes and returns, where both halves are
   the single operation.
8. **No surprise side effects.** A query does not lazily initialise, write a
   log at error level, or emit an event. In `domain` this is absolute: a method
   that reads must be safe to call twice.
9. **`error` is the last return value, and it is checked.** Never `(error, T)`,
   never a discarded error, never a named `err` returned bare from a long
   function where the reader cannot see what set it.
10. **Fail fast and return early.** Guard clauses at the top, happy path
    unindented at the bottom. Go's convention is that the body of an `if` is the
    exceptional case and the function's main line never drifts right.
11. **A function is exported only if something outside the package calls it.**
    Export is API surface, and API surface is the thing this standard most wants
    small — see [types and packages](./types-and-packages.md).

## In Go

### Early return, not nesting

```go
// Wrong. The happy path is four levels in, and the reader must hold three
// conditions in their head to find it.
func (uc *ShipOrder) Handle(ctx context.Context, cmd ShipCommand) error {
	o, err := uc.orders.ByID(ctx, cmd.ID)
	if err == nil {
		if o.IsPlaced() {
			if !o.IsShipped() {
				return uc.ship(ctx, o)
			} else {
				return ErrAlreadyShipped
			}
		} else {
			return ErrNotPlaced
		}
	}
	return err
}
```

```go
// Correct. Every exceptional case leaves immediately; the last line is the
// point of the function and it is at the leftmost indent.
func (uc *ShipOrder) Handle(ctx context.Context, cmd ShipCommand) error {
	o, err := uc.orders.ByID(ctx, cmd.ID)
	if err != nil {
		return err
	}
	if !o.IsPlaced() {
		return ErrNotPlaced
	}
	if o.IsShipped() {
		return ErrAlreadyShipped
	}
	return uc.ship(ctx, o)
}
```

Both are the same logic. The second is readable because Go's convention —
"[line of sight](https://google.github.io/styleguide/go/best-practices)", in the
Google guide's words — keeps the success path on one column.

### Flag arguments

```go
// Wrong. Nothing at the call site says what `true` means.
func (uc *CancelOrder) Handle(ctx context.Context, id order.OrderID, refund bool) error

uc.Handle(ctx, id, true)   // true what?
```

```go
// Correct, option A: two use cases, because they are two use cases. The
// business has two words for this and the code now has two as well.
func (uc *CancelOrder) Handle(ctx context.Context, id order.OrderID) error
func (uc *CancelOrderWithRefund) Handle(ctx context.Context, id order.OrderID) error
```

```go
// Correct, option B: when the flag is genuinely a parameter of one operation,
// it is a named value, not a bare bool.
type RefundPolicy struct{ name string }

var (
	RefundImmediately = RefundPolicy{"immediately"}
	RefundOnReturn    = RefundPolicy{"on-return"}
)

func (uc *CancelOrder) Handle(ctx context.Context, id order.OrderID, p RefundPolicy) error

uc.Handle(ctx, id, RefundImmediately)   // reads
```

### Too many arguments are a missing type

```go
// Wrong. Six parameters, four of them transposable at the call site without
// a compile error.
func Quote(sku string, qty int, unit int64, currency string, country string, vip bool) (int64, error)
```

```go
// Correct. The parameters were three concepts wearing six primitives.
func Quote(l order.Line, dest Address, c Customer) (order.Money, error)
```

This is Fowler's **Data Clump** smell and Martin's argument-count rule arriving
at the same place, and in this standard both defer to
[value objects](../ddd/value-objects.md), which is the more specific rule.

### Command–query separation

```go
// Wrong. Reads like a question, mutates, and the caller cannot tell.
func (o *Order) Total() Money {
	if o.total.IsZero() {
		o.total = o.recompute() // a query wrote to the aggregate
	}
	return o.total
}
```

```go
// Correct. The query is total and pure; recomputation happens where state
// legitimately changes.
func (o *Order) Total() Money { return o.total }

func (o *Order) AddLine(l Line) error {
	if o.status != StatusDraft {
		return ErrOrderNotDraft
	}
	o.lines = append(o.lines, l)
	o.total = o.recompute()
	return nil
}
```

The wrong version is also a data race waiting to happen, and it is the reason
rule 8 is absolute inside `domain`.

### When extraction is wrong

Extraction has a cost this standard takes seriously: a named helper is a new
concept in the package's vocabulary, and a helper whose name is not a domain
word makes the package harder to read, not easier.

```go
// Wrong. Three helpers whose names carry no meaning, invented purely to get
// the parent under a line count.
func (o *Order) Place(now time.Time) error {
	if err := o.checkStuff(); err != nil {
		return err
	}
	o.doTheThing(now)
	return o.finishUp()
}
```

If the extracted function cannot be given a name the business would recognise,
or a name that states a genuine sub-operation, **leave the code inline**. A
straight-line function of forty lines that reads top to bottom is better than
four functions that require jumping around a file to reconstruct one sentence.

The legitimate reasons to extract, and there are only four:

1. The fragment is a **named domain concept** — a rule, a policy, a calculation.
   Then it is often a [domain service](../ddd/domain-services.md) or a
   [specification](../ddd/specifications.md), not a private helper.
2. The fragment is **used in more than one place**.
3. The fragment is at a **different level of abstraction** from its
   surroundings — rule 2.
4. The fragment needs to be **tested in isolation** and cannot be reached
   through the public behaviour.

"It made the function shorter" is not on the list.

## Methods, functions and receivers

- **A free function** when there is no state: `money.Sum(ms ...Money) Money`.
- **A method** when there is state, or when a type must satisfy an interface.
- **A pointer receiver** when the method mutates, or the struct is large, or any
  method on the type has a pointer receiver. Never mix receiver kinds on one
  type.
- **A value receiver** for value objects, which never mutate — see
  [value objects](../ddd/value-objects.md).
- **No method on a type purely to group functions.** A struct with no fields and
  five methods is a namespace, and Go already has one: the package.

## Common mistakes

| Mistake | What it looks like | Consequence |
|---|---|---|
| Extracting to hit a line count | `checkStuff()`, `doTheThing()` | Helpers with no meaning; one sentence spread over four locations |
| Reporting length as a finding | "this function is 30 lines" | Reviews idiomatic Go as a defect; see the index page |
| Flag argument | `Ship(o, true)` | Call site unreadable; the function does two things |
| Six primitive parameters | `Quote(string, int, int64, ...)` | Transposable arguments, and a missing value object |
| Deep nesting | happy path at indent 4 | Reader reconstructs control flow instead of reading it |
| Query that mutates | `Total()` writing a cache field | Non-idempotent reads, races, surprising diffs |
| `error` not last | `func f() (error, Order)` | Breaks every Go reader's expectation |
| Ignored error | `_ = repo.Save(ctx, o)` | The one failure that mattered is invisible |
| Naked return in a long function | `return` with named results | The reader cannot see what is being returned |
| Function that lies | `Validate()` that also writes | The name is load-bearing and it is false |

## Checklist

- [ ] Each function does one thing, stated in one sentence with no "and"
- [ ] One level of abstraction per body
- [ ] No function was split to satisfy a line count
- [ ] No boolean parameters
- [ ] More than three parameters was checked for a missing value object
- [ ] Guard clauses first; the happy path is unindented
- [ ] Queries are pure; commands return only `error`
- [ ] `error` is the last return and every one is handled
- [ ] Every extraction has a name a reader recognises

## Sources

**Books.** Martin, _Clean Code_, ch. 3 — "Functions", for "do one thing", one
level of abstraction, command–query separation and flag arguments. Its size
rules are the ones this page rejects, for the reason given at the top. Fowler,
_Refactoring_ (2nd ed.), ch. 3 for Long Parameter List and Data Clump, and ch. 6
for Extract Function and its inverse, Inline Function — the inverse is the one
Go needs more often.

**Online.** Every link below was reachable when this page was written.

- [Google Go Style: best practices](https://google.github.io/styleguide/go/best-practices)
  — the "line of sight" rule, function argument guidance, and option patterns
- [Google Go Style: decisions](https://google.github.io/styleguide/go/decisions)
  — receiver types, when to use pointer receivers, and error return position
- [Effective Go](https://go.dev/doc/effective_go) — multiple return values,
  named results, `defer`, and why Go's error handling looks the way it does
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — indent
  error flow, naked returns, receiver type
- [Errors are values](https://go.dev/blog/errors-are-values) — Pike on why the
  repetition of `if err != nil` is not the problem it is taken for, and what to
  do in the rare case where it genuinely is
- [Practical Go](https://dave.cheney.net/practical-go/presentations/qcon-china.html)
  — Cheney on guard clauses, the happy path on the left, and why a long
  straight-line function is often the clearest available code
