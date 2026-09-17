---
name: standard
description: The binding standard for Domain-Driven Design, Clean Architecture, Clean Code and the modular monolith in Go. Use when modelling a domain, laying out a project, deciding which layer, package or bounded context something belongs in, naming a type, placing a port or interface, checking dependency direction, wiring a composition root, or answering "how should this be done" about aggregates, entities, value objects, repositories, domain events, application services, read models, modules or bounded contexts. Also the standards source any review, spec or implementation should cite in a Go DDD project.
---

# The archify standard

This plugin is the source of truth for **how a Go domain is modelled**. A rule
written in `standards/` binds; a rule not written there does not. When a page
and your instinct disagree, the page wins — and if the page is wrong, the page
gets changed, not bypassed.

**The corpus lives at `../../standards/` relative to this skill.** Read the page
you need. Do not work from memory of DDD: the specific rules here differ from
the folk version in ways that matter.

## Where this sits

archify is **not a workflow**. The workflow is Matt Pocock's skills — the flow
`/ask-matt` maps, from `/grill-with-docs` through `/to-spec`, `/to-tickets`,
`/implement`, `/tdd` and `/code-review`. archify runs *underneath* that flow, in
the same layer as `/codebase-design` and `/domain-modeling`: a reference the
flow pulls in, never a replacement for a step of it.

| At this point in the flow | archify supplies |
|---|---|
| `/to-spec`, `/to-tickets` | [`archify:modelling-decisions`](../modelling-decisions/SKILL.md) — the decisions the Implementation Decisions and Testing Decisions sections must carry |
| `/implement`, `/tdd` | [`archify:writing-order`](../writing-order/SKILL.md) — the order that makes a dependency error unwritable, and where the test seam is |
| `/code-review` | [`archify:review-passes`](../review-passes/SKILL.md) — the Standards axis source, and how it interacts with the Fowler smell baseline |
| before any of it | [`archify:setup`](../setup/SKILL.md) — layout, depguard, and the `CODING_STANDARDS.md` that `/code-review` reads |

Two rules keep them from fighting:

- **Never replace a flow step with an archify skill.** If the user wants a spec,
  run `/to-spec` and let it pull this in. archify decides *what the spec says
  about the model*, not whether there is a spec.
- **Never re-explain the other plugin's words.**
  [`vocabulary.md`](../../standards/vocabulary.md) maps its terms to these and
  says which meaning is live where they collide. Read it before arguing that two
  standards contradict each other — twice out of three times they do not.

## Precedence

Three authorities disagree. Averaging them is what produces the mediocre result,
so the order is fixed:

| Question | Authority |
|---|---|
| Tactical design — aggregates, repositories, events, factories | **Vernon**, _Implementing DDD_ |
| Strategic design — contexts, context maps, language | **Evans**, the blue book |
| Dependency direction | **Martin**, _Clean Architecture_ |
| `port` / `adapter` terminology | **Cockburn** |
| Code-level style — naming, functions, comments, tests | **Martin**, _Clean Code_, filtered |
| Project layout, and how contexts are packaged and deployed | **This standard's own**, on Evans ch. 14 and **Newman**, _Monolith to Microservices_ |
| Go idiom, where it collides with any of the above | **Go wins** |

Where DDD and Clean Architecture collide on names, **DDD's names win**. You
write `Aggregate` and `Application Service`. You never write `Entity` in
Martin's sense, and you never write `Interactor`.

## The map

