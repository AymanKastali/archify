# Ubiquitous language

One language, spoken by the domain experts and spelled the same way in the code.
Not a translation layer between "business terms" and "technical terms" — the
absence of one.

**Authority.** Evans, ch. 2.

## Why it exists

Every translation step is a place a misunderstanding survives. If the business
says "a Visit is forwarded to another Desk" and the code says
`transferRecord(id, deskId)`, then a conversation about forwarding cannot be
checked against the code without a human holding both vocabularies in their
head. The bug that lives in the gap is invisible from either side.

The test is blunt: **read a method name out loud to a domain expert.** If they
would not use that phrase, the name is wrong — not the expert.

## The rules

1. **The glossary is `CONTEXT.md`.** One per bounded context. It is a glossary
   and nothing else: no implementation notes, no schemas, no decisions.
2. **A term that is not in the glossary does not appear in `domain` code.** Add
   it to the glossary first. This is not bureaucracy — it is the only moment
   when renaming is free.
3. **One word per concept, and the glossary picks it.** When the business uses
   three words for one thing, choose one and list the others as rejected. Code
   uses the chosen one everywhere.
4. **The same word may mean different things in different contexts, and that is
   allowed.** `Order` in `ordering` and `Order` in `shipping` are different
   types that are never shared. That is what a bounded context is for — see
   [bounded contexts](./bounded-contexts.md).
5. **Technical vocabulary is not domain language.** `Manager`, `Helper`,
   `Util`, `Processor`, `Handler`, `Data`, `Info`, `DTO`, `Entity` name nothing
   a domain expert says out loud.

## Glossary format

```markdown
# Ordering

Receives customer orders, holds them until they are placed, and publishes the
fact that they were.

## Language

**Order**:
A customer's request for a set of goods at agreed prices, which becomes binding
when it is placed.
_Avoid_: Purchase, Transaction, Cart

**Order Line**:
One SKU, its quantity, and the price agreed for it at the moment the order was
placed.
_Avoid_: Item, Row, Product

**Place**:
The act that makes a draft Order binding. An Order is placed once and cannot be
placed again.
_Avoid_: Submit, Confirm, Checkout
```

Verbs belong in the glossary as much as nouns. `Place` above is the term that
stops three sessions producing `Submit`, `Confirm` and `Checkout` for one act.

## In Go

### Correct

```go
// Package order is the Order aggregate.
package order

// Place makes a draft Order binding. The glossary defines "place" as the act;
// this method is named for it and nothing else.
func (o *Order) Place(now time.Time) error {
	if o.status != StatusDraft {
		return ErrAlreadyPlaced
	}
	if len(o.lines) == 0 {
		return ErrNoLines
	}
	o.status = StatusPlaced
	o.placedAt = now
	o.record(OrderPlaced{OrderID: o.id, CustomerID: o.customerID, PlacedAt: now})
	return nil
}
```

### Wrong, and why

```go
// Wrong: three different words for one act, none of them the glossary's.
func (o *Order) Submit() error   { ... }
func (o *Order) Confirm() error  { ... }
func (o *Order) Checkout() error { ... }

// Wrong: named for its mechanism, not for the act.
func (o *Order) SetStatus(s string) { o.status = s }

// Wrong: a technical noun standing in for a domain concept.
type OrderManager struct{ ... }
type OrderData struct{ ... }
```

`SetStatus` is the worst of these. It is not merely badly named — it makes the
act unnameable, because every transition becomes the same call and the rule
about which transitions are legal has nowhere to live.

## Naming rules that follow

- **A method is named for the act**, in the language: `Place`, `Cancel`,
  `Forward`. Not `SetX`, not `UpdateX`, not `ProcessX`.
- **A type is named for the concept**, with no suffix: `Order`, not
  `OrderEntity`, `OrderModel` or `OrderDTO`.
- **An event is named for the fact, in the past tense**: `OrderPlaced`, not
  `PlaceOrderEvent` or `OrderPlaceEvent`.
- **A package is named for the concept it holds**, singular and lowercase:
  `package order`, not `package orders`, `package models` or `package domain`.
  Go reads the package name at every call site — `order.Place` says it;
  `models.PlaceOrder` says nothing.

## Common mistakes

| Mistake | What it looks like | Why it matters |
|---|---|---|
| Database vocabulary in the model | `row`, `record`, `insert`, `table` | The model now describes its storage, not its subject |
| HTTP vocabulary in the model | `request`, `payload`, `response` | Same, one layer out |
| Generic verbs | `Process`, `Handle`, `Manage`, `Update` | Hides which act occurred, so rules about acts cannot be written |
| Synonym drift across files | `Customer` here, `Client` there | Two names imply two concepts; readers look for the difference |
| A glossary written after the code | — | Then it documents the accident rather than deciding it |

## Checklist

- [ ] Every domain type, method and event name appears in `CONTEXT.md`
- [ ] No `Manager`, `Helper`, `Util`, `Processor`, `Data`, `Info`, `DTO` in `domain`
- [ ] Methods are named for acts, not for field assignment
- [ ] Events are past tense
- [ ] Packages are singular concept names
- [ ] No storage or transport vocabulary anywhere in `domain`

## Sources

**Books.** Evans, _Domain-Driven Design_, ch. 2 — "Communication and the Use of
Language". Vernon, _Implementing Domain-Driven Design_, ch. 1.

**Online.** Every link below was reachable when this page was written.

- [Domain-Driven Design Reference](https://www.domainlanguage.com/ddd/reference/)
  — Evans's own free distillation of every pattern definition ([direct PDF](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf))
- [UbiquitousLanguage](https://martinfowler.com/bliki/UbiquitousLanguage.html)
  — Fowler, on why the language is a shared team language and not developer
    jargon
- [Package names](https://go.dev/blog/package-names)
  — the Go team on naming packages for what they provide, which is the same
    discipline applied to import paths
