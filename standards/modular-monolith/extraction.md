# Extraction

Turning one context into a separate service. This page exists so the operation
is mechanical — and so that the first question asked is whether to do it at all.

**Authorities.** Sam Newman, _Monolith to Microservices_ (2019), ch. 3, for the
pattern catalogue. Fowler, _StranglerFigApplication_ and _MicroservicePremium_.
Evans, ch. 14, for the point the whole corpus rests on: the boundary was never
the deployment.

## The claim this page has to keep true

> **Extraction is a deployment change, not a design change.**
>
> What changes: the composition root, one outbound adapter per cross-context
> call, one inbound adapter per subscription, the schema's connection details,
> and the deployment.
>
> What does not change: any file under `domain/`, any file under
> `application/`, the aggregate, the tests of either, the published language, or
> the shape of anything.

If extracting requires editing a domain file, the extraction is not the problem
— **the modularity was decorative, and every rule under
[`modular-monolith.md`](../modular-monolith.md) exists to prevent exactly this
moment.**

## First: probably don't

The default is one deployable, and the reasons to leave it are four, each a
property you want and cannot otherwise have:

| Reason | The question that tests it |
|---|---|
| **Independent scaling** | Does this context have a genuinely different *resource* profile — CPU-bound, GPU-bound, memory-bound — or is it just busy? Busy is solved by another replica of the whole binary, which is cheaper than a service |
| **Independent release cadence** | Is a different team, on a different rotation, blocked by your release train today? Not "would be tidier" — blocked |
| **A different runtime** | Is the thing not Go? |
| **Blast-radius isolation** | Is it a written requirement — compliance, tenancy, a regulator — rather than a preference? |

**None of these is:** the codebase is large, the build is slow, the team is
growing, the boundary would be clearer, or it might need to scale later. The
first two are module problems, the third is an organisational one, the fourth is
what the compiler already gives you, and the fifth is
[`MonolithFirst`][mf] — the boundaries you would draw before you have the
traffic are the wrong ones.

The decision is recorded as an ADR naming which of the four applies.

### What you give up

State it in the ADR, because it is real and it is permanent:

- **Cross-context refactoring stops being safe.** Renaming a published field is
  currently a compile error in every consumer. Afterwards it is a runtime
  failure in production, discovered by whoever is on call.
- **The build test goes.** Today one `go test` proves the whole system wires up.
  Afterwards nothing does, until a contract test says a fraction of it.
- **Local development gets a docker-compose file** and a reason for new people
  to be stuck on their first day.
- **Every synchronous call acquires failure modes** it did not have: timeout,
  partial failure, retry storms, and the version skew of two deploys.
- **A transaction that was already forbidden is now impossible.** This one is a
  gain, and it is the only one.

## Readiness

Extraction goes wrong when it is used to *achieve* modularity rather than to
exploit it. Everything below must already be true **in the monolith**, where the
compiler is still helping you:

- [ ] The context owns its schema, with no cross-schema join or foreign key
      → [data](./data.md)
- [ ] No transaction touches this context and another
- [ ] Every cross-context message is a `published/` type, carried by the outbox
      → [communication](./communication.md)
- [ ] Every consumer of this context reaches it through an interface **the
      consumer declared**, never through its facade package
      → [modules](./modules.md), rule 6
- [ ] Every subscription to this context's events passes through an ACL on the
      consuming side
- [ ] Every handler is idempotent on the message id
- [ ] No consumer matches on this context's errors
- [ ] This context's tests use fakes for every outbound port, so none of them
      knows whether a collaborator is in-process

**Any unchecked box is work to do before extracting, in the monolith.** Doing it
afterwards means doing it across a network, without the compiler, with two
deploys.

## The procedure

Each step is independently deployable and independently revertible. That is the
property worth more than speed.

