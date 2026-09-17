---
name: writing-order
description: The order Go DDD code is written in so a dependency-direction error is unwritable, plus the done-checks for context boundaries, domain purity, port placement, schema ownership, transaction scope and errors. Use when implementing a feature, aggregate, value object, repository, application service, domain event, port or cross-context integration in a Go project that follows DDD, hexagonal architecture or a modular monolith, including inside /implement and /tdd.
---

# Writing order

`/implement` builds the ticket and drives `/tdd` to do it. This skill does not
replace either. It supplies the two things they cannot know on their own: the
**order** the pieces of a Go DDD slice get written in, and the **checks** that
say the slice is finished.

Read [`../standard/SKILL.md`](../standard/SKILL.md) for precedence and the map.

## How this fits the red–green loop

`/tdd` forbids horizontal slicing — all tests first, then all implementation —
and it is right. The order below is not that, and the distinction matters
enough to state plainly:

- **The test goes outside-in.** The failing test is written at the application
  service, the seam the spec agreed. That is where the slice enters.
- **The implementation goes inside-out.** To make that test pass you write the
  value objects, then the aggregate, then the port, then the service. Each step
  may only import what earlier steps produced, so a dependency error becomes
  impossible to type rather than something to find afterwards.
- **The slice stays vertical.** One use case per cycle, all four regions, one
  test. You are not writing all the value objects in the context — only the ones
  this test needs.

Outside-in test, inside-out implementation, one slice at a time. Nothing here
loosens `/tdd`'s rules; it only says which file to open next.

## The order

**0 — Context.** Which bounded context is this? Open its directory under
`internal/contexts/`. If the answer is "a new one", stop and check
[`ddd/bounded-contexts.md`](../../standards/ddd/bounded-contexts.md) — the
default is that it is not, and a new context costs a schema, a published
language, an ACL per consumer and eventual consistency with everything it used
to be consistent with.
→ [`modular-monolith/modules.md`](../../standards/modular-monolith/modules.md)

If the slice genuinely spans two contexts, it is **two slices** with an event
between them, not one. Decide that now, before any code.
→ [`modular-monolith/communication.md`](../../standards/modular-monolith/communication.md)

**1 — Language.** Open the project's `CONTEXT.md`. Every type, method and event
you are about to name comes from it. A name that is not in the glossary is
either wrong or a new term — and a new term is added with `/domain-modeling`,
in this change, not left for later.

**2 — Value objects.** In `domain`. Every concept that is currently a `string`,
`int` or `float64` and has a rule attached is one. Money is never a `float64`,
and a closed set is never a bare `type X string`.
→ [`ddd/value-objects.md`](../../standards/ddd/value-objects.md)

**3 — The aggregate.** Unexported fields, a constructor that cannot produce an
invalid instance, behaviour methods named for business acts, and no setters.
State the invariant in a comment on the type; if you cannot, the boundary is
wrong.
→ [`ddd/aggregates.md`](../../standards/ddd/aggregates.md)

**4 — Events.** Past tense, recorded by the aggregate, released — never
published — by it.
→ [`ddd/domain-events.md`](../../standards/ddd/domain-events.md)

**5 — The repository interface**, in `domain` beside the aggregate. Collection
vocabulary, aggregates only, typed not-found error.
→ [`ddd/repositories.md`](../../standards/ddd/repositories.md)

**6 — The application service**, in `application`. The six steps, no business
rules, one aggregate per transaction, and its non-repository ports declared in
the same package.
→ [`ddd/application-services.md`](../../standards/ddd/application-services.md)

**7 — Adapters.** Inbound maps transport to the use case and errors back to
status codes. Outbound implements the ports. Every driver concern stops here.

If this slice consumes another context's event, the **ACL is an adapter** —
`adapters/inbound/events/<upstream>.go`, translating published types into this
context's value objects and deduplicating on the message id. If it calls another
context, the client is `adapters/outbound/<downstream>/`, satisfying an
interface **this** context declared.
→ [`modular-monolith/communication.md`](../../standards/modular-monolith/communication.md)

