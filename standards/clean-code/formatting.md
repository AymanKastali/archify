# Formatting

`gofmt` decides how code is laid out. This page covers only what it does not
decide: which file a declaration goes in, and in what order.

**Authority.** `gofmt`, which is not an opinion. Martin, _Clean Code_, ch. 5 —
one idea survives, the newspaper metaphor, and it is about file organisation
rather than layout.

## What is not up for discussion

Chapter 5 spends twenty pages on horizontal alignment, indent size, blank-line
policy, brace placement and line width. In Go, every one of those questions was
answered by a program in 2009 and the answer is not negotiable:

- **`gofmt` is run on every file.** Not "usually", not "on save if configured" —
  unformatted Go is not Go, and CI rejects it.
- **Nothing is configurable.** There is no indent-size flag, no line-width flag,
  no brace style. This is the feature. Every argument the chapter is about
  cannot be had.
- **A review never comments on formatting.** If it is committed, it is
  formatted; if it is not formatted, CI caught it before a human read it.

Three tools, in order of strictness:

| Tool | Does |
|---|---|
| `gofmt` | The language's own formatter. The floor |
| `goimports` | `gofmt`, plus adds and removes imports and groups them stdlib-first |
| `gofumpt` | `gofmt`, plus a set of stricter rules it refuses to make optional |

This standard requires `goimports` behaviour at minimum, wired through
`golangci-lint`. See [`archify:setup`](../../skills/setup/SKILL.md) for the
configuration.

**One rule survives about lines:** never manually align anything `gofmt` does
not align, and never fight it. If a struct literal looks bad formatted, the
struct is wrong, not the formatter.

## The newspaper metaphor, which does survive

Martin's surviving idea: a source file should read like a newspaper article —
headline first, then the summary, then the detail. Most important at the top,
increasing detail as you scroll.

In Go this has a specific meaning, because Go has no header file and no
enforced declaration order:

```go
// internal/contexts/ordering/internal/domain/order/order.go
package order

// 1. The package's reason to exist.
//    (Here, or in doc.go when the package has many files.)

// 2. The central type.
type Order struct { ... }

// 3. Construction.
func New(id OrderID, c CustomerID) (*Order, error) { ... }
func Rehydrate(...) (*Order, error) { ... }

// 4. Behaviour, in the order the business performs it.
func (o *Order) AddLine(l Line) error { ... }
func (o *Order) Place(now time.Time) error { ... }
func (o *Order) Cancel(now time.Time, r Reason) error { ... }

// 5. Queries.
func (o *Order) ID() OrderID    { ... }
func (o *Order) Total() Money   { ... }
func (o *Order) IsPlaced() bool { ... }

// 6. Events.
func (o *Order) ReleaseEvents() []any { ... }

// 7. Unexported helpers, last, in the order they are first called.
func (o *Order) recompute() Money { ... }
```

The rules underneath it:

1. **Exported before unexported.**
2. **A type, then its constructor, then its methods** — not methods for three
   types interleaved.
3. **Callers above callees.** A helper appears below its first use, so the file
   reads downward at decreasing levels of abstraction. This is Martin's
   stepdown rule and it is the one piece of ch. 5 worth keeping.
4. **Business order over alphabetical.** `AddLine`, `Place`, `Cancel` is the
   order a reader needs. Alphabetical is the order a machine needs and no
   machine is reading this.

## File layout inside a package

`gofmt` has no opinion about which file anything lives in, and this is where
Go codebases actually go wrong. One aggregate package, one file per concept:

```text
internal/contexts/ordering/internal/domain/order/
    doc.go           package comment, when order.go would be crowded
    order.go         the Order aggregate: type, construction, behaviour
    line.go          the OrderLine entity
    id.go            OrderID
    money.go         Money, Currency
    quantity.go      Quantity
    status.go        Status — the closed set
    events.go        OrderPlaced, OrderCancelled
    errors.go        every sentinel and error type in the package
    repository.go    the Repository interface
    order_test.go    tests for order.go
    money_test.go    tests for money.go
```

- **A file is named for the concept it holds**, not for its kind. `status.go`,
  not `types.go`; `errors.go` is the one permitted kind-named file, because the
  errors of a package genuinely are one concept — see
  [`ddd/errors.md`](../ddd/errors.md) rule 1.
- **Never `models.go`, `types.go`, `utils.go`, `helpers.go`, `common.go`.** They
  are the file-level version of the package names banned in
  [naming](./naming.md), and they attract everything.
