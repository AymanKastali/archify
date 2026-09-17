# Communication

How one context reaches another when both are in the same process — and why
that fact changes nothing about the mechanism.

**What crosses** a context boundary, and the relationship patterns, are
[`../ddd/context-mapping.md`](../ddd/context-mapping.md). **What an event is**
is [`../ddd/domain-events.md`](../ddd/domain-events.md). This page is the
in-process mechanics, and one ruling those two pages do not make.

**Authorities.** Evans, ch. 14–17. Vernon, ch. 8 and ch. 13. Hohpe & Woolf,
_Enterprise Integration Patterns_, for the messaging vocabulary. The
transactional-outbox rule comes from none of them — it is Richardson's pattern
and this standard's own insistence on applying it in one process.

## The ruling

> **Cross-context delivery is asynchronous, and it goes through the outbox, even
> when the consumer is a function call away in the same binary.**

This is the rule most often broken on the grounds that it is obviously
unnecessary in one process. It is not, for four reasons, and each one bites on a
Tuesday afternoon rather than in theory:

1. **One aggregate per transaction still binds.** A synchronous in-process
   handler runs inside the publisher's transaction and writes a second
   aggregate — the exact rule
   [`../ddd/aggregates.md`](../ddd/aggregates.md) exists to enforce, broken by
   a mechanism chosen for convenience.
2. **Failure isolation.** Direct dispatch makes the publisher's availability the
   product of every subscriber's. An order cannot be placed because the
   invoicing handler has a bug is a defect the boundary was supposed to prevent.
3. **The semantics must not change under you.** In-process dispatch is
   exactly-once, ordered and instantaneous. A broker is at-least-once, unordered
   and eventually. Code written against the first and run against the second
   fails at extraction — the most expensive moment available.
4. **Atomicity.** Publishing after the transaction commits loses messages on
   crash; publishing inside it announces changes that may roll back. There is no
   third option that does not involve a table.
   → [`../ddd/domain-events.md`](../ddd/domain-events.md), rule 7

The cost is one table per context and a relay of about a hundred and fifty lines
in `platform/outbox`, written once. The alternative is a boundary that holds
only while nothing fails.

## Choosing the mechanism

