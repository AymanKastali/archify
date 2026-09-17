---
name: modelling-decisions
description: The modelling decisions a Go DDD spec or ticket must carry so the implementer cannot invent them — context, aggregate, ports, transaction, events, errors, data ownership and the cross-context mechanism. Use when writing a spec or breaking work into tickets for a Go project that follows DDD, hexagonal architecture or a modular monolith, including inside /to-spec and /to-tickets, or whenever a plan is about to be handed to an implementer.
---

# Modelling decisions

A spec that says *what* to build and not *how it is modelled* forces the
implementer to invent the model. That invention is where the standard is lost,
and it is why plans come back needing the layout rebuilt.

**This skill does not write the spec.** `/to-spec` writes the spec and
`/to-tickets` cuts the tickets. This supplies what those two must say about the
model in a Go DDD project — and refuses to let a modelling question be deferred
to implementation.

Read [`../standard/SKILL.md`](../standard/SKILL.md) first for the precedence
rule and the map of pages.

## Where the answers go

`/to-spec`'s template already has the slots. Fill them; do not add sections.

| Spec section | What archify puts in it |
|---|---|
| **Implementation Decisions** | Decisions 1–8 and 10–12 below |
| **Testing Decisions** | Decision 9, plus the seams named under *Seams*, below |
| **Out of Scope** | Any bounded context this work deliberately does not touch, named as a context |

The spec's own rule — no file paths, no code snippets — holds. A modelling
decision is "the `Order` aggregate owns the cancellation rule", not a struct.
The one exception the template already allows, a snippet that encodes a decision
more precisely than prose, covers a closed criteria type or an event payload.

## The decisions

A spec is not ready until every one of these is answered. "Decide during
implementation" is not an answer.

1. **Context.** Which bounded context does this belong to? If it spans two, what
   is the relationship, which side translates, and **which mechanism carries
   it** — a published event (the default) or a synchronous read (narrow, reads
   only, and an ADR)? A command crossing a context boundary is never an option;
   say which side owns the decision instead.
   Creating a **new** context is itself a decision with a price list — say why
   the language has already diverged.
   → [`ddd/bounded-contexts.md`](../../standards/ddd/bounded-contexts.md),
   [`ddd/context-mapping.md`](../../standards/ddd/context-mapping.md),
   [`modular-monolith/communication.md`](../../standards/modular-monolith/communication.md),
   [`modular-monolith/modules.md`](../../standards/modular-monolith/modules.md)
2. **Language.** Which glossary terms does this use? Which are new, and what do
   they mean? New terms go into `CONTEXT.md` as part of this work — run
   `/domain-modeling` to add them rather than editing the file freehand.
   → [`ddd/ubiquitous-language.md`](../../standards/ddd/ubiquitous-language.md)
3. **Aggregate and boundary.** Which aggregate owns the rule? What is inside the
   consistency boundary and what is referenced by identity? What invariant
   justifies it?
   → [`ddd/aggregates.md`](../../standards/ddd/aggregates.md)
4. **Building blocks.** Which new types are value objects, which are entities,
   and why. Default to value object; an entity needs a reason.
   → [`ddd/value-objects.md`](../../standards/ddd/value-objects.md)
5. **Behaviour placement.** Which aggregate method, or — with the four-question
   test passed — which domain service.
   → [`ddd/domain-services.md`](../../standards/ddd/domain-services.md)
6. **Use case and transaction.** The application service, its six steps, and
   exactly what is inside the transaction. One aggregate per transaction.
   → [`ddd/application-services.md`](../../standards/ddd/application-services.md)
7. **Events.** Which facts are produced, their past-tense names, and whether any
   crosses a context boundary — which means outbox, and a published event
   distinct from the domain event.
   → [`ddd/domain-events.md`](../../standards/ddd/domain-events.md)
8. **Ports.** Every port this needs, and **where each one lives**: repository
   interfaces in `domain`, everything else in `application`.
   → [`structure.md`](../../standards/structure.md)
