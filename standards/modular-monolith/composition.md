# Composition

Where the contexts meet. One file knows they all exist; nothing else does.

**Authorities.** Martin, _Clean Architecture_, ch. 26 ("The Main Component") —
`main` is a plugin to the application, the dirtiest component, and it depends on
everything while nothing depends on it. Fowler, _Inversion of Control Containers
and the Dependency Injection Pattern_ (2004), for the vocabulary and for the
distinction between the pattern and the container. The Twelve-Factor App, for
configuration.

[`../structure.md`](../structure.md) lists `composition` as the fourth region of
a context. In a modular monolith that region exists at two levels, and
[layout](./layout.md) says which is which: the context's facade builds the
context; `internal/composition/` builds the program.

## The rules

1. **`main` holds flags, signals and the exit code.** Nothing constructs
   anything in `cmd/`.
2. **Wiring is hand-written and reads top to bottom.** If you cannot see the
   dependency direction by reading one file, no reviewer can check it.
3. **No reflection-based container.** The object graph must be knowable at
   `go build`, not at start-up.
4. **No `init()` and no self-registration.** A context does not add itself to a
   list. The list is in one file and it is edited by hand.
5. **Construction fails fast.** Every `New` returns an error; a missing
   dependency is a start-up failure, never a `nil` discovered under load.
6. **Configuration is one struct, loaded once, validated once**, and passed as
   values. No context reads an environment variable.
7. **One binary, several run modes**, selected by subcommand. Each mode builds
   from the same composition code.
8. **Start order is explicit; shutdown is its reverse.** Inbound transports stop
   first, background work second, platform resources last.
9. **The composition root never reaches past a facade.** It cannot — the nested
   `internal/` forbids it — and the value is that the wiring is impossible to
   get wrong rather than merely discouraged.
10. **No business logic.** Not a conditional on a domain value, not a
    calculation, not a mapping between two contexts' vocabularies. If
    composition is translating, an ACL is missing.
    → [communication](./communication.md)
11. **Every long-running goroutine is owned here.** A context's `Run` is
    supervised by the composition root; nothing starts a goroutine in a
    constructor.
    → [`../clean-code/concurrency.md`](../clean-code/concurrency.md)
12. **Composition is covered by one test**: that the whole graph builds. It is
    the cheapest test in the repository and it catches every wiring mistake that
    a compile cannot.

## `main`

```go
// cmd/app/main.go
package main

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "app: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	// Signals cancel the root context. Every goroutine in the program descends
	// from it, so a single Ctrl-C reaches all of them.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	cfg, err := composition.LoadConfig()
	if err != nil {
		return err
	}

	switch mode := flag.Arg(0); mode {
	case "", "serve":
		return composition.Serve(ctx, cfg)
	case "worker":
		return composition.Worker(ctx, cfg)
	case "migrate":
		return composition.Migrate(ctx, cfg)
	default:
		return fmt.Errorf("unknown mode %q: want serve, worker or migrate", mode)
	}
}
```

That is the whole file, and it is the whole reason `main` is not worth testing:
there is nothing in it that could be wrong in an interesting way.

## The context list

```go
// internal/composition/contexts.go
//
// The only file in the repository that names every bounded context. Adding a
// context means editing this file, on purpose — there is no registry, no
// init() and no reflection, because the dependency direction of the whole
// program is readable here and nowhere else.
package composition

// contexts is every assembled context, plus the three things the program needs
// from them: routes to mount, subscriptions to register, and background work to
// supervise.
type contexts struct {
	all  []runnable
	mux  map[string]http.Handler
	subs []eventbus.Subscription
}

func buildContexts(ctx context.Context, cfg Config, p *platform) (*contexts, error) {
	ord, err := ordering.New(ordering.Deps{
		DB:     p.pools["ordering"],
		Bus:    p.bus,
		Clock:  p.clock,
		IDs:    p.ids,
		Logger: p.log.With("context", "ordering"),
	})
	if err != nil {
		return nil, fmt.Errorf("ordering: %w", err)
	}

	// shipping asks ordering questions through an interface shipping declared.
	// This assignment is the only coupling between the two, and the day
	// ordering becomes a service it is the only line that changes.
	shp, err := shipping.New(shipping.Deps{
		DB:     p.pools["shipping"],
		Bus:    p.bus,
		Orders: ord,
		Clock:  p.clock,
		Logger: p.log.With("context", "shipping"),
	})
	if err != nil {
		return nil, fmt.Errorf("shipping: %w", err)
	}

	bil, err := billing.New(billing.Deps{
		DB:     p.pools["billing"],
		Bus:    p.bus,
		Clock:  p.clock,
		Logger: p.log.With("context", "billing"),
	})
	if err != nil {
		return nil, fmt.Errorf("billing: %w", err)
	}

	c := &contexts{
		all: []runnable{ord, shp, bil},
		mux: map[string]http.Handler{
			"/api/orders":    ord.Routes(),
			"/api/shipments": shp.Routes(),
			"/api/invoices":  bil.Routes(),
		},
	}
	for _, r := range c.all {
		c.subs = append(c.subs, r.Subscriptions()...)
	}
	return c, nil
}

// runnable is what the composition root needs from every context, and the whole
// of what it needs. A context that grows a fourth obligation grows it here.
type runnable interface {
	Routes() http.Handler
	Subscriptions() []eventbus.Subscription
	Run(ctx context.Context) error
}
```