| The consumer needs | Mechanism | Allowed |
|---|---|---|
| To react to something that happened | Subscribe to a published event | **Default.** Requires nothing |
| To read something to serve the request it is handling now | Synchronous query through a consumer-declared interface, returning published types | **Narrow**, and requires an ADR → below |
| To cause a state change in another context | — | **Never.** See below |
| A consistent view across two contexts at one instant | — | **Never.** The boundary is wrong → [`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md) |
| To report across both | A read model built from events, owned by whoever asks | → [data](./data.md) |

### There is no synchronous cross-context write

If `shipping` needs `ordering` to change state, one of three things is true, and
none of them is "call `ordering.PlaceOrder`":

- **It is reacting to a fact.** Then `ordering` publishes and `shipping`
  subscribes, or the other way round — but the *decision* stays with the context
  that owns the rule.
- **The rule belongs to the caller.** Then it is not a cross-context write at
  all; the state is modelled in the wrong context.
- **The two must change together, always.** Then they are one context, and the
  boundary is the defect.

A command crossing a context boundary is a distributed transaction wearing a
function call.

## The rules

1. **Events cross; domain types do not.** The thing published is a
   `published/` type, built from the domain event at the moment it is recorded.
2. **Topic names are constants in `published/`**, of the form
   `<context>.<EventName>` — `ordering.OrderPlaced`. A consumer subscribes to a
   symbol, never a string literal.
3. **Every context has its own outbox table, in its own schema**, written inside
   the same transaction as the aggregate.
4. **Every context runs its own relay,** driven by its facade's `Run`. The relay
   reads that context's outbox and hands messages to the bus.
5. **The bus is platform.** `internal/platform/eventbus` knows topics and bytes.
   It knows no context, no domain type and no business rule.
   → [platform](./platform.md)
6. **Delivery is at-least-once, in process as well.** Every handler is
   idempotent. There is no arrangement of relay and marker that is not either
   at-least-once or lossy.
7. **Ordering is not guaranteed.** A handler that requires two events in order
   is either wrong or needs to carry the ordering fact in the payload.
8. **Every subscription passes through an ACL** in the consumer's
   `adapters/inbound/events/`, one file per upstream context, converting
   primitives to this context's value objects and rejecting bad input there.
   → [`../ddd/context-mapping.md`](../ddd/context-mapping.md)
9. **A handler's job is to call one use case.** It translates and delegates. A
   rule inside a subscriber is a rule outside the model.
10. **A consumer never matches on another context's error.**
    `errors.Is(err, order.ErrNotFound)` across a boundary is a coupling the
    compiler happens to allow; the ACL maps the upstream failure to this
    context's own error.
11. **No `*sql.Tx` crosses a context boundary.** Not as an argument, not in a
    `context.Context` value, not through a shared unit of work.
    → [data](./data.md)
12. **Subscriptions are declared by the consumer and registered by the
    composition root.** No context registers itself, and no global registry
    exists for it to register with.

## The bus

```go
// internal/platform/eventbus/bus.go
//
// An in-process publish/subscribe bus. It carries topics and bytes and knows
// nothing else — swapping it for Kafka or NATS is a change to the composition
// root and to nothing in any context.
package eventbus

// Message is what crosses. ID is the outbox row id and is what makes
// at-least-once delivery survivable: handlers deduplicate on it.
type Message struct {
	ID       string
	Topic    string
	Payload  []byte
	Occurred time.Time
}

// Handler processes one message. Returning an error means "not handled";
// the bus will redeliver.
type Handler func(ctx context.Context, m Message) error

type Subscription struct {
	Topic  string
	Name   string // the subscriber's own name — used for dedupe and for metrics
	Handle Handler
}

type Publisher interface {
	Publish(ctx context.Context, m Message) error
}
```

## The outbox relay, in process

```go
// internal/platform/outbox/relay.go
//
// Moves rows from one context's outbox table to the bus. One relay per context,
// reading that context's schema. Started by the composition root, never by a
// goroutine in a constructor.
package outbox

type Relay struct {
	store Store
	bus   eventbus.Publisher
	log   *slog.Logger
	tick  time.Duration
}

// Run polls until ctx is cancelled. It is the context facade's Run method.
func (r *Relay) Run(ctx context.Context) error {
	t := time.NewTicker(r.tick)
	defer t.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-t.C:
			if err := r.drain(ctx); err != nil {
				r.log.Error("outbox drain failed", "err", err)
			}
		}
	}
}

func (r *Relay) drain(ctx context.Context) error {
	batch, err := r.store.Unpublished(ctx, 100)
	if err != nil {
		return fmt.Errorf("reading outbox: %w", err)
	}

	for _, row := range batch {
		msg := eventbus.Message{
			ID: row.ID, Topic: row.Topic, Payload: row.Payload, Occurred: row.OccurredAt,
		}
		// Publish first, mark second. A crash between the two redelivers,
		// which is why every handler is idempotent. The reverse order loses
		// messages, which nothing can recover from.
		if err := r.bus.Publish(ctx, msg); err != nil {
			return fmt.Errorf("publishing %s: %w", row.ID, err)
		}
		if err := r.store.MarkPublished(ctx, row.ID); err != nil {
			return fmt.Errorf("marking %s: %w", row.ID, err)
		}
	}
	return nil
}
```

The comment on the ordering is the whole design. **Publish-then-mark is
at-least-once; mark-then-publish is at-most-once.** At-least-once with
idempotent handlers is recoverable; a lost `OrderPlaced` is not.

## The consuming side

```go
// internal/contexts/shipping/internal/adapters/inbound/events/ordering.go
//
// The anti-corruption layer for the ordering context. Nothing below this file
// knows that ordering exists, what it calls things, or that a bus carried the
// message.
package events

import (
	orderingpub "myapp/internal/contexts/ordering/published"
	"myapp/internal/contexts/shipping/internal/application/command"
	"myapp/internal/contexts/shipping/internal/domain/shipment"
)