| Read this | When |
|---|---|
| [`structure.md`](../../standards/structure.md) | Where a file goes **inside one context**, and which way a dependency points |
| [`modular-monolith.md`](../../standards/modular-monolith.md) | The default architecture: what a module is, and the six properties |
| [`vocabulary.md`](../../standards/vocabulary.md) | A word means two things, or another standard looks like it contradicts this one |
| [`domain-driven-design.md`](../../standards/domain-driven-design.md) | Entry point and index for the model |
| [`clean-code.md`](../../standards/clean-code.md) | Entry point for style — **and the list of _Clean Code_ rules not applied in Go** |
| [`ddd/aggregates.md`](../../standards/ddd/aggregates.md) | Consistency boundaries, transaction scope |
| [`ddd/value-objects.md`](../../standards/ddd/value-objects.md) | The default building block — read before reaching for an entity |
| [`ddd/entities.md`](../../standards/ddd/entities.md) | Identity, typed identifiers |
| [`ddd/repositories.md`](../../standards/ddd/repositories.md) | Loading and saving aggregates |
| [`ddd/domain-events.md`](../../standards/ddd/domain-events.md) | Facts, and the outbox rule |
| [`ddd/application-services.md`](../../standards/ddd/application-services.md) | Use cases, transaction boundaries |
| [`ddd/domain-services.md`](../../standards/ddd/domain-services.md) | Behaviour belonging to no aggregate |
| [`ddd/specifications.md`](../../standards/ddd/specifications.md) | A named rule asked as a question |
| [`ddd/factories.md`](../../standards/ddd/factories.md) | Construction that is itself a concept |
| [`ddd/read-models.md`](../../standards/ddd/read-models.md) | Queries that are not aggregates |
| [`ddd/errors.md`](../../standards/ddd/errors.md) | A broken rule as a Go value |
| [`ddd/bounded-contexts.md`](../../standards/ddd/bounded-contexts.md) | Where one model ends |
| [`ddd/context-mapping.md`](../../standards/ddd/context-mapping.md) | Relationships between contexts, ACLs |
| [`ddd/ubiquitous-language.md`](../../standards/ddd/ubiquitous-language.md) | Naming, and `CONTEXT.md` |
| [`ddd/anti-patterns.md`](../../standards/ddd/anti-patterns.md) | Fast check before finishing |
| [`clean-code/naming.md`](../../standards/clean-code/naming.md) | Naming anything the glossary does not decide |
| [`clean-code/functions.md`](../../standards/clean-code/functions.md) | Function shape — and why length is not a rule here |
| [`clean-code/comments.md`](../../standards/clean-code/comments.md) | Doc comments, which are mandatory, not a failure |
| [`clean-code/error-handling.md`](../../standards/clean-code/error-handling.md) | Errors outside the model: wrapping, translation, `panic` |
| [`clean-code/tests.md`](../../standards/clean-code/tests.md) | What a test looks like, and what may be doubled |
| [`clean-code/boundaries.md`](../../standards/clean-code/boundaries.md) | Depending on third-party code |
| [`clean-code/solid.md`](../../standards/clean-code/solid.md) | When a review argument turns abstract |
| [`clean-code/smells.md`](../../standards/clean-code/smells.md) | The heuristics sweep, and the Fowler baseline |
| [`modular-monolith/layout.md`](../../standards/modular-monolith/layout.md) | **The canonical project tree** — every directory, and what never goes in it |
| [`modular-monolith/modules.md`](../../standards/modular-monolith/modules.md) | A context's facade, its published surface, and how many contexts to have |
| [`modular-monolith/communication.md`](../../standards/modular-monolith/communication.md) | One context talking to another in the same process |
| [`modular-monolith/data.md`](../../standards/modular-monolith/data.md) | Schema per context, migrations, and the transaction rule |
| [`modular-monolith/composition.md`](../../standards/modular-monolith/composition.md) | `main`, wiring, config, lifecycle, shutdown |
| [`modular-monolith/platform.md`](../../standards/modular-monolith/platform.md) | What may live in `internal/platform/`, and what never may |
| [`modular-monolith/enforcement.md`](../../standards/modular-monolith/enforcement.md) | depguard, the architecture test, and what no tool catches |
| [`modular-monolith/extraction.md`](../../standards/modular-monolith/extraction.md) | Turning a context into a service — and whether to |

## The rules that get broken most

These six cause the most rework. They apply whether or not you opened a page:

1. **`domain` imports stdlib and its own context's `domain`. Nothing else.** No
   framework, no driver, no struct tag, no `context.Context` except on a
   repository interface.
2. **A repository interface lives in `domain`, beside its aggregate. Every other
   port lives in `application`, beside the use case that needs it.** This is the
   single most common misplacement, and it is not a matter of taste — see
   [`structure.md`](../../standards/structure.md).
3. **One aggregate per transaction.** Two `Save` calls in one transaction is a
   design error, not a performance note.
4. **An aggregate is never constructed invalid.** No zero-value struct literal,
   no setters, no exported fields.
5. **A context owns its schema exclusively.** No cross-context join, no
   cross-context foreign key, no transaction touching two contexts. **Nothing in
   the import graph reveals any of these** — it is the most common way a
   boundary that looks enforced is not. See
   [`modular-monolith/data.md`](../../standards/modular-monolith/data.md).
6. **A context never imports another context's facade package.** It declares the
   interface it needs; the composition root satisfies it. This one line is what
   makes extracting a context a deployment change rather than a rewrite. See
   [`modular-monolith/modules.md`](../../standards/modular-monolith/modules.md),
   rule 6.

## Working with the standard

- **Cite the page** when you apply a rule: "repositories.md rule 4". A claim
  without a citation is an opinion, and this plugin exists to replace opinions.
- **Read before writing.** Two pages, actually opened, beat a recalled summary.
- **Use the project's `CONTEXT.md` for names.** The standard says the language
  must be ubiquitous; only the project knows what it is. `CONTEXT.md` is owned
  by `/domain-modeling` — run it to change the glossary rather than editing the
  file freehand, and keep to its format.

## Departing from a rule

A project may overrule any page. The departure is recorded as an ADR in that
project's `docs/adr/` via `/domain-modeling`, naming the rule and arguing the
trade-off. It qualifies under that skill's own bar without argument: a
deliberate deviation from the obvious path is one of the cases it names.

**A deviation without an ADR is a defect,** not a style choice. An ADR-backed
departure is settled and is never reported as a finding.