Note that `buildContexts` is a **list of `New` calls and one wiring
assignment**. When it grows a conditional, something has moved into the wrong
place.

## Lifecycle

```go
// internal/composition/lifecycle.go

// Serve runs the HTTP transport and every context's background work until ctx
// is cancelled, then shuts them down in reverse order.
func Serve(ctx context.Context, cfg Config) error {
	p, err := newPlatform(ctx, cfg)
	if err != nil {
		return err
	}
	defer p.Close() // platform closes last, because everything uses it

	cs, err := buildContexts(ctx, cfg, p)
	if err != nil {
		return err
	}

	for _, s := range cs.subs {
		if err := p.bus.Subscribe(s); err != nil {
			return fmt.Errorf("subscribing %s to %s: %w", s.Name, s.Topic, err)
		}
	}

	srv := &http.Server{
		Addr:              cfg.HTTP.Addr,
		Handler:           router(cs.mux, p),
		ReadHeaderTimeout: 5 * time.Second,
	}

	g, gctx := errgroup.WithContext(ctx)

	// Background work: every context's Run, supervised. One failing relay
	// cancels gctx and brings the program down deliberately rather than
	// leaving it half-running.
	for _, r := range cs.all {
		g.Go(func() error { return r.Run(gctx) })
	}

	g.Go(func() error {
		if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			return err
		}
		return nil
	})

	// Shutdown, in reverse: stop accepting requests, then let Run return via
	// gctx, then let the deferred p.Close release the pools.
	g.Go(func() error {
		<-gctx.Done()
		sctx, cancel := context.WithTimeout(context.WithoutCancel(gctx), cfg.HTTP.ShutdownTimeout)
		defer cancel()
		return srv.Shutdown(sctx)
	})

	if err := g.Wait(); err != nil && !errors.Is(err, context.Canceled) {
		return err
	}
	return nil
}
```

Four properties are worth naming because each is a defect when absent:

- **One root context.** A signal cancels everything descended from it.
- **Inbound stops first.** Shutting down the HTTP server before cancelling
  background work means in-flight requests finish against a live database.
- **`context.WithoutCancel`** on the shutdown context: `gctx` is already
  cancelled by the time you need it, so a timeout derived from it would expire
  instantly.
- **The platform closes last**, via `defer`, after every user of it has stopped.

## Configuration

```go
// internal/composition/config.go

// Config is the whole program's configuration. It is loaded once, validated
// once, and passed onward as values — no context reads the environment, so
// every context is constructible in a test without one.
type Config struct {
	Env      string `env:"APP_ENV"       default:"development"`
	HTTP     HTTPConfig
	Contexts map[string]ContextConfig // DSN per context → data.md
	Log      LogConfig
}

func LoadConfig() (Config, error) {
	var c Config
	if err := envconfig.Process(&c); err != nil {
		return Config{}, fmt.Errorf("loading config: %w", err)
	}
	return c, c.validate()
}

// validate fails at start-up rather than at the first request that needs a
// missing value. Every field is checked, and the error names all of them at
// once — discovering configuration problems one restart at a time is its own
// kind of outage.
func (c Config) validate() error {
	var errs []error
	if c.HTTP.Addr == "" {
		errs = append(errs, errors.New("HTTP_ADDR is required"))
	}
	for name, cc := range c.Contexts {
		if cc.DSN == "" {
			errs = append(errs, fmt.Errorf("DSN for context %q is required", name))
		}
	}
	return errors.Join(errs...)
}
```

## No container, and the one exception

Rule 3 rejects reflection-based dependency injection — `dig`, `fx`, and anything
that assembles the graph from struct tags at start-up. The reasons are specific:

- **The dependency direction becomes unreviewable.** The whole point of this
  standard is that a wrong direction is visible. A container hides it behind a
  provider set.
- **Wiring errors move from compile time to start-up**, which in practice means
  to the first deploy that exercises the path.
