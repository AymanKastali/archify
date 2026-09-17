# Enforcement

A boundary nobody can cross beats a boundary nobody is supposed to cross. This
page is what actually stops each rule being broken, in order of how hard it is
to ignore — and, just as importantly, what none of it catches.

**Authorities.** None. Every mechanism here is this standard's own arrangement
of Go's `internal/` rule, golangci-lint's depguard, and
`golang.org/x/tools/go/packages`.

## The four levels

| Level | Catches | Ignorable by |
|---|---|---|
| **The compiler** | A context importing another context's interior | Nobody. It is not a build |
| **depguard** | A region importing a package it may not | Deleting the lint rule, which is visible in the diff |
| **An architecture test** | Everything path-shaped that depguard cannot express | Deleting a test, which is visible in the diff |
| **Review** | Everything about meaning — whether a type is in the right region *at all* | Being tired → [review passes](../../skills/review-passes/SKILL.md) |

**Use the highest level that can express the rule.** Writing an architecture
test for something the compiler already prevents is wasted; hoping review
catches something depguard could state is how a standard erodes.

## 1 — The compiler

The nested `internal/` in [layout](./layout.md) is not a naming convention. `go`
permits a package under `a/internal/b` to be imported only from within `a`, so:

```go
// internal/contexts/shipping/internal/application/command/prepare_shipment.go
import "myapp/internal/contexts/ordering/internal/domain/order"
```

```text
use of internal package myapp/internal/contexts/ordering/internal/domain/order
not allowed
```

That is property 2 of a modular monolith, obtained for the price of one
directory. It is stronger than anything a service boundary gives you: a service
can be called by anything that can reach its port, and this cannot be imported
at all.

**What it does not catch:** everything inside one context, everything about
`platform/`, and every runtime coupling — most importantly a cross-schema join,
which the import graph never sees. → [data](./data.md)

## 2 — depguard

`.golangci.yml`, with the real module path substituted. This is the file
[`/archify:setup`](../../skills/setup/SKILL.md) writes:

```yaml
version: "2"

linters:
  enable:
    - depguard
  settings:
    depguard:
      rules:
        # domain imports the standard library and its own context's domain.
        # Nothing else — no driver, no framework, no platform, no other context.
        domain:
          files:
            - "**/internal/contexts/*/internal/domain/**"
          allow:
            - $gostd
            - myapp/internal/contexts
          deny:
            - pkg: "myapp/internal/platform"
              desc: "domain imports stdlib and its own context's domain only"
            - pkg: "github.com"
              desc: "domain imports stdlib and its own context's domain only"
            - pkg: "google.golang.org"
              desc: "domain imports stdlib and its own context's domain only"
            - pkg: "gopkg.in"
              desc: "domain imports stdlib and its own context's domain only"

        # application orchestrates. It declares ports; it does not name the
        # things that satisfy them.
        application:
          files:
            - "**/internal/contexts/*/internal/application/**"
          allow:
            - $gostd
            - myapp/internal/contexts
          deny:
            - pkg: "myapp/internal/platform"
              desc: "declare a port; the adapter supplies the platform type"
            - pkg: "database/sql"
              desc: "persistence belongs in adapters/outbound"
            - pkg: "net/http"
              desc: "transport belongs in adapters/inbound"
            - pkg: "github.com"
              desc: "no third-party type in application"

        # query is the read side. It answers a screen by going round the
        # aggregate, so it has no business naming a domain type or a
        # repository — and a query that can reach the write model eventually
        # writes through it.
        query:
          files:
            - "**/internal/contexts/*/internal/application/query/**"
          allow:
            - $gostd
          deny:
            - pkg: "myapp"
              desc: "a read model is primitives; query imports no domain and no repository"

        # platform is a leaf. It knows no context, including published/.
        platform:
          files:
            - "**/internal/platform/**"
          deny:
            - pkg: "myapp/internal/contexts"
              desc: "platform must not depend on any bounded context"

        # published/ is data. It carries no behaviour and no dependencies.
        published:
          files:
            - "**/internal/contexts/*/published/**"
          allow:
            - $gostd
          deny:
            - pkg: "myapp"
              desc: "published types are plain data, importing nothing"
```

Then verify it rather than assuming it parses:

```bash
golangci-lint config verify && golangci-lint run ./...
```

**What depguard cannot express.** It matches import paths by prefix, with no
notion of *which* context a file is in. So it cannot say "`ordering` may not
import `shipping`" without one rule per pair — which is why the `allow` lists
above stop at `myapp/internal/contexts` and the next level picks it up.