type OrderingACL struct {
	prepare *command.PrepareShipment
}

func (a *OrderingACL) OnOrderPlaced(ctx context.Context, m eventbus.Message) error {
	var e orderingpub.OrderPlaced
	if err := json.Unmarshal(m.Payload, &e); err != nil {
		// Malformed payload is permanent. Returning an error here would
		// redeliver it forever; it is dropped to a dead-letter table instead.
		return fmt.Errorf("%w: decoding OrderPlaced: %v", errPermanent, err)
	}

	cmd, err := toPrepareShipment(e)
	if err != nil {
		return fmt.Errorf("%w: %v", errPermanent, err)
	}

	// Dedupe on the message id: delivery is at-least-once.
	return a.prepare.Handle(ctx, m.ID, cmd)
}

// toPrepareShipment turns ordering's words into shipping's. Ordering says
// "Line"; shipping says "Item". Ordering says "CustomerID"; shipping does not
// care who the customer is, only where the parcel goes.
func toPrepareShipment(e orderingpub.OrderPlaced) (command.PrepareShipment, error) {
	items := make([]command.Item, 0, len(e.Lines))
	for _, l := range e.Lines {
		sku, err := shipment.NewSKU(l.SKU)
		if err != nil {
			return command.PrepareShipment{}, fmt.Errorf("order %s: %w", e.OrderID, err)
		}
		qty, err := shipment.NewQuantity(l.Quantity)
		if err != nil {
			return command.PrepareShipment{}, fmt.Errorf("order %s: %w", e.OrderID, err)
		}
		items = append(items, command.Item{SKU: sku, Quantity: qty})
	}

	return command.PrepareShipment{
		OrderRef: shipment.OrderRef(e.OrderID),
		Items:    items,
	}, nil
}
```

Three things are happening, and all three are the point: **translation** at one
file, **validation** into value objects at the boundary, and **idempotency**
carried on the message id rather than assumed.

## The narrow synchronous read

`../ddd/context-mapping.md` rule 2 makes a synchronous cross-context call a
departure requiring an ADR. That stands. When the ADR exists, this is the shape,
and the constraints are tighter than the ADR needs to say:

- **Reads only.** Never a command.
- **Returns published types.** Never the model.
- **The consumer declares the interface**, in its own facade file. It does not
  import the upstream context.
  → [modules](./modules.md), rule 6
- **It still passes through an ACL** in the consumer's `adapters/outbound/`,
  which converts the published types into this context's value objects.
- **It is treated as a remote call**: it takes a `context.Context`, it has a
  timeout, and its failure is a handled case rather than an impossibility.

```go
// internal/contexts/shipping/internal/adapters/outbound/ordering/queries.go
package ordering

// orderQueries is the slice of the ordering context this adapter uses.
// Declared here so the package imports ordering/published and nothing else;
// *ordering.Component satisfies it structurally today, an HTTP client will
// satisfy it later, and a fake satisfies it in tests.
type orderQueries interface {
	OrderSummary(ctx context.Context, id string) (orderingpub.OrderSummary, error)
}

type ACL struct{ q orderQueries }