- **The call graph disappears.** "Find all references" stops answering the
  question it exists to answer.

The exception is **code generation**: [`google/wire`][wire] emits the file you
would have written by hand, and it is checked in and reviewable. It is permitted
with an ADR, because it is a build-time tool rather than a runtime one. A
hand-written `buildContexts` is still the default, and for three contexts it is
shorter than the provider sets would be.

The same reasoning rejects a **mediator or command bus** in front of use cases.
An application service is called directly, by name, from an adapter that holds
it. A bus buys uniformity and sells the call graph.

## Testing composition

```go
// internal/composition/build_test.go

// TestBuilds is the cheapest test in the repository: it asserts that the whole
// object graph can be constructed. It catches every missing dependency, every
// nil check in a New, and every wiring mistake the compiler cannot see.
func TestBuilds(t *testing.T) {
	cfg := testsupport.Config(t) // real shape, throwaway schemas
	p, err := newPlatform(t.Context(), cfg)
	if err != nil {
		t.Fatalf("platform: %v", err)
	}
	t.Cleanup(p.Close)

	if _, err := buildContexts(t.Context(), cfg, p); err != nil {
		t.Fatalf("building contexts: %v", err)
	}
}
```

Beyond that, composition is exercised by `test/e2e/`, which starts the binary
and talks to it over HTTP. There is nothing in between worth a unit test, and
there is nothing in composition worth mocking.

## Wrong, and why

```go
// Wrong: self-registration. The context list is now assembled by import side
// effects, in an order nobody chose, and no file shows what the program is.
func init() { composition.Register("ordering", New) }
```

```go
// Wrong: a context reads the environment. It is now unconstructible in a test
// without setting a global, and the configuration surface of the program is
// unknowable.
func New(d Deps) (*Component, error) {
	timeout, _ := time.ParseDuration(os.Getenv("ORDERING_TIMEOUT"))
	...
}
```

```go
// Wrong: business logic in the composition root. This rule is now in the one
// place no test of the model reaches, and no glossary covers.
if cfg.Env == "production" && customer.Tier == "enterprise" {
	place = command.NewPlaceOrderWithApproval(...)
}
```

```go
// Wrong: a goroutine with no owner. Nothing can stop it, nothing observes its
// failure, and shutdown does not wait for it.
func New(d Deps) (*Component, error) {
	go relay.Loop()
	...
}
```

```go
// Wrong: lazy construction. The failure now happens on the first request that
// needs it, in production, rather than at start-up in CI.
func (c *Component) orders() order.Repository {
	c.once.Do(func() { c.repo = postgres.NewOrders(c.db) })
	return c.repo
}
```

## Checklist

- [ ] `cmd/app/main.go` constructs nothing
- [ ] One file names every context; nothing else does
- [ ] No `init()`, no registry, no reflection-based container
- [ ] Every `New` returns an error, and nothing is built lazily
- [ ] No context reads an environment variable
- [ ] Config is validated at start-up and reports every problem at once
- [ ] Every long-running goroutine is started by the composition root under an `errgroup`
- [ ] Shutdown stops inbound transports before cancelling background work
- [ ] No conditional in composition reads a domain value
- [ ] A test asserts the whole graph builds

## Sources

**Books.** Robert C. Martin, _Clean Architecture_, ch. 26 ("The Main
Component"). Martin Fowler, _Patterns of Enterprise Application Architecture_,
ch. 18, for Service Locator and why this page does not use one. Sam Newman,
_Building Microservices_, 2nd ed., ch. 11, for shutdown and lifecycle
expectations that apply identically to a context inside one process.

**Online.** Every link below was reachable when this page was written.

- [Inversion of Control Containers and the Dependency Injection Pattern](https://martinfowler.com/articles/injection.html)
  — Fowler, 2004. The article that named the pattern, and it is careful that the
  pattern does not require a container
- [The Twelve-Factor App: Config](https://12factor.net/config) — rule 6, stated
  as a deployment property
- [google/wire](https://github.com/google/wire) — the code-generation exception
  to rule 3, and the Go team-adjacent argument for generating wiring rather than
  reflecting it
- [errgroup](https://pkg.go.dev/golang.org/x/sync/errgroup) — the supervision
  primitive rule 11 assumes
- [signal.NotifyContext](https://pkg.go.dev/os/signal#NotifyContext) — the
  single-root-context arrangement in `main`
- [context.WithoutCancel](https://pkg.go.dev/context#WithoutCancel) — added in
  Go 1.21, and the fix for the shutdown-timeout bug named above
- [http.Server.Shutdown](https://pkg.go.dev/net/http#Server.Shutdown) — the
  ordering guarantee rule 8 depends on

[wire]: https://github.com/google/wire
