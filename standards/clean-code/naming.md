# Naming

What every identifier in the program is called, excluding the ones the glossary
already decides.

**Authority.** Martin, _Clean Code_, ch. 2 — for the reasoning. [Effective
Go](https://go.dev/doc/effective_go#names), [Go Code Review
Comments](https://go.dev/wiki/CodeReviewComments) and the [Google Go Style
Guide](https://google.github.io/styleguide/go/decisions#naming) — for the rules,
which override Martin's wherever they differ.

## The split with the glossary

**A name that appears in `CONTEXT.md` is decided by
[ubiquitous language](../ddd/ubiquitous-language.md), and this page has nothing
to say about it.** If the business says "consignment", the type is `Consignment`
and no style rule shortens it.

This page governs everything the glossary does not reach: packages, receivers,
locals, parameters, interfaces, files, test names, error variables, and the
non-domain code in `adapters`, `application` and `platform`.

When both could apply, the glossary wins and the finding cites
`ddd/ubiquitous-language.md`.

## Why it exists

Martin's chapter 2 is right about the failure and wrong about the remedy. The
failure is real: `d`, `theList`, `ProcessData`, `OrderInfo`, `manager`. Each
forces the reader to reconstruct a meaning that the author knew and did not
write down.

His remedy is "long descriptive names are better than short ones". In Java, with
no package-qualified call sites and no convention of short receivers, that is
sound. In Go it produces this:

```go
// Wrong. Every name is longer than its scope justifies, and the noise hides
// the one thing the function actually does.
func (orderRepositoryInstance *PostgresOrderRepositoryImplementation) SaveOrderAggregate(
	contextObject context.Context,
	orderAggregateToSave *order.Order,
) error {
	for indexOfLine, orderLineItem := range orderAggregateToSave.Lines() {
		...
	}
}
```

```go
// Correct. Nothing is guessed: the package is `postgres`, the receiver is
// three characters because it is visible on one screen, and the loop variable
// is `i` because its scope is four lines.
func (r *OrderRepository) Save(ctx context.Context, o *order.Order) error {
	for i, l := range o.Lines() {
		...
	}
}
```

Both examples name the same things. The second is readable because Go supplies
half of each name from context — the package qualifier, the receiver type, the
scope — and repeating that context in the identifier is not clarity, it is
noise.

## The rules

1. **Name length is proportional to the size of the scope.** A variable live for
   three lines gets one or two characters. A package-level exported identifier
   gets a full descriptive name. This is the direct inversion of Martin's rule
   and it is the Go convention.
2. **The package qualifier is part of the name.** `order.Repository`, not
   `order.OrderRepository`. Read every exported identifier as
   `package.Identifier` before judging it. Exception below.
3. **The aggregate root and its identifier repeat the package name.**
   `order.Order`, `order.OrderID`. This is deliberate stutter — see below.
4. **A receiver is one to three letters**, the same letters for every method on
   the type, and never `this`, `self` or `me`.
5. **An interface is named for the behaviour it requires**, from the caller's
   vocabulary. One-method interfaces take the `-er` form: `Publisher`, `Clock`,
   `Notifier`. Never an `I` prefix, never an `Impl` suffix.
6. **No type in the name.** Not `orderList`, `nameString`, `countInt`,
   `userMap`. The type is in the declaration.
7. **No meaningless qualifiers.** `Data`, `Info`, `Object`, `Manager`, `Helper`,
   `Util`, `Base`, `Common`, `Service` (unqualified), `Processor`, `Handler`
   (outside inbound adapters). In `domain` these are findings on sight, per
   [anti-patterns](../ddd/anti-patterns.md).
8. **Initialisms keep one case.** `URL`, `ID`, `HTTP`, `SQL`, `API` — so
   `orderID`, `OrderID`, `httpClient`, `ServeHTTP`. Never `orderId`, `Url`,
   `HttpClient`.
9. **A getter has no `Get`.** `o.Total()`, not `o.GetTotal()`. A setter, where
   one is permitted at all — and on an aggregate it is not — keeps `Set`.
10. **Errors are `Err`-prefixed variables and `Error`-suffixed types.**
    `ErrOrderNotFound`, `InsufficientStockError`.
11. **Booleans read as assertions.** `ok`, `found`, `o.IsPlaced()`,
    `c.HasCredit()`. Never `flag`, `status bool`, `check`.
12. **One word, one meaning, across the whole codebase.** If `fetch` means "read
    from another context over the network", then nothing local is ever
    `fetchOrder`. Martin's "use one word per concept" survives the language
    change untouched.

## Packages

A package name is the most load-bearing name in Go, because it prefixes
everything the package exports.

```text
Good:   order   shipment   invoice   postgres   http   outbox   money
Bad:    models  types      utils     helpers    common  base    shared
        managers  services  handlers  impl      core    internal_stuff
```

- **Lowercase, one word, no underscores, no camelCase, singular.**
- **Named for what it provides, not what it contains.** `order` provides orders.
  `models` provides nothing — it is a filing cabinet, and every codebase that
  has one ends up with every type in it.
- **A package name plus an identifier is one phrase.** `postgres.OrderStore`
  reads. `postgres.PostgresOrderStore` does not.
- **Never a plural, and never a generic grouping noun.** The aggregate package
  is `order`, holding `Order`, `OrderLine`, `OrderID`, `Status`, `Repository`
  and the aggregate's errors. See
  [aggregates](../ddd/aggregates.md) for why the package is the encapsulation
  unit.

**`command` and `query` are not exceptions to that last rule.** They are named
for a role rather than for a concept, and so is the `inbound` / `outbound` split
under `adapters`. What separates a role from a filing cabinet is that the role
carries a **different set of allowed imports**: `query` may not import `domain`,
and lint says so, where nothing whatever can be said about what may go in
`models`. A grouping a tool can enforce is a boundary; one it cannot is a
cabinet.

They are singular for the same reason the aggregate package is `order` and not
`orders`: the package name qualifies the identifier at the call site, and the
phrase it forms is about one thing. `command.PlaceOrder` is *the command
PlaceOrder*. `commands.PlaceOrder` is a lookup in a collection, and there is no
collection.
→ [`../ddd/application-services.md`](../ddd/application-services.md)

## The one place this standard overrides Go's anti-stutter rule

Go Code Review Comments says to avoid stutter: the type in package `order`
should be `order.Store`, not `order.OrderStore`. This standard keeps that rule
everywhere except two identifiers per aggregate package:

```go
package order

type Order struct { ... }    // not order.Root, not order.Aggregate
type OrderID struct { ... }  // not order.ID
type Repository interface {} // anti-stutter applies: not OrderRepository
type Status struct { ... }   // anti-stutter applies: not OrderStatus
```

Three reasons, and they do not generalise beyond these two names:

1. **The glossary says "Order" and "Order ID".** `ubiquitous-language.md` rule
   1 requires the code to spell the business's word exactly. `order.Root` is a
   word the business has never used.
2. **An identifier is read in a foreign package.** `order.OrderID` appears in
   `application`, in `adapters`, in another context's ACL. In a signature that
   also takes a `shipment.ShipmentID` and a `customer.CustomerID`, three
   `ID`s named `ID` is worse than three named for their aggregate.
3. **It is bounded.** Two names, in one kind of package. Everything else in the
   aggregate's package — `Repository`, `Status`, `Line`, the errors — obeys the
   anti-stutter rule, which is why `order.Repository` and not
   `order.OrderRepository` is on the page above.

An adapter implementing it is named for its technology in its own package:
`postgres.OrderRepository` stutters with nothing.

## Naming across regions

| Region | The name answers |
|---|---|
| `domain` | What the business calls it. The glossary is the authority |
| `application` | What the use case is, as an imperative: `PlaceOrder`, `CancelOrder`, `ShipConsignment` |
| `application` ports | What the caller needs, never what implements it: `Clock`, `Publisher`, `PaymentGateway` |
| `adapters` | What the technology is: `postgres.OrderRepository`, `kafka.Publisher`, `chi.OrderHandler` |
| `composition` | Nothing exported. It is wiring |
| `platform` | What the technical capability is: `config`, `logging`, `testhelp` |

The rule underneath: **an interface is named by its consumer, an implementation
by itself.** A port called `KafkaPort` has already leaked its adapter into the
region that declared it.

## Test names

```go
func TestPlaceOrder_RejectsAnEmptyBasket(t *testing.T)
```

`Test<Unit>_<BehaviourUnderTest>`. The behaviour half is a sentence about the
domain, not about the mechanism: `RejectsAnEmptyBasket`, not `ReturnsError`.
Subtests inside a table carry the case name, in the same voice. See
[tests](./tests.md).

## Wrong, and why

```go
// Wrong.
package models

type OrderData struct {
	OrderStatusString string
	OrderTotalFloat   float64
	IsValidFlag       bool
}

type IOrderManager interface {
	ProcessOrderData(d *OrderData) error
	GetOrderData(orderIdString string) (*OrderData, error)
}
```

Six failures in twelve lines:

| What | Rule |
|---|---|
| `package models` | 7 — a filing cabinet, not a provider |
| `OrderData` | 7 — `Data` means nothing; and in `models` it stutters |
| `OrderStatusString` | 6 — the type is in the declaration; and a closed set is not a string |
| `OrderTotalFloat` | 6 — and money is never a `float64`, per [value objects](../ddd/value-objects.md) |
| `IsValidFlag` | 11 — `Flag` is noise; `IsValid` was already the assertion |
| `IOrderManager` | 5, 7 — `I` prefix, and `Manager` |
| `ProcessOrderData` | 7 — `Process` names no operation the business performs |
| `GetOrderData` | 9 — `Get` prefix |
| `orderIdString` | 6, 8 — type in the name, and `Id` for an initialism |

```go
// Correct.
package order

type Order struct { ... }

type Status struct { ... }      // closed set, see value-objects.md
type Repository interface {
	ByID(ctx context.Context, id OrderID) (*Order, error)
	Save(ctx context.Context, o *Order) error
}

func (o *Order) Total() Money   { ... }
func (o *Order) IsPlaced() bool { ... }
```

## Common mistakes

| Mistake | What it looks like | Consequence |
|---|---|---|
| Java-length names | `orderRepositoryInstance` | Reads as noise; signals the author is not writing Go |
| Stutter | `order.OrderRepository` | Every call site says "order" twice |
| `I` prefix | `IClock` | A convention from a language Go is not |
| `Impl` suffix | `ClockImpl` | Names the implementation after the interface; the adapter is named for its technology |
| Package named for a layer | `package domain` holding everything | The package is the encapsulation unit; one package per aggregate |
| `Id` / `Url` / `Http` | `orderId` | Fails `golint`, and breaks the one-case initialism rule |
| `Get` prefix | `GetTotal()` | Not the Go convention; and `Get` suggests a lookup that may fail |
| A name that is a lie | `Validate()` that also saves | Worse than a vague name — see [functions](./functions.md) rule 6 |
| Renaming across regions | `Order` → `OrderDTO` → `OrderModel` → `OrderEntity` | Four names for one concept; the glossary had one |

## Checklist

- [ ] Every name in `domain` is a glossary word, spelled as the glossary spells it
- [ ] Name length matches scope size — short locals, full exported names
- [ ] Exported identifiers read correctly as `package.Identifier`
- [ ] No `I` prefix, no `Impl` suffix, no type in any name
- [ ] No `Manager`, `Helper`, `Util`, `Data`, `Info`, `Processor`
- [ ] Initialisms are one case throughout
- [ ] No `Get` prefix on accessors
- [ ] Receivers are one to three letters and consistent per type
- [ ] Ports are named for the need, adapters for the technology
- [ ] Package names are singular providers; the only role-named packages are
      `command`, `query`, and the two adapter directions

## Sources

**Books.** Martin, _Clean Code_, ch. 2 — "Meaningful Names", for the failures it
catalogues, all of which are real. Its length rule is the one this page inverts.
Evans, _Domain-Driven Design_, ch. 2, for why the glossary outranks any style
rule about a name in the model.

**Online.** Every link below was reachable when this page was written.

- [Effective Go: names](https://go.dev/doc/effective_go#names) — package names,
  getters, interface names, MixedCaps; the oldest statement of the rules here
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the
  sections on initialisms, receiver names, interface names and package names
- [Package names](https://go.dev/blog/package-names) — the Go blog on why
  `models` and `utils` are the wrong shape, and what to do instead
- [Google Go Style Decisions: naming](https://google.github.io/styleguide/go/decisions#naming)
  — the most detailed published Go naming rules, including the
  length-proportional-to-scope rule stated explicitly
- [Practical Go: identifier length](https://dave.cheney.net/practical-go/presentations/qcon-china.html#_identifier_length)
  — Cheney's rule: the greater the distance between a name's declaration and its
  uses, the longer the name should be. The same rule as 1 above, stated as a
  distance rather than as a scope
- [Go Proverbs](https://go-proverbs.github.io/) — "Don't name a package after
  what it contains"
