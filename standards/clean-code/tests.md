# Tests

What a test looks like in this codebase, what may be doubled, and where the
seam is.

**Authority.** Martin, _Clean Code_, ch. 9 — F.I.R.S.T. and "keep tests clean"
bind; "one assert per test" is inverted. [Go Wiki: Table-Driven
Tests](https://go.dev/wiki/TableDrivenTests) and [Go Wiki: Test
Comments](https://go.dev/wiki/TestComments) — binding. Fowler, [Mocks Aren't
Stubs](https://martinfowler.com/articles/mocksArentStubs.html), for the
vocabulary of doubles.

## The split with the workflow

**`/tdd` owns the loop** — write the failing test, watch it fail, make it pass,
refactor, and never write production code without a red test first. That is the
process, it is not restated here, and no rule on this page changes it.

**This page owns the artefact**: what a Go test in a DDD codebase is shaped
like, which collaborators may be replaced by a double, and which may never be.
`/tdd` asks "is there a failing test?"; this page answers "is it the right
test?".

The one place they meet is slicing, and it is settled on
[`archify:writing-order`](../../skills/writing-order/SKILL.md): **the test is
written outside-in, at the application service; the implementation proceeds
inside-out, from value objects to adapters.** The slice stays vertical.

## Why it exists

Chapter 9's central claim binds without modification:

> Test code is just as important as production code … It must be kept as clean
> as production code.

The consequence people skip: a test suite that is hard to change is a brake on
the design, and the most common cause is doubles. A suite that mocks every
collaborator is pinned to the current call graph, so every refactor breaks a
hundred tests that were never about the behaviour that changed. That suite gets
deleted eventually, and the codebase it was protecting is worse than if it had
never existed.

Which is why the rules below are mostly about **what not to double**.

## The rules

1. **F.I.R.S.T.** — Fast, Independent, Repeatable, Self-validating, Timely. All
   five bind as written.
2. **Test code is production code**, with one deliberate exception: **prefer
   duplication to indirection in test setup.** A test that requires reading
   three helper functions to learn what it sets up has failed at the one thing a
   test is for.
3. **One concept per test, not one assert.** Martin's rule is a proxy for "don't
   test two behaviours in one function"; in Go the table-driven test holds many
   asserts and still tests one concept. This is the inversion.
4. **Table-driven with subtests is the default shape.** Reach for it whenever
   there is more than one case.
5. **The test name is a sentence about behaviour**, in the domain's words:
   `TestPlaceOrder_RejectsAnEmptyBasket`. Not `TestPlace1`, not
   `TestPlaceReturnsError`. See [naming](./naming.md).
6. **The domain is tested directly, with no doubles of any kind.** An aggregate
   has no collaborators it does not own — that is what makes it an aggregate.
   If a domain test needs a double, the model is wrong.
7. **The application service is the main seam.** Its test drives a use case end
   to end with fakes for its ports, and it is where most behavioural coverage
   lives.
8. **Never double your own code.** Not an aggregate, not a value object, not a
   domain service, not an application service. Only **ports** get doubles. See
   the table below.
9. **Prefer a hand-written fake to a generated mock.** A fake is a working
   implementation; a mock is an assertion about a call sequence, and a call
   sequence is not a behaviour.
10. **Outbound adapters are tested against the real technology** — a real
    Postgres, a real broker, in a container. An adapter tested against a mock of
    the driver tests nothing, because the only thing it contains is knowledge of
    the driver.
11. **Assert on observable behaviour**, through the package's public API. Never
    export an identifier so a test can reach it, and never assert on an
    unexported field from an internal test package when a method would do.
12. **Use the external test package**, `package order_test`, so tests are
    written against the API a caller has. Drop into `package order` only when
    testing something genuinely unexported, and expect that to be rare.
13. **No sleeps, no wall clock, no network in a unit test.** Time enters through
    the `Clock` port — see [boundaries](./boundaries.md).
14. **`t.Helper()` in every helper, `t.Cleanup()` for teardown,
    `t.Parallel()` where the test is independent.** These are not optional
    style; `t.Helper` is what makes a failure point at the right line.
15. **A failure message says what was expected and what happened**, with the
    input. `got %v, want %v` is the Go convention and it is enough.
16. **Coverage is a diagnostic, not a target.** A number is not the goal; an
    uncovered branch worth covering is.

## What may be doubled

This table is the standing answer. It is cited by
[`archify:writing-order`](../../skills/writing-order/SKILL.md) and by
[`archify:modelling-decisions`](../../skills/modelling-decisions/SKILL.md)
rather than restated there.

| Collaborator | Double it? | With what |
|---|---|---|
| Repository port | **Yes** | An in-memory fake — a real map-backed implementation |
| `Clock` | **Yes** | A fixed time |
| ID generator | **Yes** | A deterministic sequence |
| `Publisher` / event bus | **Yes** | A recording fake you can assert against |
| External service port (payments, carrier, mail) | **Yes** | A fake with programmable outcomes |
| Aggregate | **Never** | Construct a real one |
| Value object | **Never** | Construct a real one |
| Domain service | **Never** | Use the real one |
| Application service | **Never** | Call it; it is the thing under test |
| SQL driver / broker client | **Never** | Test the adapter against the real thing |

The pattern underneath: **a port is doubled, everything you wrote is used.** If
something you wrote is hard to use in a test, that is a design finding, not a
mocking problem.

## In Go

### The table-driven test

```go
package order_test

func TestOrder_Place(t *testing.T) {
	t.Parallel()

	at := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)

	tests := []struct {
		name    string
		order   func(t *testing.T) *order.Order
		wantErr error
	}{
		{
			name:  "places a draft order that has lines",
			order: draftWithOneLine,
		},
		{
			name:    "refuses an order with no lines",
			order:   emptyDraft,
			wantErr: order.ErrNoLines,
		},
		{
			name:    "refuses an order that is already placed",
			order:   alreadyPlaced,
			wantErr: order.ErrOrderNotDraft,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			o := tt.order(t)

			err := o.Place(at)

			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("Place() error = %v, want %v", err, tt.wantErr)
			}
			if tt.wantErr != nil {
				return
			}
			if !o.IsPlaced() {
				t.Errorf("status = %v, want placed", o.Status())
			}
			if got := o.ReleaseEvents(); len(got) != 1 {
				t.Errorf("released %d events, want 1", len(got))
			}
		})
	}
}
```

Four asserts in the success case, one concept: what `Place` does. The subtest
name is the specification, and `go test -run 'TestOrder_Place/refuses_an_order_with_no_lines'`
runs exactly one line of it.

Note what is absent: no double, no setup framework, no mock of `Line` or
`Money`. The aggregate is constructed for real, which is possible precisely
because [aggregates](../ddd/aggregates.md) forbids it from having infrastructure
collaborators.

### The in-memory fake

```go
// internal/contexts/ordering/internal/adapters/outbound/memory/orders.go
//
// Orders is a working, in-memory Repository. It is the second adapter that
// makes the repository port a real seam rather than a hypothetical one, and it
// is used by every application-service test.
package memory

type Orders struct {
	mu   sync.Mutex
	byID map[order.OrderID]*order.Order
}

func NewOrders(seed ...*order.Order) *Orders { ... }

func (o *Orders) ByID(_ context.Context, id order.OrderID) (*order.Order, error) {
	o.mu.Lock()
	defer o.mu.Unlock()

	found, ok := o.byID[id]
	if !ok {
		return nil, order.ErrOrderNotFound
	}
	return found, nil
}

func (o *Orders) Save(_ context.Context, ord *order.Order) error { ... }
```

It returns the **same** `ErrOrderNotFound` the Postgres adapter returns, because
that error is part of the port's contract, not of either implementation. A fake
that returns a different error for the same condition makes every test that
passes with it a lie.

### The application service test — the main seam

```go
package command_test

func TestPlaceOrder(t *testing.T) {
	t.Parallel()

	at := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)

	tests := []struct {
		name       string
		seed       []*order.Order
		cmd        command.PlaceOrderCommand
		wantErr    error
		wantEvents int
	}{
		{
			name:       "places a draft order",
			seed:       []*order.Order{draftWithOneLine(t)},
			cmd:        command.PlaceOrderCommand{OrderID: "ORD-1"},
			wantEvents: 1,
		},
		{
			name:    "reports an unknown order",
			cmd:     command.PlaceOrderCommand{OrderID: "ORD-9"},
			wantErr: order.ErrOrderNotFound,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			orders := memory.NewOrders(tt.seed...)
			events := &fake.Publisher{}
			uc := command.NewPlaceOrder(orders, events, fake.ClockAt(at))

			err := uc.Handle(context.Background(), tt.cmd)

			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("Handle() error = %v, want %v", err, tt.wantErr)
			}
			if got := len(events.Published); got != tt.wantEvents {
				t.Errorf("published %d events, want %d", got, tt.wantEvents)
			}
		})
	}
}
```

Three doubles, all of them ports, none of them mocks. The assertions are on
outcomes — an error, a published event — never on "was `Save` called once with
these arguments".

### The adapter test

```go
//go:build integration

package postgres_test

func TestOrderRepository_SaveAndLoad(t *testing.T) {
	db := testdb.Start(t) // a real Postgres, torn down by t.Cleanup

	repo := postgres.NewOrderRepository(db)
	want := draftWithOneLine(t)

	if err := repo.Add(context.Background(), want); err != nil {
		t.Fatalf("Add() = %v", err)
	}

	got, err := repo.ByID(context.Background(), want.ID())
	if err != nil {
		t.Fatalf("ByID() = %v", err)
	}
	if !reflect.DeepEqual(got.Total(), want.Total()) {
		t.Errorf("total = %v, want %v", got.Total(), want.Total())
	}
}
```

Behind a build tag so the fast suite stays fast, and against a real database
because the only thing this file contains is SQL and a mapping. Mocking the
driver here would test that the code calls the functions it calls.

## Mocks, fakes and the difference that matters

| Double | What it is | Used here |
|---|---|---|
| **Fake** | A working implementation, simplified — the in-memory repository | **The default** |
| **Stub** | Returns canned answers, no logic | For a port whose response you are varying |
| **Spy** | A stub that records calls, asserted on afterwards | For a `Publisher`, to count events |
| **Mock** | Pre-programmed with expected calls; fails if they do not arrive | **Avoid.** See below |
| **Dummy** | Passed to satisfy a signature, never used | Fine |

A mock asserts on **how** the code did its work. That couples the test to the
implementation, which is the one thing a test must not do — refactoring is
changing how without changing what, and a mocked suite makes every refactor red.
A generated mock framework makes this cheap to do at scale, which is why
codebases that adopt one end up with thousands of tests and no confidence.

**The one legitimate use of an interaction assertion** is when the interaction
*is* the behaviour: an event was published, a payment was captured exactly once,
an email was sent. Assert on the recorded result in a spy — `events.Published` —
not on a call expectation.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Mocking an aggregate or value object | Tests the mock; the real invariant is never exercised |
| Mocking the application service | Nothing is tested; the use case is the subject |
| Mocking the SQL driver in an adapter test | Asserts that the code calls the functions it calls |
| A fake returning a different error than the real adapter | Every test using it passes on a lie |
| `time.Now()` in a test | Flakes at midnight, at month end, in another timezone |
| `time.Sleep` to wait for a goroutine | Slow and flaky; use a channel or `t.Cleanup` with a signal |
| Exporting a field so a test can read it | The API is now shaped by the test suite |
| Helper without `t.Helper()` | Failures point into the helper, not the test |
| Tests sharing mutable state | Order-dependent, and unparallelisable |
| One test asserting three behaviours | One failure hides the other two |
| Coverage as a target | Tests written to touch lines, not to state behaviour |
| Test setup behind four helpers | The test no longer says what it is testing |

## Checklist

- [ ] Every test name is a behaviour sentence in domain words
- [ ] Multi-case tests are table-driven with named subtests
- [ ] Domain tests use real aggregates and value objects — no doubles
- [ ] Only ports are doubled, and with fakes rather than mocks
- [ ] The fake returns the same errors as the real adapter
- [ ] Application-service tests assert on outcomes, not on calls
- [ ] Adapter tests run against the real technology, behind a build tag
- [ ] Tests live in the external `_test` package unless there is a reason
- [ ] `t.Helper`, `t.Cleanup`, `t.Parallel` used correctly
- [ ] No wall clock, no sleeps, no network in the fast suite
- [ ] Failure messages report got and want

## Sources

**Books.** Martin, _Clean Code_, ch. 9 — "Unit Tests", for F.I.R.S.T. and for
the argument that test code carries the same standard as production code. Its
one-assert-per-test rule is the one inverted here. Fowler, _Refactoring_ (2nd
ed.), ch. 2, on the role of a test suite in making refactoring safe — which is
the argument against mocks stated from the other side. Gerard Meszaros, _xUnit
Test Patterns_ (Addison-Wesley, 2007, ISBN 978-0-13-149505-0), ch. 11, for the
taxonomy of doubles used above.

**Online.** Every link below was reachable when this page was written.

- [Go Wiki: Table-Driven Tests](https://go.dev/wiki/TableDrivenTests) — the
  canonical shape, from the Go project itself
- [Go Wiki: Test Comments](https://go.dev/wiki/TestComments) — the things Go
  reviewers say about tests: failure message format, helpers, table names
- [Using Subtests and Sub-benchmarks](https://go.dev/blog/subtests) — `t.Run`,
  parallel subtests, and the cleanup ordering that trips people up
- [`testing` package documentation](https://pkg.go.dev/testing) — `T.Helper`,
  `T.Cleanup`, `T.Parallel`, and the build-tag conventions
- [Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)
  — Fowler, on the difference between state and interaction verification, and
  on what each costs
- [The Little Mocker](https://blog.cleancoder.com/uncle-bob/2014/05/14/TheLittleMocker.html)
  — Martin's own taxonomy of doubles, and his position on when a mock is
  appropriate
- [Google Go Style: best practices](https://google.github.io/styleguide/go/best-practices)
  — test helpers, test doubles, and keeping tests readable