**8 — Schema.** A new table or column is a migration in this context's
`migrations/`, numbered within this context. No foreign key to another context's
schema; another context's identifier is a plain column.
→ [`modular-monolith/data.md`](../../standards/modular-monolith/data.md)

**9 — Composition.** Wiring only, in this context's facade — and in
`internal/composition/` if the context gained a dependency. It may import
everything; nothing imports it.
→ [`modular-monolith/composition.md`](../../standards/modular-monolith/composition.md)

## Doubles

`/tdd` doubles at system boundaries only, and never your own code. In this
layout that resolves exactly:

| Thing | Doubled? |
|---|---|
| Repository port | **Yes** — an in-memory fake. It is the database boundary |
| Clock, ID generator, message publisher, external service port | **Yes** — same reason |
| Aggregate, value object, domain service | **Never.** Code you own, and pure. Use the real one |
| Application service | **Never.** It is the seam under test, not a collaborator |

The in-memory fake is not a testing convenience. It is the second adapter that
makes the port a real seam rather than a hypothetical one — see
[`vocabulary.md`](../../standards/vocabulary.md).

The full table, including what a fake must guarantee, is
[`clean-code/tests.md`](../../standards/clean-code/tests.md) — the fake returns
the **same errors** as the real adapter, or every test that passes against it
passes on a lie.

## Checks before you call it done

Run these deliberately before handing off to `/code-review`. They are the
findings that come back most often:

- [ ] `domain` imports nothing but stdlib and its own context's `domain`
- [ ] No struct tag, no `context.Context` (outside repository interfaces), no
      `any`, no framework type anywhere in `domain`
- [ ] No exported field and no setter on an aggregate
- [ ] A slice or map returned from `domain` is a copy, not the internal one
- [ ] One aggregate saved per transaction
- [ ] Events released and written to the outbox **inside** the same transaction
      as the aggregate — never published to a broker inside a transaction, and
      never published after it commits
- [ ] Every port is on the side that needs it: repositories in `domain`,
      the rest in `application`
- [ ] `application` contains no conditional that reads aggregate state to
      decide a business outcome
- [ ] Errors are sentinels or typed values, wrapped with `%w`, mapped to
      transport only in the inbound adapter
- [ ] Every new term is in `CONTEXT.md`
- [ ] Every new exported identifier has a doc comment beginning with its name,
      and each new aggregate states its invariant in one sentence
      → [`clean-code/comments.md`](../../standards/clean-code/comments.md)
- [ ] No third-party type in `domain` or `application`; clock, IDs and config
      arrive as ports or values
      → [`clean-code/boundaries.md`](../../standards/clean-code/boundaries.md)
- [ ] No SQL added by this slice names a table outside this context's schema,
      and no new foreign key crosses one
- [ ] Nothing imports another context's facade package; a cross-context call
      goes through an interface this context declared
      → [`modular-monolith/modules.md`](../../standards/modular-monolith/modules.md), rule 6
- [ ] A cross-context event is a `published/` type, recorded to this context's
      outbox in the aggregate's transaction, and consumed through an ACL that
      deduplicates on the message id
- [ ] Nothing new under `internal/platform/` would change because a business
      rule changed

Then read
[`ddd/anti-patterns.md`](../../standards/ddd/anti-patterns.md) — its review
heuristics list is a thirty-second pass that catches most of what remains — and
[`clean-code/smells.md`](../../standards/clean-code/smells.md) for the same
sweep at the level of code rather than model.

**Do not restructure to satisfy a rule this standard does not hold.** Function
length, repeated `if err != nil` and type switches over a closed set are
conformant Go; [`clean-code.md`](../../standards/clean-code.md) lists every
_Clean Code_ rule that is deliberately not applied here.

## When the standard and the ticket conflict

Stop and say so. Do not quietly pick the middle. Either the ticket changes, or
the rule is overruled by an ADR written with `/domain-modeling`. Silently
splitting the difference is what produces code that looks like DDD and is not.

If the conflict is that the ticket's model is wrong — a rule placed in the
application layer, a boundary that cannot hold its invariant — that is a spec
defect, not an implementation decision. Say which decision in the spec is wrong
and what it should be.