**1 — Build the second binary, wired from the same code.**
Add `cmd/ordering/main.go` that calls `composition.ServeOrdering(ctx, cfg)`,
constructing only the ordering context. Deploy nothing. This proves the context
is constructible alone, which is the one thing the monolith never tested.

**2 — Move the schema.** Point ordering's DSN at its own database instance.
Because there were never any cross-schema references, this is a `pg_dump` of one
schema and a DSN change. If it is not, go back to `data.md` and finish.

**3 — Replace the bus with a broker.** `platform/eventbus` grows a second
implementation — Kafka, NATS, SQS — and the composition root chooses it by
configuration. **Nothing in any context changes**: the relay still drains the
outbox, the subscriber still receives a `Message`, the ACL still translates.
This step is where publish-then-mark and idempotent handlers stop being
pedantry: they are now load-bearing.

**4 — Replace each synchronous call with a client.** For every consumer-declared
interface that `*ordering.Component` was satisfying, write an adapter that
speaks HTTP or gRPC instead, and change the assignment in the composition root:

```go
// before
shp, err := shipping.New(shipping.Deps{DB: pools["shipping"], Orders: ord})

// after — one line, in one file
shp, err := shipping.New(shipping.Deps{
	DB:     pools["shipping"],
	Orders: orderingclient.New(cfg.Ordering.BaseURL, cfg.Ordering.Timeout),
})
```

`orderingclient` lives in shipping's `adapters/outbound/ordering/`, beside the
ACL that was already there, and it satisfies the same interface shipping
declared. **Shipping's tests do not change** — they were using a fake for that
interface already.

**5 — Deploy the second binary and cut over**, one caller at a time, behind
configuration. Run both for a while. Fowler's strangler fig is the shape: the
new path takes traffic incrementally and the old one is removed last.

**6 — Delete the context from the monolith's composition root**, and the
dependency from `go.mod` if the code moves repositories. Deleting it from
`internal/contexts/` is the *last* step, and it is a revert boundary until then.

## What changes, exhaustively

| Region | Change |
|---|---|
| `domain/` | **None.** Not one file |
| `application/` | **None.** Not one file, including its ports — they were already interfaces |
| `published/` | **None**, except that it now ships as a shared package or is copied into each consumer |
| `adapters/inbound/http/` | None. It was already serving HTTP; now something else calls it |
| `adapters/inbound/events/` | The subscriber registration changes shape; the ACL translation function does not |
| `adapters/outbound/<ctx>/` | One new client implementation, satisfying an interface that already existed |
| `migrations/` | None. They move with the context |
| `<context>.go` | None. `New` already took everything it needed as parameters |
| `internal/composition/` | Split in two, and one assignment per cross-context call |
| `platform/` | One new `eventbus` implementation. Everything else unchanged |
| Tests of the model | **None** |
| Tests of the application services | **None** — they used fakes |
| Tests of adapters | One new adapter gets one new test |
| New work | Contract tests between the two, which nothing replaced |

**If your extraction's list is longer than this one, stop and find out which
rule was not being followed.** The extra work is the accumulated cost of that
rule, being paid at the worst possible moment, and it will be cheaper to fix
inside the monolith first.

## What the network adds, and where it goes

The failure modes are new; the place they live is not. **They go in the
consumer's outbound ACL**, which already existed, and nothing inward notices:

```go
// internal/contexts/shipping/internal/adapters/outbound/ordering/client.go
//
// Satisfies the same shipping.OrderQueries interface *ordering.Component used
// to. Everything the network added — timeout, retry, breaker, decoding — is
// here, and shipping's application layer is unchanged.
type Client struct {
	http    *http.Client
	base    string
	breaker *breaker.Breaker
}

func (c Client) OrderSummary(ctx context.Context, id string) (orderingpub.OrderSummary, error) {
	ctx, cancel := context.WithTimeout(ctx, c.timeout)
	defer cancel()

	var out orderingpub.OrderSummary
	err := c.breaker.Do(func() error { return c.get(ctx, "/api/orders/"+id, &out) })
	switch {
	case errors.Is(err, breaker.ErrOpen), errors.Is(err, context.DeadlineExceeded):
		// The same error shipping's ACL already returned when ordering was a
		// function call away and failed. Nothing upstream learns anything new.
		return orderingpub.OrderSummary{}, shipment.ErrOrderUnavailable
	case err != nil:
		return orderingpub.OrderSummary{}, fmt.Errorf("ordering summary %s: %w", id, err)
	}
	return out, nil
}
```

