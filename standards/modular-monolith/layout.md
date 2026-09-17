# Layout

The project tree. This is not a suggestion and it is not a starting point to
adapt — **it is the layout every Go project held to this standard uses**, so
that a file's path answers what it is allowed to import before anyone opens it.

**Authorities.** The Go team's own [module layout guidance][layout], which is
deliberately thin and leaves everything below the module root open. Everything
this page adds on top is this standard's own and says so. Fowler,
_PresentationDomainDataLayering_, for why the top level is **not** split by
technical concern.

Read [`../structure.md`](../structure.md) for what happens **inside** one
context; this page places the contexts and everything around them.

## The tree

```text
myapp/
├── go.mod                              one module, for the whole repository
├── go.sum
├── Makefile                            the commands CI runs, runnable locally
├── README.md
├── CODING_STANDARDS.md                 the seam /code-review discovers
├── CONTEXT-MAP.md                      which contexts exist and how they relate
├── .golangci.yml                       depguard: the dependency rule, as lint
├── .github/workflows/ci.yml
│
├── api/
│   └── openapi.yaml                    the published HTTP contract, if there is one
├── deploy/
│   ├── Dockerfile
│   └── docker-compose.yml              the dependencies a developer needs locally
├── docs/
│   ├── adr/                            every deviation from this standard
│   └── agents/                         issue tracker, triage labels, domain docs
│
├── cmd/
│   └── app/
│       └── main.go                     flags, signals, exit code. Nothing else
│
├── internal/
│   ├── composition/                    the binary's composition root
│   │   ├── app.go                      build everything, return something Run-able
│   │   ├── config.go                   the whole program's configuration, one struct
│   │   ├── contexts.go                 the module list. The only file that knows it
│   │   ├── router.go                   mount each context's routes under its prefix
│   │   └── lifecycle.go                start order, shutdown order, health
│   │
│   ├── contexts/
│   │   ├── ordering/
│   │   │   ├── CONTEXT.md              this context's glossary
│   │   │   ├── ordering.go             THE FACADE. The only non-published export
│   │   │   ├── published/              the published language. Other contexts may import this
│   │   │   │   ├── events.go
│   │   │   │   └── ids.go
│   │   │   ├── migrations/             this context's schema, owned by nobody else
│   │   │   │   ├── 0001_create_schema.sql
│   │   │   │   └── 0002_create_orders.sql
│   │   │   └── internal/               ← the compile-time wall
│   │   │       ├── domain/
│   │   │       │   └── order/          one package per aggregate
│   │   │       │       ├── order.go        the aggregate root
│   │   │       │       ├── line.go         its entities
│   │   │       │       ├── id.go           typed identifiers
│   │   │       │       ├── money.go        value objects
│   │   │       │       ├── status.go
│   │   │       │       ├── events.go       domain events
│   │   │       │       ├── errors.go       sentinels and typed errors
│   │   │       │       ├── repository.go   the repository interface. Here, not elsewhere
│   │   │       │       └── order_test.go
│   │   │       ├── application/         two packages, and never a .go file here
│   │   │       │   ├── command/             the write side
│   │   │       │   │   ├── place_order.go       the use case, and the ports only it needs
│   │   │       │   │   ├── place_order_test.go
│   │   │       │   │   ├── cancel_order.go
│   │   │       │   │   ├── unit_of_work.go      a port every use case needs
│   │   │       │   │   ├── outbox.go
│   │   │       │   │   ├── clock.go
│   │   │       │   │   └── ids.go
│   │   │       │   └── query/               the read side. Imports no domain
│   │   │       │       ├── list_customer_orders.go  the query, its view, its port
│   │   │       │       └── order_detail.go
│   │   │       └── adapters/
│   │   │           ├── inbound/
│   │   │           │   ├── http/           handlers, routes, DTOs, status mapping
│   │   │           │   └── events/         subscribers + the ACL for each upstream
│   │   │           └── outbound/
│   │   │               ├── postgres/       repository and read-model implementations
│   │   │               ├── memory/         the in-memory fake that makes the port a seam
│   │   │               └── billing/        outbound ACL: calling the billing context
│   │   ├── shipping/                   identical shape
│   │   └── billing/                    identical shape
│   │
│   └── platform/                       technical, no domain meaning. See platform.md
│       ├── config/
│       ├── postgres/
│       ├── outbox/
│       ├── eventbus/
│       ├── httpx/
│       ├── observability/
│       └── testsupport/
│
└── test/
    └── e2e/                            black-box tests against the built binary
```