- **`x_test.go` sits beside `x.go`.** A package with one 2,000-line
  `order_test.go` covering nine files is untraceable.
- **Length is not a rule, but it is a signal.** A file past about 500 lines
  usually holds two concepts. Split it by concept, never at an arbitrary line.

## Imports

`goimports` groups them; the grouping is standard library, then everything else.
Where a project separates its own module into a third group, that is a project
convention and belongs in its `.golangci.yml`, not in an argument.

Two rules the tool cannot enforce:

- **No import aliases except to resolve a genuine collision**, or to rename a
  package whose name is misleading. An alias on every import hides the
  dependency graph from the reader.
- **A blank import (`_`) carries a comment** saying why. `_ "github.com/lib/pq"`
  without one is indistinguishable from a mistake.

The import block is also the fastest review this standard has: the imports of a
file in `domain` are checkable against [`structure.md`](../structure.md) in two
seconds, which is why "direction" is pass 1 in
[`archify:review-passes`](../../skills/review-passes/SKILL.md).

## Vertical density

The one layout judgement `gofmt` leaves open is blank lines inside a body, and
it matters more than it looks:

```go
// Wrong. Nothing is grouped, so nothing stands out.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd Command) error {
	id, err := order.NewOrderID(cmd.OrderID)
	if err != nil {
		return err
	}
	o, err := uc.orders.ByID(ctx, id)
	if err != nil {
		return err
	}
	if err := o.Place(uc.clock.Now()); err != nil {
		return err
	}
	if err := uc.orders.Save(ctx, o); err != nil {
		return err
	}
	return uc.publisher.Publish(ctx, o.ReleaseEvents()...)
}
```

```go
// Correct. One blank line per step, so the five steps are visible before any
// of them is read.
func (uc *PlaceOrder) Handle(ctx context.Context, cmd Command) error {
	id, err := order.NewOrderID(cmd.OrderID)
	if err != nil {
		return err
	}

	o, err := uc.orders.ByID(ctx, id)
	if err != nil {
		return err
	}

	if err := o.Place(uc.clock.Now()); err != nil {
		return err
	}

	if err := uc.orders.Save(ctx, o); err != nil {
		return err
	}

	return uc.publisher.Publish(ctx, o.ReleaseEvents()...)
}
```

A blank line separates **steps**. Lines that belong to one step — a call and its
error check — stay together. That is the whole rule.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Unformatted code committed | CI failure, and a diff full of noise on the next edit |
| A formatting comment in review | Spends review attention on the one thing a tool already decided |
| `types.go`, `models.go`, `utils.go` | Attracts unrelated code until it is the package |
| One test file for nine source files | Nobody can find the test for a change |
| Methods for three types interleaved | The file has no subject |
| Alphabetical method order | Reading order stops matching business order |
| Helper above its caller | The file reads bottom-up |
| Aliased imports throughout | The dependency graph is hidden from the reader |
| Blank line between a call and its error check | The step is visually split in half |
| Manual alignment | `gofmt` undoes it on the next save; the diff is noise |

## Checklist

- [ ] `gofmt`/`goimports` clean, enforced in CI
- [ ] No file named for a kind, except `errors.go` and `doc.go`
- [ ] One concept per file; test file beside its source file
- [ ] Exported before unexported; type, constructor, methods, queries, helpers
- [ ] Helpers below their first caller
- [ ] Methods in business order, not alphabetical
- [ ] Imports unaliased unless resolving a collision; blank imports commented
- [ ] Blank lines separate steps, not calls from their error checks

## Sources

**Books.** Martin, _Clean Code_, ch. 5 — "Formatting", for the newspaper
metaphor and the stepdown rule, which are the two pieces that survive. Its
horizontal-formatting, alignment and line-width sections are void in Go.

**Online.** Every link below was reachable when this page was written.

- [gofmt](https://go.dev/blog/gofmt) — the Go team on why the formatter has no
  options, and what that bought the language
- [Effective Go: formatting](https://go.dev/doc/effective_go#formatting) — the
  short section that ends the argument
- [gofumpt](https://github.com/mvdan/gofumpt) — the stricter formatter, and its
  list of rules `gofmt` leaves optional
- [golangci-lint](https://golangci-lint.run/) — the runner this standard
  configures in `archify:setup`, including the formatter linters
- [Google Go Style Decisions](https://google.github.io/styleguide/go/decisions)
  — import grouping, import aliasing and blank imports