The reason this is a small diff is rule 10 of
[communication](./communication.md): shipping never matched on ordering's
errors, so it already had its own `ErrOrderUnavailable` and already had a path
for it.

## Wrong ways to extract

| Approach | What happens |
|---|---|
| Extract first, modularise after | You are now doing the hard half across a network with two deploys and no compiler |
| Extract the layer, not the context — a "data service", an "API gateway" owning models | A distributed monolith: every change touches every service, with latency added |
| Share the database between the monolith and the new service "for now" | The coupling that mattered never left. You have paid for distribution and kept the constraint |
| Keep a synchronous call and call it temporary | It is not temporary. Two availability budgets are now one, and nothing will ever be scheduled to fix it |
| Copy the context into a new repository and diverge | Two models of one thing, a divergence nobody planned, and a merge that never happens |
| Extract because the context is the messiest one | Messy in-process is cheap to fix. Messy across a network is not. Extract the **clean** context; fix the messy one where the compiler helps |

## Coming back

Merging a service back into the monolith is legitimate and is not an admission
of anything. It is the same procedure in reverse and it is easier: the interface
the consumer declared is still there, and the assignment goes back to
`Orders: ord`. Record it as an ADR superseding the extraction one, so the
history says a decision was revisited rather than forgotten.

## Checklist

- [ ] An ADR names which of the four reasons applies, and what is being given up
- [ ] Every readiness box above is ticked, in the monolith, before step 1
- [ ] The context builds and runs as its own binary before anything is deployed
- [ ] The schema moved with no join or foreign key to remove
- [ ] The broker swap changed no file inside any context
- [ ] Each synchronous call became one new adapter and one composition-root line
- [ ] No `domain/` or `application/` file was edited
- [ ] Contract tests exist between the two deployables
- [ ] The old path is deleted last, and cut-over was reversible until then

## Sources

**Books.** Sam Newman, _Monolith to Microservices_. O'Reilly, 2019.
ISBN 978-1-492-04784-1 — ch. 3 is the pattern catalogue (Strangler Fig, Branch
by Abstraction, Parallel Run, Decorating Collaborator) and ch. 4 is the data
half. Sam Newman, _Building Microservices_, 2nd ed., ch. 3, for the
decomposition decision. Evans, ch. 14.

**Online.** Every link below was reachable when this page was written.

- [StranglerFigApplication](https://martinfowler.com/bliki/StranglerFigApplication.html)
  — Fowler. Step 5's shape, and the reason it is incremental
- [MicroservicePremium](https://martinfowler.com/bliki/MicroservicePremium.html)
  — Fowler, 2015. The price list *First: probably don't* is quoting
- [MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html) — Fowler,
  2015, on boundaries drawn before there is evidence for them
- [How to break a Monolith into Microservices](https://martinfowler.com/articles/break-monolith-into-microservices.html)
  — Dehghani; the sequencing argument, and the point that the data split is the
  real work
- [Pattern: Monolithic architecture](https://microservices.io/patterns/monolithic.html)
  — Richardson's honest statement of what is being left behind
- [Towards Modern Development of Cloud Applications](https://sigops.org/s/conferences/hotos/2023/papers/ghemawat.pdf)
  — Ghemawat et al., HotOS 2023: write the modular monolith, defer the
  distribution decision to deployment. This page is that argument with the
  deferral made explicit

[mf]: https://martinfowler.com/bliki/MonolithFirst.html