## The rules

1. **One `go.mod`, at the repository root.** Not one per context, not a
   workspace. A second `go.mod` buys independent versioning between contexts —
   which is a cost of distribution, taken without the benefit, and it deletes
   the compile-time boundary because `internal/` stops applying across module
   lines.

2. **Everything is under `internal/`.** There is no `pkg/`. A product has no
   external importers, so "public" means "importable by the next person who is
   in a hurry". `pkg/` is not a Go convention; the directory that *is* a Go
   convention is `internal/`, and it does real work.

3. **The top level of `internal/` is three entries: `composition/`,
   `contexts/`, `platform/`.** Adding a fourth is a design decision, not a
   convenience, and it needs an ADR. In particular there is no
   `internal/models/`, `internal/services/`, `internal/handlers/`,
   `internal/repositories/` or `internal/db/`.

4. **`internal/contexts/<name>/` is a bounded context, named for the business.**
   Lower case, one word where possible, no underscores, no `-service` suffix.
   → [`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md), rule 4

5. **Every context has the same five entries** and no others:
   `CONTEXT.md`, `<name>.go`, `published/`, `migrations/`, `internal/`. A sixth
   entry is a finding — whatever it is, it belongs inside `internal/`.

6. **The nested `internal/` is load-bearing, not decorative.** `go` permits a
   package under `a/internal/b` to be imported only from within `a`. So
   `shipping` cannot import `ordering`'s domain: it fails `go build`, not
   review. This is property 2 of a modular monolith and it is free.

7. **`cmd/app/main.go` holds flags, signal handling and the exit code.**
   Everything else is `internal/composition/`. `main` is untestable by
   construction, so it holds as close to nothing as possible.
   → [composition](./composition.md)

8. **One binary.** Run modes are subcommands — `app serve`, `app worker`,
   `app migrate` — not separate `cmd/` directories. Several binaries means
   several composition roots, and they drift. A second `cmd/` entry needs an
   ADR, and is usually the first step of an extraction.

9. **Migrations live with the context that owns the schema**, numbered within
   that context and applied by the runner in `platform/postgres`. There is no
   repository-wide `migrations/` directory, because there is no
   repository-wide schema.
   → [data](./data.md)

10. **Tests live beside the code they test**, in the same package where they
    test unexported behaviour and in `package foo_test` where they test the
    public surface. `testdata/` beside the test that reads it. The only
    top-level test directory is `test/e2e/`, for tests that drive the built
    binary over its real transports.

11. **A file is named for what is in it, in the singular** —
    `place_order.go`, `order.go`, `money.go`. Never `models.go`, `types.go`,
    `helpers.go`, `utils.go`, `common.go`, `manager.go`.
    → [`../clean-code/formatting.md`](../clean-code/formatting.md)

12. **`application/` is two packages — `command/` and `query/` — and holds no
    Go file of its own.** The two halves have disjoint dependencies: a command
    needs the repository, the transaction and the outbox; a query needs none of
    them and must not acquire them. Flat, that is something review has to
    notice; split, it is an import, and lint states it.
    → [`../ddd/application-services.md`](../ddd/application-services.md)

13. **`CONTEXT-MAP.md` at the root lists the contexts and the relationship
    between each pair.** It is owned by `/domain-modeling` in its multi-context
    layout; this standard adds only that every directory under
    `internal/contexts/` appears in it.

## What goes where

| Directory | Holds | Never holds |
|---|---|---|
| `cmd/app/` | Flag parsing, signal handling, `os.Exit` | Construction, HTTP routes, SQL, business logic |
| `internal/composition/` | Config loading, dependency construction, the module list, route mounting, start/stop order | Anything a context should own. No rule, no query, no handler |
| `internal/contexts/<c>/<c>.go` | The facade: `New(...)`, the methods other code may call, `Routes()`, `Run()` | Business logic. It delegates and it constructs |
| `internal/contexts/<c>/published/` | Event structs, typed identifiers, the version marker. Pure data with JSON tags | Behaviour, domain types, anything one consumer asked for |
| `internal/contexts/<c>/migrations/` | `NNNN_name.sql` for this context's schema only | A table another context reads. A cross-schema foreign key |
| `.../internal/domain/<agg>/` | The aggregate, its entities, value objects, events, errors, the repository interface | Struct tags, `context.Context` outside the repository interface, drivers, `time.Now()`, `any` |
| `.../internal/application/` | Two directories, `command/` and `query/` | A `.go` file. A third directory, without an ADR |
| `.../internal/application/command/` | Use cases that change state, the commands they take, the non-repository ports they call, the transaction boundary | Business rules, SQL, HTTP, another context's anything |
| `.../internal/application/query/` | Read models, the query ports that answer them, their handlers | The write model. It imports no `domain` package and no repository |
| `.../internal/adapters/inbound/` | HTTP handlers, event subscribers, CLI, and the ACL translating each upstream's published language | Business rules. Decisions that belong to the model |
| `.../internal/adapters/outbound/` | Postgres, the in-memory fake, message publishing, HTTP clients, and the outbound ACL for each downstream context | Anything importable from `domain` or `application` |
| `internal/platform/` | Config, the DB pool, the outbox runner, the in-process bus, HTTP middleware, telemetry, test helpers | Any type that would change because a **business rule** changed → [platform](./platform.md) |
| `test/e2e/` | Tests that start the binary and talk to it over HTTP | Unit tests. Anything importing `internal/contexts/*/internal/...` — it cannot, and should not want to |

## Two composition roots, and they are different

This is the one place [`structure.md`](../structure.md)'s four-region table
needs an explicit reading. It lists `composition` as a region of a context. In a
modular monolith there are **two** levels of it, and conflating them is how
`internal/composition/` ends up holding business logic:

| | Knows | Builds |
|---|---|---|
| `internal/contexts/ordering/ordering.go` | Only ordering | Ordering's adapters and application services. Returns the facade |
| `internal/composition/` | Every context, and platform | The DB pool, the logger, the bus — then calls each context's `New` and wires the results together |

The rule that follows: **`internal/composition/` never reaches past a facade.**
It cannot — the nested `internal/` forbids it — and the value of the facade is
exactly that it makes the wiring impossible to get wrong rather than merely
discouraged.

## The single-context project

Most projects start with one context, and the answer is **the same tree with one
directory under `contexts/`**. Not a flattened variant to be restructured later;
the whole point is that the second context costs one `mkdir`.

```text
internal/
├── composition/
├── contexts/
│   └── ordering/            ← the only one, for now
└── platform/
```

Do not create a second context because the layout has room for it.
→ [modules](./modules.md)

## Wrong, and why

| Layout | What it actually is |
|---|---|
| `internal/handlers/`, `internal/services/`, `internal/repositories/` | The whole application layered by technical concern. Every feature is spread across three directories and no boundary appears anywhere |
| `internal/modules/ordering/` | The right idea with the wrong word — `module` means `go.mod` and it means a package. Use `contexts/` |
| `internal/contexts/shared/` | A fourth model that nobody owns and everybody edits → [`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md) |
| `pkg/ordering/` | Importable by anything, including the next repository. The boundary is gone before it was drawn |
| `internal/contexts/ordering/domain/` (no nested `internal/`) | Looks identical in the file tree and enforces nothing. `shipping` can now import `order.Order`, and one day will |
| `migrations/` at the root | One schema pretending to be several. The first cross-context foreign key is now one line away |
| `cmd/ordering/`, `cmd/shipping/` | Several binaries, several composition roots, and a distributed system whose authors have not said so |
| `internal/platform/domain/` | Something with domain meaning in the place reserved for things without it |
| `application/` as one flat package, with `ports.go` and `queries.go` | Two files named for a kind, which is where a type goes when nobody decided. And the read side can now reach the write model |
| `application/port/`, `application/dto/`, `application/shared/` | Grouping by kind one level further in. The interface is now separated from its only caller, which is the one thing a consumer-side port must not be |

## Adopting this in an existing project

Do not move every file. That restructure is where adoption stalls, and it makes
one enormous unreviewable diff out of work that could have been a ratchet.

1. Create `internal/contexts/<new>/` with the full shape for **new** work only.
2. Write `CODING_STANDARDS.md` and `.golangci.yml`; scope depguard's rules to
   the new paths so the build goes green immediately.
3. Record the existing directories in an ADR as **inherited**, and list them
   under `CODING_STANDARDS.md`'s *Inherited* heading so reviews stop reporting
   them.
4. Move an existing context only when you are already changing it substantially,
   and move it whole.

→ [`../../skills/setup/SKILL.md`](../../skills/setup/SKILL.md) automates 2 and 3.

## Checklist

- [ ] Exactly one `go.mod`, at the root
- [ ] No `pkg/` directory
- [ ] `internal/` contains `composition/`, `contexts/`, `platform/` and nothing else
- [ ] Every directory under `contexts/` has `CONTEXT.md`, `<name>.go`, `published/`, `migrations/`, `internal/`, and nothing else
- [ ] Every context's interior is behind a nested `internal/`
- [ ] One `cmd/` directory; run modes are subcommands
- [ ] Migrations are per context; there is no root `migrations/`
- [ ] `application/` is `command/` and `query/`, with no `.go` file of its own
- [ ] No file named `models.go`, `types.go`, `utils.go`, `helpers.go`,
      `common.go`, `ports.go` or `queries.go`
- [ ] Every context appears in `CONTEXT-MAP.md`

## Sources

**Books.** Sam Newman, _Monolith to Microservices_, ch. 1, for module boundaries
in one deployable. Martin Fowler, _Patterns of Enterprise Application
Architecture_, ch. 1, for the layering this page's top level deliberately
refuses.

**Online.** Every link below was reachable when this page was written.

- [Organizing a Go module](https://go.dev/doc/modules/layout) — the Go team's
  own layout guidance. It is short on purpose, and it does not contain `pkg/`
- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — the
  visibility rule rules 2 and 6 depend on
- [Go Modules Reference](https://go.dev/ref/mod) — why rule 1 is one `go.mod`
- [Package names](https://go.dev/blog/package-names) — why `domain/order` beats
  `domain/models`
- [Avoid package names like base, util, or common](https://dave.cheney.net/2019/01/08/avoid-package-names-like-base-util-or-common)
  — Cheney; the argument behind rules 3 and 11
- [golang-standards/project-layout](https://github.com/golang-standards/project-layout)
  — cited because it is the most-copied Go layout and **this standard does not
  follow it**: it is not from the Go team, and its `pkg/` convention is
  explicitly rejected by rule 2
- [Standard Package Layout](https://www.gobeyond.dev/standard-package-layout/)
  — Ben Johnson; the dependency-shaped alternative, and the closest published
  Go layout to this one
- [PresentationDomainDataLayering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html)
  — Fowler, on why the technical-concern top level in the *Wrong* table above
  keeps being chosen and keeps failing

[layout]: https://go.dev/doc/modules/layout
