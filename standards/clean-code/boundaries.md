# Boundaries

How this codebase depends on code it does not own.

**Authority.** Martin, _Clean Code_, ch. 8 — "Boundaries", which binds in full.
Alistair Cockburn, [Hexagonal
Architecture](https://alistair.cockburn.us/hexagonal-architecture/), which is
the same argument with a diagram.

## The split

Three pages touch boundaries and they do not overlap:

| Question | Page |
|---|---|
| Which region may import what, and where an adapter lives | [`structure.md`](../structure.md) |
| How **another bounded context's** model is kept out of this one | [`ddd/context-mapping.md`](../ddd/context-mapping.md) |
| How **third-party code** — a library, an SDK, a vendor API — is kept out of this one | **this page** |

The mechanism is the same in all three: an interface you own, an adapter you
write, and a translation at the edge. The reasons differ, and the reason on this
page is the one Martin gives: **you do not control that code, and you will be
holding it when it changes.**

## Why it exists

Chapter 8's example is `java.util.Map`: passed around a system raw, its
`clear()` method visible to every holder, and its generic signature rippling
through a hundred files when the library changes. The Go version is the same
failure with different type names:

```go
// Wrong. `application` now imports a driver, a message broker client and a
// vendor SDK. The dependency rule is broken in the second-innermost region,
// and this use case cannot be tested without three network services.
package command

import (
	"github.com/jackc/pgx/v5"
	"github.com/segmentio/kafka-go"
	"github.com/stripe/stripe-go/v76"
)

type PlaceOrder struct {
	tx     *pgx.Tx
	writer *kafka.Writer
	stripe *stripe.Client
}
```

```go
// Correct. Three interfaces, named for what this use case needs, satisfied in
// `adapters` by types this package never sees.
package command

type PlaceOrder struct {
	orders    order.Repository // domain, per structure.md
	publisher Publisher
	payments  PaymentGateway
	clock     Clock
}

type Publisher interface {
	Publish(ctx context.Context, events ...any) error
}

type PaymentGateway interface {
	Authorise(ctx context.Context, id order.OrderID, amount order.Money) (AuthCode, error)
}

type Clock interface{ Now() time.Time }
```

The second version compiles without any of the three dependencies present, is
testable with three fakes, and survives replacing Stripe with Adyen as an edit
to one file in `adapters/outbound`.

## The rules

1. **A third-party type never appears in `domain` or `application`** — not in a
   field, not in a signature, not in a struct tag, not as an error that escapes.
   This is the region table in [`structure.md`](../structure.md), stated for
   dependencies specifically, and `depguard` enforces it.
2. **You define the interface, in your vocabulary, sized to your need.** Not the
   library's interface, not a mirror of its surface. A payment SDK with 90
   methods is consumed through a port with two.
3. **Translation happens in the adapter.** Library types in, your value objects
   out. Library errors in, your errors out — see
   [error handling](./error-handling.md) rule 7.
4. **Write a learning test before you depend on behaviour.** Not to test the
   library — to record what you believe about it, so that an upgrade tells you
   when the belief stops being true. See below.
5. **Define the interface you wish you had for code that does not exist yet.**
   A vendor API that ships next quarter is not a blocker: write the port, write
   a fake, build everything behind it, and write one adapter when the API
   arrives.
6. **Do not wrap the standard library** — with four named exceptions, below.
   `context`, `time.Time` as a value, `io.Reader`, `error`, `net/url` are part
   of the language's vocabulary, and wrapping them adds a layer that translates
   nothing.
7. **Generated code lives in `adapters` and is never hand-edited.** sqlc output,
   protobuf stubs, OpenAPI clients, mocks. If it must be changed, change the
   generator's input.
8. **A framework never reaches past `adapters` and `composition`.** A library is
   called by your code; a framework calls your code. The second kind wants to
   own `main`, the request type, the transaction and often the struct tags —
   give it `adapters` and nothing more.
9. **`domain` does not log.** A logger is a third-party dependency with a global
   habit. Errors carry information outward; the adapter that handles them logs
   once — see [error handling](./error-handling.md) rule 2.

## The four standard-library wraps

Rule 6 says do not wrap the standard library. These four are wrapped anyway,
because each is a hidden input rather than a utility, and a hidden input cannot
be tested:

| Wrapped | Port | Why |
|---|---|---|
| `time.Now()` | `Clock` in `application` | A test cannot control it; an aggregate calling it is untestable and non-deterministic |
| `rand`, UUID generation | `IDs` in `application` | Same reason; and a generated identifier is usually a domain concept |
| `os.Getenv` | Config loaded in `composition` | Configuration is read once, at startup, and passed as values |
| `net/http` **as a client** | A named outbound port | It is an outbound service; the port is named for the service, not the protocol |

`net/http` as a *server* is not wrapped. It is the inbound adapter, and it is
already at the edge.

`time.Time` itself is passed freely as a value — it is a value object in all but
name. What is banned is *reading the clock* inside the model. See
[`ddd/aggregates.md`](../ddd/aggregates.md), which requires `now` to be a
parameter.

## Learning tests

Martin's best idea in this chapter, and the one most often skipped.

A learning test is a test **of the third-party library**, in your repository,
asserting the behaviour you are about to depend on. It is not there to verify
their code — it is there to fail loudly at the moment an upgrade changes an
assumption you built on.

```go
// internal/contexts/ordering/internal/adapters/outbound/postgres/learning_test.go
//
// Learning tests: what this codebase believes about pgx and about Postgres
// isolation. Not a test of the driver — a record of the assumptions the
// OrderRepository is built on. If one of these fails after an upgrade, the
// repository is wrong, not the test.

func TestPgx_ScanNullTimestampIntoZeroTime(t *testing.T) {
	// The repository relies on a NULL cancelled_at scanning into the zero
	// Time rather than erroring, so Order.Rehydrate can treat it as "never".
	...
}

func TestPostgres_RepeatableReadRejectsConcurrentUpdate(t *testing.T) {
	// Optimistic concurrency in Save depends on this, and on the SQLSTATE
	// value being 40001. If either changes, ErrConcurrentModification stops
	// being returned and lost updates start.
	...
}
```

Write one whenever you find yourself saying "I checked, and it does X". That
sentence is the test.

## Code that does not exist yet

```go
// The vendor's API ships next quarter. Nothing waits for it.

// application/command/place_order.go — the interface you wish you had, in your
// words, in the file of the only use case that calls it.
type CarrierRates interface {
	Quote(ctx context.Context, from, to Address, w Weight) (order.Money, error)
}

// adapters/outbound/carrier/fake.go — the whole feature is built against this.
type FixedRates struct{ rate order.Money }

func (f FixedRates) Quote(context.Context, Address, Address, Weight) (order.Money, error) {
	return f.rate, nil
}

// adapters/outbound/carrier/acme.go — arrives in Q3, and is the only new file.
type ACME struct{ client *acmesdk.Client }

func (a ACME) Quote(ctx context.Context, from, to Address, w Weight) (order.Money, error) {
	// translate our values in, their response out, their errors into ours
}
```

This is Martin's `FakeTransmitter` argument, and it is also the honest answer to
`/codebase-design`'s "one adapter means a hypothetical seam": here there are two
adapters on day one, and the seam was never hypothetical. See
[`vocabulary.md`](../vocabulary.md).

## Which dependencies get wrapped

| Dependency | Wrap | Port lives in | Notes |
|---|---|---|---|
| SQL driver, ORM, query builder | **Yes** | `domain` — the `Repository` | Per [`structure.md`](../structure.md); the only port in `domain` |
| Message broker client | **Yes** | `application` | `Publisher`, `Consumer` |
| Payment, email, SMS, vendor SDK | **Yes** | `application` | Named for the capability, not the vendor |
| Another bounded context | **Yes**, plus an ACL | `application` | [context mapping](../ddd/context-mapping.md) is the specific rule |
| Cache | **Yes** | `application` | And it is not a repository |
| Clock, IDs, config, outbound HTTP | **Yes** | `application` | The four above |
| Logger, metrics, tracing | **At the edge only** | — | Never reaches `domain`; `platform` owns the setup |
| Decimal, money, currency libraries | **Yes** — as a value object | `domain` | The library is an implementation detail of `Money` |
| JSON, encoding, compression | **No** | — | Used inside adapters, never crosses inward |
| `context`, `io`, `errors`, `time` | **No** | — | Language vocabulary |
| Test assertion libraries | **No** | — | Tests are not the model |

## Wrong, and why

```go
// Wrong. The port is a mirror of the SDK: it has the vendor's method names,
// takes the vendor's types, and returns the vendor's errors. It is an import
// statement wearing an interface.
type StripeClient interface {
	NewPaymentIntent(params *stripe.PaymentIntentParams) (*stripe.PaymentIntent, error)
	ConfirmPaymentIntent(id string, p *stripe.PaymentIntentConfirmParams) (*stripe.PaymentIntent, error)
}
```

Three failures at once: `application` imports `stripe` to name the types, the
fake must construct vendor structs, and swapping vendor means rewriting every
caller. The interface is not a boundary — a boundary is the thing that stops
types crossing, and these cross.

```go
// Correct. Your words, your types, your errors. `stripe` is imported in exactly
// one file, in adapters/outbound.
type PaymentGateway interface {
	Authorise(ctx context.Context, id order.OrderID, amount order.Money) (AuthCode, error)
	Capture(ctx context.Context, code AuthCode) error
}

var ErrPaymentDeclined = errors.New("payment declined")
```

The test for any port: **could a second, completely different vendor satisfy it
without changing the interface?** If not, it is the vendor's interface with your
name on it.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Vendor type in an `application` signature | Dependency rule broken; the use case cannot be tested |
| Port mirrors the SDK's methods | The boundary stops nothing; swapping vendor rewrites callers |
| Driver error escaping an adapter | `sql.ErrNoRows` reaches an HTTP handler; see [`ddd/errors.md`](../ddd/errors.md) |
| Wrapping `io.Reader` or `context` | A layer that translates nothing |
| `time.Now()` inside the model | Untestable, non-deterministic, and invisible in the signature |
| Hand-edited generated code | Lost on the next generation, silently |
| A framework's struct tags on domain types | Persistence and transport in the model at once |
| Logger passed into `domain` | A global side effect inside the one region that must be pure |
| No learning test on relied-upon behaviour | An upgrade changes a guarantee and nothing fails until production |
| One `Infra` interface holding everything | Every test fakes ten methods to exercise one |

## Checklist

- [ ] No third-party import in `domain` or `application`
- [ ] Every external dependency is reached through a port you named
- [ ] Each port could be satisfied by a different vendor unchanged
- [ ] Library types and errors are translated in the adapter
- [ ] Clock, IDs, config and outbound HTTP are ports, not direct calls
- [ ] Behaviour you rely on is covered by a learning test
- [ ] Code that does not exist yet has a port and a fake
- [ ] Generated code is in `adapters` and unedited
- [ ] No framework type reaches past `adapters`
- [ ] Nothing in `domain` logs

## Sources

**Books.** Martin, _Clean Code_, ch. 8 — "Boundaries", for learning tests, for
"define the interface you wish you had", and for the argument against passing a
third-party type through a system. Vernon, _Implementing Domain-Driven Design_,
ch. 4, for the same boundary expressed as ports and adapters inside a DDD
codebase. Evans, ch. 14, for the anti-corruption layer, which is this pattern
applied to another team's model rather than to a library.

**Online.** Every link below was reachable when this page was written.

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
  — Cockburn's own page; the origin of `port` and `adapter`
- [Hexagonal Architecture explained](https://jmgarridopaz.github.io/content/hexagonalarchitecture.html)
  — Garrido de Paz, written with Cockburn's involvement; the clearest statement
  of what a port is and why it is sized by the caller's need
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the
  interfaces section: define the interface where it is used, not where it is
  implemented
- [Google Go Style: best practices](https://google.github.io/styleguide/go/best-practices)
  — on test doubles, injecting dependencies, and keeping global state out of
  packages
- [Errors are values](https://go.dev/blog/errors-are-values) — the model that
  makes translating an error at a boundary an ordinary operation
