# Data

One database instance. One schema per context. No exceptions that are not an
ADR.

**Authorities.** Evans, ch. 14, rule 3 — a context owns its persistence. Sam
Newman, _Monolith to Microservices_, ch. 4, which is the best treatment of
splitting a schema without splitting a deployment. Richardson's
_Database per service_, read as *schema per context*: the isolation is the
point, the process count is not.

Read [`../ddd/bounded-contexts.md`](../ddd/bounded-contexts.md) for why the
boundary exists. This page is how it is held at runtime, which is the half that
gets lost.

## Why this is where the boundary actually dies

A cross-context import fails `go build`. A cross-context **join** compiles,
passes review, ships, and is discovered two years later when one context cannot
be changed without the other.

> **Nothing in the import graph reveals a join.** The directory structure looks
> correct, the linter is green, and the boundary exists only at compile time
> while the runtime has none. This is the most common way a modular monolith is
> modular in appearance only.

Everything below exists to make that failure impossible rather than
discouraged.

## The rules

1. **One schema per context**, named for the context: `ordering`, `shipping`,
   `billing`. Not a table-name prefix — a prefix is a naming convention, a
   schema is a permission boundary.
2. **One database role per context**, granted usage on its own schema and
   nothing else. This is what turns rule 3 from a review item into an error the
   database raises.
3. **No cross-schema read.** No `SELECT` naming another context's table, no
   view over one, no function that reads one.
4. **No cross-schema foreign key.** A reference to another context is an
   identifier column with no constraint behind it, and the integrity is
   maintained by the ACL that accepted it, not by the database.
5. **No transaction spans two contexts.** Not through a shared `*sql.Tx`, not
   through a unit of work, not through `context.Context`.
6. **Migrations belong to the context** that owns the schema, in
   `internal/contexts/<c>/migrations/`, numbered within that context. There is
   no repository-wide migration sequence, because there is no repository-wide
   schema.
7. **The outbox table lives in the context's own schema.** It is that context's
   data. → [communication](./communication.md)
8. **A context reads other contexts' data by keeping its own copy**, built from
   subscribed events. That copy is this context's data and is modelled in this
   context's words.
9. **A read model that spans contexts belongs to a context that owns the
   question** — usually a reporting context that subscribes to everything and
   owns a denormalised schema of its own.
   → [`../ddd/read-models.md`](../ddd/read-models.md)
10. **Reference data with no domain meaning** — currency codes, country codes,
    time zones — is platform or is duplicated. It is never a shared table that
    two contexts join to.
11. **Each context's adapter tests run against that context's schema only.**
    A fixture that inserts into two schemas is a test of something this standard
    forbids.
12. **`search_path` is set per connection, not per statement.** Application SQL
    does not qualify table names with a schema, so a query that reaches outside
    its own schema fails rather than silently succeeding.

## The schema

```sql
-- internal/contexts/ordering/migrations/0001_create_schema.sql
CREATE SCHEMA IF NOT EXISTS ordering;

-- The role the application connects as when it is acting for this context.
-- It cannot see shipping or billing, and that is enforced here rather than
-- reviewed in a pull request.
CREATE ROLE app_ordering LOGIN PASSWORD :'ordering_password';
GRANT USAGE ON SCHEMA ordering TO app_ordering;
ALTER DEFAULT PRIVILEGES IN SCHEMA ordering
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_ordering;
```

```sql
-- internal/contexts/ordering/migrations/0002_create_orders.sql
CREATE TABLE ordering.orders (
    id           uuid PRIMARY KEY,
    customer_id  uuid        NOT NULL,   -- identity's aggregate. No FK: another context
    status       text        NOT NULL,
    total_minor  bigint      NOT NULL,
    currency     char(3)     NOT NULL,
    version      bigint      NOT NULL,   -- optimistic concurrency
    placed_at    timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ordering.outbox (
    id           uuid PRIMARY KEY,
    topic        text        NOT NULL,
    payload      jsonb       NOT NULL,
    occurred_at  timestamptz NOT NULL,
    published_at timestamptz
);

CREATE INDEX ON ordering.outbox (published_at) WHERE published_at IS NULL;
```

`customer_id` has no foreign key and that is deliberate, not an oversight worth
a comment in review. The identity context owns customers; ordering holds an
identifier it validated at its ACL when it accepted it.

## One pool per context

The composition root builds a pool per context, each connecting as that
context's role with its own `search_path`:

```go
// internal/composition/database.go
func pools(ctx context.Context, cfg Config) (map[string]*pgxpool.Pool, error) {
	out := make(map[string]*pgxpool.Pool, len(cfg.Contexts))
	for name, c := range cfg.Contexts {
		// search_path is the enforcement: unqualified SQL in this context can
		// only resolve to this context's schema.
		dsn := fmt.Sprintf("%s?search_path=%s", c.DSN, name)
		p, err := pgxpool.New(ctx, dsn)
		if err != nil {
			return nil, fmt.Errorf("pool for %s: %w", name, err)
		}
		out[name] = p
	}
	return out, nil
}
```

Then `ordering.New(ordering.Deps{DB: pools["ordering"], ...})`. The context
receives a handle that cannot reach anything else, and extraction changes a DSN
rather than a query.

**The permitted fallback:** one shared pool and one role, with SQL that
qualifies table names. It is simpler, it is what most projects already have, and
it makes rules 3 and 4 review-only. Take it deliberately and record it as an
ADR — not by default, and never without knowing which enforcement you gave up.

## Transactions

A transaction is opened by one context's outbound adapter, used by one
application service, and closed before control leaves that context. It is never
a parameter to anything outside the context that opened it.

```go
// Correct: the unit of work is one use case in one context. The aggregate and
// the events it produced commit together; nothing else is in scope.
func (s *PlaceOrder) Handle(ctx context.Context, cmd PlaceOrder) error {
	return s.uow.Do(ctx, func(ctx context.Context) error {
		o, err := order.Place(cmd.OrderID, cmd.CustomerID, cmd.Lines, s.clock.Now())
		if err != nil {
			return err
		}
		if err := s.orders.Save(ctx, o); err != nil {
			return err
		}
		return s.outbox.Record(ctx, o.ReleaseEvents()) // same transaction
	})
}
```

Three constraints hold on that block and they are the whole of the rule:

- **One aggregate is saved in it.**
  → [`../ddd/aggregates.md`](../ddd/aggregates.md)
- **The events go to this context's outbox inside it.**
  → [`../ddd/domain-events.md`](../ddd/domain-events.md), rule 7
- **Nothing in another context is touched by it** — not a table, not a facade,
  not a publish to a broker.

The transaction handle itself travels in the `context.Context` between the
application service and this context's own repository adapter, and the
application service never names `*pgx.Tx`. That keeps `application` free of the
driver while keeping the boundary honest: the handle is invisible outside the
context because nothing outside the context is ever called inside the block.

## Migrations

Each context owns a numbered sequence. A platform runner walks the contexts and
applies each in its own schema, with its own version table:

```go
// internal/platform/postgres/migrate.go
//
// Applies each context's migrations in its own schema, tracked in its own
// version table. Contexts are independent: ordering at 0007 and shipping at
// 0002 is a normal, correct state.
func Migrate(ctx context.Context, cfg Config, sets map[string]fs.FS) error {
	for name, files := range sets {
		if err := applySchema(ctx, cfg.AdminDSN, name, files); err != nil {
			return fmt.Errorf("migrating %s: %w", name, err)
		}
	}
	return nil
}
```

```go
// internal/contexts/ordering/ordering.go
//
//go:embed migrations/*.sql
var migrations embed.FS

// Migrations is ordering's schema, for the migration runner. It is the one
// thing besides the facade and published/ that leaves this directory, and it
// leaves as bytes.
func Migrations() fs.FS { return migrations }
```

**Numbering is per context.** Two contexts both having an `0003` is correct and
expected; a global sequence would mean every branch that adds a migration
conflicts with every other, which is the coordination cost the boundary was
supposed to remove.

## Reading across contexts

Three options, in order of preference. **Joining is not one of them.**

| Option | When | Cost |
|---|---|---|
| **Subscribe and keep a local copy** — the context stores what it needs, in its own words, updated from events | The default. Almost every case | Eventual consistency, and a projection to maintain |
| **A reporting context** that subscribes to everything and owns a denormalised schema | Cross-context questions that are genuinely a business capability — dashboards, statements, exports | A whole context, and a second model of everything it covers |
| **A synchronous query** through the upstream's published API | The answer is needed to serve the request in hand, and staleness is unacceptable | An availability coupling, and an ADR → [communication](./communication.md) |

Analytics and BI are a fourth thing and not an application concern: replicate
out, and let the warehouse join whatever it likes. A warehouse joining across
schemas is reading a snapshot; an application joining across schemas is
pretending the boundary is not there.