## 3 — The architecture test

One test, in the repository, that walks the real import graph and states the
rules depguard cannot. It runs in about a second and it is the highest-value
test in the project after the composition build test.

```go
// internal/arch/arch_test.go
//
// Asserts the dependency rules that neither the compiler nor depguard can
// state, by walking the real import graph. Everything here is a path rule;
// rules about meaning are review's job.
package arch_test

import (
	"strings"
	"testing"

	"golang.org/x/tools/go/packages"
)

// module is this repository's module path, exactly as go.mod spells it.
const module = "myapp"

func TestImportRules(t *testing.T) {
	cfg := &packages.Config{Mode: packages.NeedName | packages.NeedImports}
	pkgs, err := packages.Load(cfg, module+"/...")
	if err != nil {
		t.Fatalf("loading packages: %v", err)
	}

	for _, p := range pkgs {
		for imp := range p.Imports {
			if reason := forbidden(p.PkgPath, imp); reason != "" {
				t.Errorf("%s\n  imports %s\n  %s", p.PkgPath, imp, reason)
			}
		}
	}
}

// forbidden returns why `from` may not import `to`, or "" if it may.
func forbidden(from, to string) string {
	if !strings.HasPrefix(to, module+"/") {
		// The standard library and third-party packages are depguard's
		// problem, not this test's. Test the module prefix and nothing else:
		// a module path with no dot in it — "myapp" — is indistinguishable
		// from a standard-library path by any other rule.
		return ""
	}

	fromCtx, fromRegion := classify(from)
	toCtx, _ := classify(to)

	switch {
	case strings.HasPrefix(from, module+"/internal/platform/"):
		if toCtx != "" {
			return "platform must not depend on a bounded context"
		}

	case fromCtx != "" && toCtx != "" && fromCtx != toCtx:
		// Cross-context. Only published/ may cross, and only from adapters.
		if !strings.HasPrefix(to, module+"/internal/contexts/"+toCtx+"/published") {
			return "a context may import another context's published/ package and nothing else"
		}
		// Only adapters (where the ACL translates) and the facade (where the
		// consumer declares the interface it needs) may name another context's
		// published types.
		if fromRegion != "adapters" && fromRegion != "facade" {
			return "another context's published types belong in adapters/ or the facade, not in " + fromRegion
		}

	case fromRegion == "domain" && !strings.HasPrefix(to, module+"/internal/contexts/"+fromCtx+"/internal/domain/"):
		return "domain imports the standard library and its own context's domain only"

	case fromRegion == "application" && strings.HasPrefix(to, module+"/internal/platform/"):
		return "application declares a port; the adapter supplies the platform type"

	case strings.HasSuffix(from, "/published") && strings.HasPrefix(to, module+"/"):
		return "published types are plain data, importing nothing from this module"
	}
	return ""
}

// classify returns the bounded context a package belongs to and its region
// within that context. Both are "" for packages outside internal/contexts.
func classify(pkg string) (context, region string) {
	rest, ok := strings.CutPrefix(pkg, module+"/internal/contexts/")
	if !ok {
		return "", ""
	}
	parts := strings.Split(rest, "/")
	context = parts[0]
	switch {
	case len(parts) >= 3 && parts[1] == "internal":
		region = parts[2] // domain | application | adapters
	case len(parts) >= 2 && parts[1] == "published":
		region = "published"
	default:
		region = "facade"
	}
	return context, region
}
```

Two rules in that function are worth naming, because they are the ones no other
level can reach:

- **The region check** on a cross-context import. It is not enough that only
  `published/` crosses; it must arrive somewhere that translates it. `adapters`
  is where the ACL lives and the facade is where the consumer-declared interface
  lives; a `published` type named in `application` or `domain` is an upstream
  contract that reached the model.
  → [communication](./communication.md), rule 8
- **The `published` case**: a published package importing anything from this
  module means a domain type has leaked into the contract, which is the failure
  that makes every internal rename a breaking change.

### The second architecture test

Cheap, and catches the other half:

```go
// No context may name another context's facade package. Structural interfaces
// mean it never has to. → modules.md, rule 6
func TestNoFacadeImports(t *testing.T) {
	// ... same load ...
	for _, p := range pkgs {
		fromCtx, _ := classify(p.PkgPath)
		if fromCtx == "" {
			continue // composition is allowed to, and must
		}
		for imp := range p.Imports {
			toCtx, toRegion := classify(imp)
			if toCtx != "" && toCtx != fromCtx && toRegion == "facade" {
				t.Errorf("%s imports the %s facade; declare the interface it needs instead", p.PkgPath, toCtx)
			}
		}
	}
}
```

## 4 — CI

The whole of it, and it is short:

```makefile
.PHONY: check
check: fmt lint arch test

fmt:
	gofmt -l -d . | tee /dev/stderr | (! read)

lint:
	golangci-lint config verify
	golangci-lint run ./...

arch:
	go test -count=1 ./internal/arch/... ./internal/composition/...

test:
	go test -race ./...
	go test -race -tags=integration ./...
```

`arch` is called out separately from `test` on purpose: when it fails, the
failure is architectural and the fix is not "make the test pass".

**`-count=1` is not optional there.** The architecture test reads the import
graph off the filesystem at run time rather than through its own imports, so
`go test` will serve a cached pass for a tree that has since acquired a
violation. A cached green arch run is the one failure mode that makes this whole
page decorative, and it is invisible — the output says `ok`.

## What none of this catches

Everything about **meaning**, and one thing about **runtime**. These are review
findings, and a green build that is taken to mean more than this is how a
standard quietly stops applying:

| Not caught by any tool | Level |
|---|---|
| A cross-schema join or foreign key | Review + [data](./data.md). **Nothing in the import graph shows it** |
| A transaction spanning two contexts | Review. Both handles came from the same pool, legitimately |
| A business rule in an application service, a subscriber, or a facade | Review |
| An aggregate with exported fields, or constructible invalid | Review |
| Two aggregates saved in one transaction | Review |
| A port named for its adapter, or declared on the wrong side | Review |
| A context that should not exist, or two that should be one | Review |
| A published type shaped for exactly one consumer | Review |
| A `platform/` package with domain meaning in it | Review. The import graph is clean; the *content* is not |

The passes that cover these are in
[`/archify:review-passes`](../../skills/review-passes/SKILL.md). The first four
rows are the expensive ones.

## Adding enforcement to an existing project

Scope the rules to new paths so the build is green on day one, then widen:

1. Add the `platform` and `published` depguard rules first — they are almost
   always already satisfied, and they are the ones that decay silently.
2. Add the `domain` and `application` rules scoped to
   `**/internal/contexts/<new>/**` only.
3. Add the architecture test with a **known-failures list** — a literal set of
   `from → to` pairs that are allowed to exist, each with a comment naming the
   ADR. Make the test fail if a pair in the list has been fixed and not removed;
   a ratchet that only tightens is the point.
4. Widen the depguard file globs as each inherited context is migrated.

## Checklist

- [ ] Every context's interior is behind a nested `internal/`
- [ ] `.golangci.yml` carries the five depguard rules, and `golangci-lint config verify` passes
- [ ] The architecture test exists and runs in CI as its own step, with `-count=1`
- [ ] The composition build test exists → [composition](./composition.md)
- [ ] CI runs `-race`, and runs the integration-tagged tests
- [ ] Any known-failures list in the architecture test cites an ADR per entry

## Sources

**Books.** Robert C. Martin, _Clean Architecture_, ch. 14 ("Component Coupling")
— the acyclic-dependencies principle these tests assert mechanically. Sam
Newman, _Monolith to Microservices_, ch. 3, on why an enforced module boundary
is the precondition for everything else.

**Online.** Every link below was reachable when this page was written.

- [Internal packages](https://go.dev/cmd/go#hdr-Internal_packages) — the
  rule level 1 is entirely built on
- [golangci-lint: linters configuration](https://golangci-lint.run/docs/linters/configuration/)
  — the `depguard` settings used above, including `$gostd` and `files`
- [golangci-lint](https://github.com/golangci/golangci-lint) — the runner, and
  `config verify`, which is the step most projects skip
- [go/packages](https://pkg.go.dev/golang.org/x/tools/go/packages) — the loader
  the architecture test uses; `NeedName | NeedImports` is the cheapest useful
  mode
- [go-arch-lint](https://github.com/fe3dback/go-arch-lint) — a declarative
  alternative to writing the test above. Worth knowing about; this standard
  prefers the test, because the rules are then in Go and reviewable as code
- [Go Modules Reference](https://go.dev/ref/mod) — for why a module path need
  not contain a dot, which is the trap the import guard above is written around
