# Clean Code

How code reads. This page is the entry point, the verdict on each of Martin's
chapters, and the list of rules that are **deliberately not applied in Go**; the
rules themselves are one page each under [`clean-code/`](./clean-code/).

**Authority.** Robert C. Martin, _Clean Code: A Handbook of Agile Software
Craftsmanship_ (2008). For SOLID, the same author's _Clean Architecture_ (2017),
Part III. Martin Fowler, _Refactoring_ (2nd ed., 2018), for the smell catalogue
this standard shares with `/code-review`.

## Precedence

_Clean Code_ is a Java book written in 2008, three years before Go 1. Applying
it line by line to Go produces code that is worse by both standards — the
result reads like Java written with Go keywords, which is the specific failure
this page exists to prevent.

The order is fixed:

1. **Go wins wherever idiom collides with the book.** Not "usually wins" —
   wins. The Go sources are [Effective Go](https://go.dev/doc/effective_go),
   [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) and the
   [Google Go Style Guide](https://google.github.io/styleguide/go/), and where
   they speak, they are the rule.
2. **The model wins over style.** A rule here never justifies breaking one
   under [`ddd/`](./ddd/). If "extract this function" would move an invariant
   out of an aggregate, the invariant stays and the function is long.
3. **Martin binds on cohesion, coupling and dependency direction** — the
   reasoning of the book, which survives the language change intact.
4. **Martin does not bind on mechanics** — line counts, argument counts as
   absolutes, exception style, comment prohibition. These are Java-shaped and
   are replaced below.

**The distinction that matters:** _Clean Code_ argues for things and then gives
rules of thumb for achieving them in Java. **The arguments bind. The rules of
thumb do not.** "A function should do one thing" binds. "A function should be
four lines long" does not.

## The chapters, and what each is worth here

| Ch. | Martin's chapter | Verdict | Page |
|---|---|---|---|
| 2 | Meaningful Names | **Binds, with one inversion** — name length is proportional to scope in Go | [naming](./clean-code/naming.md) |
| 3 | Functions | **Binds on cohesion, rejected on size** | [functions](./clean-code/functions.md) |
| 4 | Comments | **Inverted for exported identifiers** — Go requires what Martin calls failure | [comments](./clean-code/comments.md) |
| 5 | Formatting | **Settled by `gofmt`** — the chapter is void, one rule survives | [formatting](./clean-code/formatting.md) |
| 6 | Objects and Data Structures | **Binds** — it is the anaemic-model argument in another vocabulary | [types and packages](./clean-code/types-and-packages.md) |
| 7 | Error Handling | **Rejected** — Go's error model replaces it wholesale | [error handling](./clean-code/error-handling.md) |
| 8 | Boundaries | **Binds** — and it is hexagonal architecture, arrived at from another direction | [boundaries](./clean-code/boundaries.md) |
| 9 | Unit Tests | **Binds on F.I.R.S.T., inverted on one-assert-per-test** | [tests](./clean-code/tests.md) |
| 10 | Classes | **Binds, re-seated on the package** — Go has no classes | [types and packages](./clean-code/types-and-packages.md) |
| 11 | Systems | **Superseded** by [`structure.md`](./structure.md) and [`modular-monolith/composition.md`](./modular-monolith/composition.md) | — |
| 12 | Emergence | **Binds** — the four rules of simple design | [smells](./clean-code/smells.md) |
| 13 | Concurrency | **Superseded** by the Go memory model and `go vet -race` | [concurrency](./clean-code/concurrency.md) |
| 14–16 | Case studies | **Not rules.** Worth reading; nothing here cites them | — |
| 17 | Smells and Heuristics | **Filtered** — most bind, eight do not | [smells](./clean-code/smells.md) |
| _CA_ III | SOLID | **Binds, re-expressed** for a language with no inheritance | [SOLID](./clean-code/solid.md) |

## The rules deliberately not applied here

Every one of these is in the book, every one is wrong for Go, and every one is a
finding a reviewer will otherwise raise on a diff that is correct. They are
listed once, here, so that no reviewer has to argue them again.

| The book says | This standard says | Why |
|---|---|---|
| "Prefer exceptions to returning error codes" (ch. 7) | Errors are returned values, checked at the call site | Go has no exceptions. `panic` is not one and must not be used as one → [error handling](./clean-code/error-handling.md) |
| "Functions should hardly ever be 20 lines long" — and ideally four (ch. 3) | **No line limit.** A function does one thing; how many lines that takes is not a rule | `if err != nil { return … }` costs three lines and adds no abstraction. A 15-line Go function often has fewer concepts than a 6-line Java one → [functions](./clean-code/functions.md) |
| "Long descriptive names are better than short ones" (ch. 2) | Name length is **proportional to the size of the scope** | `for i := range xs` and `func (o *Order)` are correct. `orderRepositoryInstance` is not → [naming](./clean-code/naming.md) |
| "Comments are always failures" (ch. 4) | Every exported identifier carries a doc comment, whether or not the code is self-evident | The doc comment is the package's published API, rendered by `go doc` and pkg.go.dev. It is documentation, not apology → [comments](./clean-code/comments.md) |
| "Don't return null. Don't pass null" (ch. 7) | A usable zero value where one exists; a value object where one does not | Go's answer to null is not a wrapper object, it is making the zero value meaningful → [error handling](./clean-code/error-handling.md) |
| "One assert per test" (ch. 9) | **One concept per test**, expressed as a table-driven test with subtests | Table-driven tests are the Go convention and they hold many asserts by construction → [tests](./clean-code/tests.md) |
| "Replace switch with polymorphism" (ch. 3, ch. 17 G23) | A type switch over a closed set stays a type switch | Already settled for the smell baseline in [`vocabulary.md`](./vocabulary.md) |
| "Prefer non-static methods to static" / "the object graph" (ch. 6, ch. 17) | Free functions are fine. A method exists when there is state or an interface to satisfy | Go has no static/instance split to argue about |
| Hungarian-style prefixes and `I`-prefixed interfaces (ch. 2) | Neither, ever. An interface is named for the behaviour, usually `-er` | [naming](./clean-code/naming.md) |

Two more collisions are settled on [`vocabulary.md`](./vocabulary.md) rather
than here, because they come from `/code-review`'s smell baseline and not from
the book: **Middle Man** and **Repeated Switches**.

## What this corpus does not cover

The split is strict, because a rule written twice drifts.

| Question | Page |
|---|---|
| What is modelled, and how | [`domain-driven-design.md`](./domain-driven-design.md) and [`ddd/`](./ddd/) |
| Where code goes inside a context, and which way dependencies point | [`structure.md`](./structure.md) |
| The project layout, and how contexts are packaged and kept apart | [`modular-monolith.md`](./modular-monolith.md) and [`modular-monolith/`](./modular-monolith/) |
| What a word means when another standard uses it differently | [`vocabulary.md`](./vocabulary.md) |
| How a **domain** error is declared and mapped | [`ddd/errors.md`](./ddd/errors.md) — [error handling](./clean-code/error-handling.md) covers the rest of the program |
| What a **name in the model** must be | [`ddd/ubiquitous-language.md`](./ddd/ubiquitous-language.md) — [naming](./clean-code/naming.md) covers identifiers the glossary does not reach |

Where a page here and a page under `ddd/` both apply, **the `ddd/` page is the
more specific rule and the finding cites it.**

## The running example

The same three contexts as the model pages — `ordering`, `shipping`, `billing`
— so that an example on this page is the same code as an example on that one.
See [`domain-driven-design.md`](./domain-driven-design.md).

## Departing from this standard

A project may depart from any rule under `clean-code/`. The departure is
recorded as an ADR in that project's `docs/adr/`, naming the rule it overrules
and arguing why.

**A deviation without an ADR is a defect,** not a style choice.

A reviewer treats an ADR-backed departure as settled and does not report it. A
departure without one is a finding every time it is seen.

One asymmetry is worth stating: **the rules this page says are not applied need
no ADR.** They are not deviations. Writing a 40-line Go function with six error
checks is conformance, and reporting it is the finding.

## Sources

### The books this standard binds to

- Robert C. Martin, _Clean Code: A Handbook of Agile Software Craftsmanship_.
  Prentice Hall, 2008. ISBN 978-0-13-235088-4. Chapters 2–13 and 17 are the ones
  this corpus takes a position on, chapter by chapter, in the table above.
- Robert C. Martin, _Clean Architecture_. Prentice Hall, 2017.
  ISBN 978-0-134-49416-6. Part III for SOLID. Part V is cited by
  [`structure.md`](./structure.md) and not here.
- Martin Fowler, _Refactoring: Improving the Design of Existing Code_, 2nd ed.
  Addison-Wesley, 2018. ISBN 978-0-134-75759-9. Chapter 3 is the smell
  catalogue; the named remedies are the catalogue's own.

Also cited, not binding:

- Kent Beck, _Extreme Programming Explained_, 2nd ed. Addison-Wesley, 2004.
  ISBN 978-0-321-27865-4. The four rules of simple design that Martin's ch. 12
  restates.
- John Ousterhout, _A Philosophy of Software Design_, 2nd ed. Yaknyam Press,
  2021. ISBN 978-1-7321022-5-1. Cited because `/codebase-design` takes its
  "deep module" idea from it, and because ch. 13 disagrees with Martin on
  comments in a way this corpus resolves in Go's favour.

### Go, which wins where they collide

- [Effective Go](https://go.dev/doc/effective_go) — the Go team's own style
  document, and the oldest of them
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the list
  of things Go reviewers actually say, maintained on the Go wiki
- [Google Go Style Guide](https://google.github.io/styleguide/go/guide) — and
  its [decisions](https://google.github.io/styleguide/go/decisions) and
  [best practices](https://google.github.io/styleguide/go/best-practices)
  pages, which are the most detailed style rules published for the language
- [Go Proverbs](https://go-proverbs.github.io/) — Pike's, short enough to
  memorise and load-bearing more often than they look
- [The Go Programming Language Specification](https://go.dev/ref/spec)

### Online, from the authorities

- [Solid Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html)
  — Martin, 2020, on which of these principles he still considers load-bearing
  twelve years on
- [The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html)
  — Martin's own correction of the most misread principle in the set
- [CodeSmell](https://martinfowler.com/bliki/CodeSmell.html) — Fowler's
  definition, including the part everyone drops: a smell is a hint, not a rule
- [Refactoring catalog](https://refactoring.com/catalog/) — the free, canonical
  list of smells and their named remedies
- [Practical Go](https://dave.cheney.net/practical-go/presentations/qcon-china.html)
  — Cheney; the closest thing Go has to a _Clean Code_ of its own, and it
  disagrees with Martin in most of the same places this page does
