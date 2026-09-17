# Concurrency

Where concurrency is allowed to exist, who owns a goroutine, and what the model
is protected from.

**Authority.** The [Go Memory Model](https://go.dev/ref/mem) and the Go
concurrency material — binding. Martin, _Clean Code_, ch. 13, contributes two
rules that survive the language change: **keep concurrency code separate from
business logic**, and **keep critical sections small**. Its Java-specific
material — synchronized methods, `volatile`, the execution models,
client-based versus server-based locking — is superseded.

## Why chapter 13 is superseded

The chapter is about defending shared mutable state in a language where every
object is shared by default and locking is a keyword. Go's answer is different
enough that the advice does not transfer:

- **Go has a written memory model.** [`go.dev/ref/mem`](https://go.dev/ref/mem)
  defines exactly which operations establish happens-before. There is no
  guesswork to give heuristics about.
- **Go has a race detector.** `go test -race` finds, at runtime, the class of
  bug the chapter spends twenty pages teaching you to reason about. It is not
  optional in this standard.
- **Go's primary tool is not the lock.** Channels and goroutine ownership
  restructure the problem so that most shared state never exists.

What survives is the structural rule, and in this standard it is stronger than
Martin states it.

## The first rule: the model is single-threaded

**Nothing in `domain` is concurrent, and nothing in `domain` is concurrency-safe.**

An aggregate has no mutex, starts no goroutine, reads no channel and does not
document itself as safe for concurrent use. It does not need to be, because the
transaction boundary already serialises it: one aggregate per transaction,
loaded, mutated, saved — see
[application services](../ddd/application-services.md) and
[aggregates](../ddd/aggregates.md).

Two transactions racing for the same aggregate are handled by **optimistic
concurrency at the repository**, not by locking in the model. That mechanism —
a version column, zero rows affected, `ErrConcurrentModification` — is specified
on [aggregates](../ddd/aggregates.md) and is not repeated here.

So concurrency lives in exactly three places:

| Region | Concurrency |
|---|---|
| `domain` | **None.** Not a goroutine, not a mutex, not a channel |
| `application` | **None, by default.** A use case is a sequence. Fan-out across aggregates is a design decision that needs a reason |
| `adapters` | **Yes** — servers, consumers, pollers, connection pools, workers, retries |
| `composition` | **Yes** — startup, shutdown, signal handling, supervision |

This is Martin's "keep concurrency code separate", taken to its conclusion: the
separation is a compile-time region boundary, not a convention.

## The rules

1. **`domain` is concurrency-free**, as above.
2. **Every goroutine has an owner, and the owner knows how it stops.** Before
   writing `go`, answer two questions in the code: what signals it to stop, and
   who waits for it to finish. If either has no answer, you have written a leak.
3. **Never start a goroutine in a constructor** or anywhere a caller cannot see
   it. A type that silently starts a background worker cannot be used in a test
   or shut down cleanly. Return a `Run(ctx) error` and let the caller start it.
4. **`context.Context` is the only cancellation mechanism.** First parameter,
   named `ctx`, never stored in a struct, never `nil`. Cancellation is checked
   and returned, not ignored — see
   [error handling](./error-handling.md) rule 9.
5. **Share memory by communicating, or protect it with a mutex — pick one per
   piece of state.** Both are correct Go. Mixing them on the same data is how
   races are written by people who know about both.
6. **Critical sections are small, and never contain a call out.** No network
   call, no disk write, no callback, no lock acquisition while holding a lock.
   This is Martin's rule and it is the most commonly broken one here.
7. **A mutex is unexported, and never copied.** Embed it as a field, never in an
   exported struct that is passed by value. `go vet` catches the copy; it cannot
   catch an exported one being locked inconsistently by a caller.
8. **Bound every fan-out.** An unbounded `for … { go … }` over a slice from a
   request is a denial-of-service with your own name on it. Use
   `errgroup.Group` with `SetLimit`, or a worker pool.
9. **`go test -race` runs in CI**, on the whole suite. A race that only appears
   under load is a race that appears in production first.
10. **No `time.Sleep` for coordination.** Sleeps are either flakiness or
    latency, usually both. Use a channel, a `sync.WaitGroup`, or `errgroup`.
11. **Consistency across aggregates is eventual, and that is the design.** The
    mechanism is the domain event and the outbox — see
    [domain events](../ddd/domain-events.md). Do not reach for concurrency to
    make two aggregates consistent inside one transaction; that is the rule
    telling you the boundary is wrong.
12. **Concurrency is tested.** A concurrent path gets a test that runs it
    concurrently, under `-race`, with `-count` above one.

## In Go

### Every goroutine has an owner

```go
// Wrong. Three failures: nothing stops it, nothing waits for it, and the error
// it returns is discarded into a log line nobody reads. The constructor has
// also made this type impossible to use in a test.
func NewOutboxRelay(db *sql.DB, p Publisher) *OutboxRelay {
	r := &OutboxRelay{db: db, publisher: p}
	go func() {
		for {
			if err := r.drain(context.Background()); err != nil {
				log.Println(err)
			}
			time.Sleep(time.Second)
		}
	}()
	return r
}
```

```go
// Correct. The constructor constructs. Run blocks until ctx is cancelled and
// returns why, so composition can wait for it during shutdown and a test can
// run it with a cancellable context.
func NewOutboxRelay(db *sql.DB, p Publisher, every time.Duration) *OutboxRelay {
	return &OutboxRelay{db: db, publisher: p, every: every}
}

func (r *OutboxRelay) Run(ctx context.Context) error {
	t := time.NewTicker(r.every)
	defer t.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-t.C:
			if err := r.drain(ctx); err != nil && !errors.Is(err, context.Canceled) {
				r.log.Error("outbox drain", "err", err)
			}
		}
	}
}
```

```go
// composition: started, supervised and waited for, in one place.
g, ctx := errgroup.WithContext(ctx)
g.Go(func() error { return relay.Run(ctx) })
g.Go(func() error { return server.Run(ctx) })
if err := g.Wait(); err != nil && !errors.Is(err, context.Canceled) {
	return err
}
```

### Critical sections, and calling out under a lock

```go
// Wrong. The publisher is a network call, made while holding the lock. Every
// other goroutine blocks for the round trip, and a slow broker becomes a total
// stall that looks like a deadlock in production.
func (r *Recorder) Record(ctx context.Context, e Event) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.seen = append(r.seen, e)
	return r.publisher.Publish(ctx, e) // network I/O under a mutex
}
```

```go
// Correct. The lock covers the state change and nothing else.
func (r *Recorder) Record(ctx context.Context, e Event) error {
	r.mu.Lock()
	r.seen = append(r.seen, e)
	r.mu.Unlock()

	return r.publisher.Publish(ctx, e)
}
```

Note the deliberate absence of `defer` in the correct version. `defer` is the
right default for a lock, but when the critical section is a prefix of the
function, unlocking explicitly is clearer and correct.

### Bounded fan-out

```go
// Wrong. One goroutine per element of a slice that came from a request body,
// and one connection each. The size of the fan-out is chosen by the caller.
for _, id := range req.OrderIDs {
	go func() { _ = uc.Handle(ctx, Command{OrderID: id}) }()
}
```

```go
// Correct. Bounded, cancelled as a group on the first error, and waited for.
g, ctx := errgroup.WithContext(ctx)
g.SetLimit(8)

for _, id := range req.OrderIDs {
	g.Go(func() error { return uc.Handle(ctx, Command{OrderID: id}) })
}

if err := g.Wait(); err != nil {
	return fmt.Errorf("place orders: %w", err)
}
```

Since Go 1.22 the loop variable is per-iteration, so `id` no longer needs
copying into the closure. On any module declaring an older Go version in
`go.mod`, it does — and that is exactly the kind of assumption a
[learning test](./boundaries.md) is for.

### Worker consuming a queue

```go
// An inbound adapter: the only place in this standard where a worker pool
// belongs. Each message becomes one call to one use case, which stays a
// sequence — the concurrency is outside the application, not inside it.
func (c *Consumer) Run(ctx context.Context) error {
	g, ctx := errgroup.WithContext(ctx)
	g.SetLimit(c.workers)

	for {
		msg, err := c.reader.Fetch(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				break
			}
			return fmt.Errorf("fetch: %w", err)
		}

		g.Go(func() error { return c.handle(ctx, msg) })
	}

	return g.Wait()
}
```

## What never becomes concurrent

| Tempting | Why not | Instead |
|---|---|---|
| Two aggregates updated in parallel in one use case | Breaks one-aggregate-per-transaction, and neither can be rolled back against the other | An event, and the [outbox](../ddd/domain-events.md) |
| A goroutine inside an aggregate method | The model becomes non-deterministic and untestable | The method returns; the caller decides |
| Parallel validation inside a domain service | Validation is microseconds; coordination is not | Sequential |
| A background cache refresh started by a repository | A hidden goroutine with no owner | An explicit component in `composition` |
| `go` in a constructor | Cannot be stopped, cannot be tested | `Run(ctx) error` |

## Common mistakes

| Mistake | Consequence |
|---|---|
| Goroutine with no stop signal | Leak; process memory grows until restart |
| Goroutine nobody waits for | Work lost at shutdown; half-written state |
| `go` in a constructor | Untestable, unstoppable, invisible |
| `ctx` stored in a struct | Cancellation applies to the wrong lifetime |
| Ignoring `ctx.Err()` | Work continues after the caller has gone |
| Network call under a mutex | Stalls every other goroutine; reads as a deadlock |
| Mutex copied by value | Two locks protecting nothing; `go vet` catches it |
| Exported mutex | Callers lock inconsistently; the invariant is external |
| Unbounded `go` per request item | Self-inflicted denial of service |
| `time.Sleep` for coordination | Flaky under load, slow when idle |
| No `-race` in CI | The class of bug that only appears in production |
| Concurrency in `domain` | The one region that must be deterministic no longer is |

## Checklist

- [ ] `domain` contains no goroutine, mutex or channel
- [ ] `application` is a sequence unless there is a written reason otherwise
- [ ] Every goroutine has a documented owner, stop signal and waiter
- [ ] No goroutine is started by a constructor
- [ ] `ctx` is the first parameter everywhere and is never stored in a struct
- [ ] Cancellation is checked and distinguished from failure
- [ ] Critical sections hold no I/O and no callbacks
- [ ] Mutexes are unexported and never copied
- [ ] Every fan-out is bounded
- [ ] `go test -race` runs the full suite in CI
- [ ] No `time.Sleep` used for coordination
- [ ] Cross-aggregate consistency is eventual, via events

## Sources

**Books.** Martin, _Clean Code_, ch. 13 — "Concurrency", for separating
concurrency from business logic and for keeping synchronized sections small.
Its Java-specific material is superseded by the Go memory model. Vernon,
_Implementing Domain-Driven Design_, ch. 8 and ch. 10, for why cross-aggregate
consistency is eventual rather than coordinated.

**Online.** Every link below was reachable when this page was written.

- [The Go Memory Model](https://go.dev/ref/mem) — the normative definition of
  happens-before in Go; the reason this page gives rules rather than heuristics
- [Data Race Detector](https://go.dev/doc/articles/race_detector) — how to run
  it, what it can and cannot see, and why it belongs in CI
- [Introducing the Go Race Detector](https://go.dev/blog/race-detector) — the
  announcement, with worked examples of the races it finds
- [Go Concurrency Patterns: Context](https://go.dev/blog/context) — cancellation
  propagation, and why `ctx` is a parameter rather than a field
- [Go Concurrency Patterns: Pipelines and cancellation](https://go.dev/blog/pipelines)
  — the ownership and shutdown discipline rule 2 is taken from
- [Concurrency is not parallelism](https://go.dev/blog/waza-talk) — Pike; the
  distinction that decides whether a problem wants concurrency at all
- [Go Proverbs](https://go-proverbs.github.io/) — "Don't communicate by sharing
  memory, share memory by communicating", and "Channels orchestrate; mutexes
  serialize"