9. **Reads.** Which questions are read models rather than repository methods.
   → [`ddd/read-models.md`](../../standards/ddd/read-models.md)
10. **Failure.** Which rules can be broken, the sentinel or typed error for
    each, and how the inbound adapter maps them.
    → [`ddd/errors.md`](../../standards/ddd/errors.md)
11. **Deviations.** Any rule this work needs to break, and the ADR that records
    it. Write the ADR with `/domain-modeling` as part of the spec, not
    afterwards.
12. **Data ownership.** Which schema the new tables live in, and — if this work
    needs a fact another context owns — whether it is projected from events into
    this context's own tables or read synchronously. **A join across contexts is
    not an option to weigh**; say which of the two it is.
    → [`modular-monolith/data.md`](../../standards/modular-monolith/data.md)

## Seams

`/to-spec` asks for the seams the feature is tested at, and wants the fewest
possible — ideally one. In a hexagonal Go context that question has a standing
answer, so propose it rather than re-deriving it:

- **The application service is the seam.** One use case in, ports faked, the
  aggregate exercised for real through it. Almost every feature needs exactly
  this one.
- **The domain is tested directly, with no doubles at all.** It is pure by
  construction, so there is nothing to fake. This is not a second seam; it is
  the absence of one.
- **A port gets a fake, never a mock of your own code.** `/tdd`'s rule is to
  double at system boundaries only — a repository *is* the database boundary,
  so an in-memory fake is right. A domain service or another aggregate is code
  you own, so it is never doubled.
- **An outbound adapter gets its own test against the real thing** — a
  container, not a mock of the driver.

If a feature seems to need a seam inside `domain`, the aggregate boundary is
wrong. Fix decision 3 instead of adding the seam.

## Cutting tickets

`/to-tickets` wants **vertical** slices — a narrow but complete path through
every layer. A region-structured codebase tempts you into the opposite, and it
is the most common way this standard gets applied badly:

> **Wrong:** ticket 1 "add the value objects", ticket 2 "add the aggregate",
> ticket 3 "add the repository", ticket 4 "wire the handler".
>
> That is four horizontal slices of the region stack. None is demoable, none
> can be verified alone, and the model is settled in ticket 1 by whoever writes
> it fastest.

**A vertical slice in this layout is one use case, end to end** — the value
objects it needs, the aggregate method, the port, the adapter, the wiring, the
test at the application service. It touches all four regions because that is
what "complete path" means here.

The file list for a slice is grouped by region, because that is where a
dependency-direction error is visible before it is written:

```text
contexts/ordering/internal/domain/order/       order.go, line.go, events.go, repository.go, errors.go
contexts/ordering/internal/application/command/  place_order.go, and any port only it calls
contexts/ordering/internal/application/query/    list_customer_orders.go, if the slice has a read side
contexts/ordering/internal/adapters/inbound/   http/place_order_handler.go
contexts/ordering/internal/adapters/outbound/  postgres/order_repository.go, postgres/outbox.go
contexts/ordering/published/                   events.go          (only if the fact leaves the context)
contexts/ordering/migrations/                  0007_add_placed_at.sql
contexts/ordering/ordering.go                  wiring, if a dependency was added
```

If a file appears under `domain/` that needs a driver, a framework or a clock,
the model is wrong and this is the moment it is cheap to fix.

The one exception `/to-tickets` already carves out — the **wide refactor**,
sequenced expand–contract — applies unchanged. Renaming a value object used in
forty places is exactly that, and forcing it into a tracer bullet is wrong.

## What not to do

- Do not write pseudo-code for the whole feature. Decisions, not transcription.
- Do not leave "TBD" on a consistency boundary. A boundary decided later is a
  boundary decided by whoever is typing.
- Do not restate the standard in the spec. Cite the page.
- Do not add archify sections to `/to-spec`'s template. The slots exist.