// Summary answers shipping's question in shipping's words, and maps ordering's
// failures to shipping's errors — shipping never matches on ordering's.
func (a ACL) Summary(ctx context.Context, ref shipment.OrderRef) (shipment.OrderFacts, error) {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	s, err := a.q.OrderSummary(ctx, string(ref))
	if err != nil {
		return shipment.OrderFacts{}, fmt.Errorf("looking up %s: %w", ref, shipment.ErrOrderUnavailable)
	}
	return shipment.OrderFacts{Ref: ref, Placed: s.Status == "placed"}, nil
}
```

## Wrong, and why

```go
// Wrong: direct dispatch. The subscriber runs inside the publisher's
// transaction, writes a second aggregate, and takes the publisher down with it
// when it fails.
func (s *PlaceOrder) Handle(ctx context.Context, cmd Cmd) error {
	// ... save the order ...
	return s.shipping.PrepareShipment(ctx, ...) // a command across a boundary
}
```

```go
// Wrong: the transaction crosses the boundary. Now one rollback spans two
// schemas, and extracting either context is impossible without a rewrite.
func (s *PlaceOrder) Handle(ctx context.Context, tx *sql.Tx, cmd Cmd) error {
	...
	return s.billing.RaiseInvoice(ctx, tx, ...)
}
```

```go
// Wrong: matching on the upstream's error. The consumer now depends on
// ordering's error values, which are in ordering's domain package — and if the
// nested internal/ did not stop this compiling, the extraction would.
if errors.Is(err, order.ErrNotFound) { ... }
```

```go
// Wrong: a rule inside a subscriber. Shipping decides whether ordering's order
// was large, using a threshold nobody in shipping's glossary can explain.
func (a *OrderingACL) OnOrderPlaced(ctx context.Context, m eventbus.Message) error {
	var e orderingpub.OrderPlaced
	_ = json.Unmarshal(m.Payload, &e)
	if len(e.Lines) > 10 {
		return a.prepare.HandlePalletised(ctx, e)
	}
	return a.prepare.Handle(ctx, e)
}
```

```go
// Wrong: subscribing to a string literal. A rename in published/ now fails at
// runtime, in production, on the messages nobody is receiving.
bus.Subscribe("order.placed", h)
```

## Failure, retries and poison messages

| Situation | Handling |
|---|---|
| Handler returns a transient error | The relay redelivers. Backoff lives in the bus, not in the handler |
| Handler returns a permanent error — malformed payload, a value object that can never be constructed | Dead-letter it. Redelivering forever is an outage that looks like a queue |
| The same message arrives twice | Expected. The handler deduplicates on `Message.ID` |
| Two events must be processed in order | Carry the ordering fact — a version, a timestamp — and let the handler decide. Do not assume the bus |
| A subscriber is down | The publisher does not know and does not care. That is the property being bought |

## Checklist

- [ ] No context calls another context's application service
- [ ] No command crosses a context boundary
- [ ] Every published event is written to the outbox in the aggregate's transaction
- [ ] Each context runs its own relay, from its facade's `Run`
- [ ] Every subscriber is idempotent on `Message.ID`
- [ ] Every subscription has an ACL file, one per upstream context
- [ ] Topics are constants from `published/`, never literals
- [ ] No `*sql.Tx` appears in any cross-context signature
- [ ] No `errors.Is` against another context's error
- [ ] Any synchronous cross-context call is a read, returns published types, has a timeout, and has an ADR

## Sources

**Books.** Gregor Hohpe & Bobby Woolf, _Enterprise Integration Patterns_.
Addison-Wesley, 2003. ISBN 978-0-321-20068-6 — the vocabulary for everything on
this page. Vernon, ch. 8 (Domain Events) and ch. 13 (Integrating Bounded
Contexts). Evans, ch. 14. Sam Newman, _Building Microservices_, 2nd ed., ch. 4,
for why the synchronous option is narrower than it looks.

**Online.** Every link below was reachable when this page was written.

- [Pattern: Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)
  — Richardson. The pattern rule 3 applies, and the reason the ordering comment
  in `drain` is the design
- [Pattern: Polling publisher](https://microservices.io/patterns/data/polling-publisher.html)
  — the relay above, named
- [Pattern: Idempotent Consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html)
  — rule 6, with the storage options laid out
- [Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/patterns/messaging/)
  — Hohpe's free pattern index; Dead Letter Channel and Idempotent Receiver are
  the two this page leans on
- [What do you mean by "Event-Driven"?](https://martinfowler.com/articles/201701-event-driven.html)
  — Fowler, on the four different things "event" is used for, which is worth
  settling before an argument about this page
- [Anti-corruption Layer pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer)
  — the consuming-side translation rule 8 requires
- [Go Code Review Comments: interfaces](https://go.dev/wiki/CodeReviewComments)
  — the consumer declares the interface, which is what makes the synchronous
  read extractable