## Wrong, and why

```sql
-- Wrong: the join. Shipping has deleted its boundary at runtime while
-- appearing to have one at compile time. Nothing in the import graph shows it.
SELECT s.id, o.total_minor
FROM shipping.shipments s
JOIN ordering.orders o ON o.id = s.order_id;
```

```sql
-- Wrong: the cross-context foreign key. Ordering can no longer be migrated,
-- backfilled or extracted without shipping's permission.
ALTER TABLE shipping.shipments
    ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES ordering.orders (id);
```

```sql
-- Wrong: the shared table with a discriminator column. Two contexts, one
-- schema, one lock, and a column that is meaningless in half its rows.
CREATE TABLE public.documents (
    id       uuid PRIMARY KEY,
    kind     text NOT NULL,     -- 'order' | 'invoice' | 'shipment'
    payload  jsonb NOT NULL
);
```

```go
// Wrong: the transaction crosses. One rollback now spans two schemas, and
// neither context can be extracted without a rewrite.
tx, _ := pool.Begin(ctx)
_ = ordering.SaveWithin(ctx, tx, o)
_ = billing.SaveWithin(ctx, tx, inv)
_ = tx.Commit(ctx)
```

```go
// Wrong: the shared repository. It compiles because both contexts were given
// the same pool, and it is the join above with a Go accent.
type Reports struct{ db *pgxpool.Pool }

func (r Reports) OrdersWithShipments(ctx context.Context) ([]Row, error) { ... }
```

## Migrating an existing shared schema

The tables are already in `public` and everything joins to everything. The order
below is the one that keeps the build green at every step:

1. **Assign every table to exactly one context**, on paper, and write the list
   into the ADR. A table two contexts both claim is the real finding — resolve
   the model before touching SQL.
2. **Create the schemas** and move each table with `ALTER TABLE ... SET SCHEMA`,
   leaving a view in `public` behind it so nothing breaks yet.
3. **Delete the cross-context foreign keys.** This is the irreversible step and
   the one worth doing deliberately.
4. **Replace each cross-context join** with a subscription and a local
   projection, one call site at a time.
5. **Drop the compatibility views**, then create the per-context roles. Until
   this step the isolation is a convention; after it, it is a permission.

Steps 1 and 4 are the work. Steps 2, 3 and 5 are an afternoon.

## Checklist

- [ ] One schema per context, named for the context
- [ ] A role per context, or an ADR recording the shared-pool fallback
- [ ] No SQL anywhere names a table outside its own context's schema
- [ ] No foreign key crosses a schema
- [ ] No transaction touches two contexts
- [ ] Migrations live under the context and are numbered per context
- [ ] The outbox table is in the context's own schema
- [ ] Cross-context questions are answered by a projection or a reporting context, not a join
- [ ] No shared table with a `kind` or `type` discriminator serving two contexts

## Sources

**Books.** Sam Newman, _Monolith to Microservices_, ch. 4 ("Decomposing the
Database") — the schema-splitting patterns, including the compatibility-view
step above. Evans, ch. 14. Vernon, ch. 2 and ch. 12. Martin Fowler, _Patterns of
Enterprise Application Architecture_, ch. 11, for Unit of Work, which this page
scopes to one context and one use case.

**Online.** Every link below was reachable when this page was written.

- [Pattern: Database per service](https://microservices.io/patterns/data/database-per-service.html)
  — Richardson. Read as schema-per-context: the isolation is the pattern, the
  process count is incidental
- [Pattern: Shared database](https://microservices.io/patterns/data/shared-database.html)
  — the same author on the anti-pattern this page's *Wrong* section is made of
- [Pattern: Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)
  — rule 7, and why the table is the context's own
- [PostgreSQL: Schemas](https://www.postgresql.org/docs/current/ddl-schemas.html)
  — including the `search_path` semantics rule 12 relies on
- [PostgreSQL: GRANT](https://www.postgresql.org/docs/current/sql-grant.html)
  — what rule 2 actually buys
- [golang-migrate](https://github.com/golang-migrate/migrate) and
  [goose](https://github.com/pressly/goose) — either runs the per-context
  sequences; both support an explicit schema and an explicit version table,
  which is the feature rule 6 needs
- [How to break a Monolith into Microservices](https://martinfowler.com/articles/break-monolith-into-microservices.html)
  — Zhamak Dehghani on martinfowler.com; the data-splitting half is the hard
  half, and it is the same work whether or not a network follows
