# Smells and heuristics

_Clean Code_ chapter 17, filtered: what binds in Go, what does not, and where
each one routes.

**Authority.** Martin, _Clean Code_, ch. 17 — "Smells and Heuristics", and
ch. 12 — "Emergence". Fowler, _Refactoring_ (2nd ed.), ch. 3, for the smell
catalogue `/code-review` carries as its baseline.

## What this page is for

A smell is not a defect. Fowler's own definition is the part people drop:

> a surface indication that usually corresponds to a deeper problem in the
> system … Smells don't always indicate a problem.

So this page is a **sweep**, not a rule set. Work it when a change is finished
and before it is proposed. Anything it catches is a question to ask, and the
answer is sometimes "no, this is correct here".

It complements the model-level list at the end of
[`ddd/anti-patterns.md`](../ddd/anti-patterns.md), which catches failures of
*modelling*. This page catches failures of *code*. The two do not overlap, and
when both could apply, the anti-patterns page is the more specific rule.

## The four rules of simple design

Beck's rules, which Martin's ch. 12 restates, and which are the ranking this
page uses when two smells suggest opposite fixes. **The order is the rule:**

1. **The tests pass.** Design that does not work is not design.
2. **It reveals intention.** Names, structure and flow say what the code is for.
3. **There is no duplicated knowledge.**
4. **It has the fewest elements** — types, methods, packages.

Rule 2 outranks rules 3 and 4, and that resolves most arguments this page
produces. An abstraction that removes duplication at the cost of obscuring
intent is a net loss. So is one that reduces the element count by merging two
concepts that happen to look alike.

## Duplication — and the one Go proverb that qualifies it

Martin calls duplication "the primary enemy of a well-designed system", and
chapter 17's G5 is the longest entry in the chapter. It binds — with a
qualification Go states explicitly:

> A little copying is better than a little dependency.

Both are right, because they are about different things:

- **Duplicated knowledge is always a defect.** A business rule expressed in two
  places will be changed in one. A validation rule, a tax calculation, a state
  transition, a status mapping — one place, always. In this standard that place
  is usually the model, which is the point of the model.
- **Duplicated code is sometimes correct.** Two structs with the same fields,
  two table-test scaffolds, two adapters that both do `rows.Scan` in a similar
  shape — these are coincidence, not knowledge. Merging them couples two things
  that will diverge, and the coupling is worse than the copy.

The test: **when this changes, does the other one have to change for the same
reason?** If yes, it is one thing and duplication is a defect. If no, it is two
things that look alike, and a shared helper is premature coupling.

Rule of three: two occurrences is an observation, three is a pattern.

## The heuristics that bind

Grouped as Martin groups them, with the Go reading and the page that owns each.

### Names

| | Heuristic | In Go | Owner |
|---|---|---|---|
| N1 | Choose descriptive names | Descriptive **and** scope-proportional — this is the one inversion | [naming](./naming.md) |
| N2 | Choose names at the appropriate level of abstraction | A port is named for the need, not the technology | [naming](./naming.md) |
| N3 | Use standard nomenclature | `-er` interfaces, `New…`, `ByID`, `String()` | [naming](./naming.md) |
| N4 | Unambiguous names | No `Data`, `Info`, `Manager`, `Processor` | [naming](./naming.md) |
| N5 | Long names for long scopes | Inverted in wording, identical in effect | [naming](./naming.md) |
| N7 | Names should describe side effects | A `Validate` that also saves is a lie | [functions](./functions.md) |

### Functions

| | Heuristic | In Go | Owner |
|---|---|---|---|
| F1 | Too many arguments | A signal past three, not a limit — usually a missing value object | [functions](./functions.md) |
| F2 | Output arguments | Pointer-out parameters instead of return values | [functions](./functions.md) |
| F3 | Flag arguments | `Ship(o, true)` — unreadable at the call site | [functions](./functions.md) |
| F4 | Dead function | No compile error in Go; `unused`/`deadcode` linters catch it | [formatting](./formatting.md) |

### Comments

| | Heuristic | In Go | Owner |
|---|---|---|---|
| C1 | Inappropriate information | Changelogs, authors, ticket numbers in comments | [comments](./comments.md) |
| C2 | Obsolete comment | A comment that disagrees with the code is a defect | [comments](./comments.md) |
| C3 | Redundant comment | `// increment i` | [comments](./comments.md) |
| C5 | Commented-out code | Delete it; `git` has it | [comments](./comments.md) |

### General

| | Heuristic | In Go | Owner |
|---|---|---|---|
| G5 | Duplication | Qualified above: knowledge, not lines | this page |
| G6 | Code at the wrong level of abstraction | A rule in `application`, SQL in `domain` | [`structure.md`](../structure.md) |
| G7 | Base classes depending on derivatives | Rare in Go; appears as a package importing its own adapter | [`structure.md`](../structure.md) |
| G8 | Too much information | A package exporting thirty identifiers; a nine-method port | [types and packages](./types-and-packages.md), [SOLID](./solid.md) |
| G9 | Dead code | Unreferenced exported functions; `if` branches that cannot run | [formatting](./formatting.md) |
| G10 | Vertical separation | A helper three hundred lines from its caller | [formatting](./formatting.md) |
| G11 | Inconsistency | Two names for one concept; two error styles in one package | [naming](./naming.md) |
| G13 | Artificial coupling | A `platform` package importing a context's `domain` | [`structure.md`](../structure.md) |
| G14 | Feature envy | Behaviour in a service that reads an aggregate's state | [aggregates](../ddd/aggregates.md) |
| G15 | Selector arguments | Same as F3 | [functions](./functions.md) |
| G16 | Obscured intent | Dense one-liners, unnamed intermediate results | [functions](./functions.md) |
| G18 | Inappropriate static | A package-level mutable variable used as state | [types and packages](./types-and-packages.md) |
| G19 | Use explanatory variables | Name the intermediate rather than commenting it | [comments](./comments.md) |
| G20 | Function names should say what they do | And everything they do | [functions](./functions.md) |
| G21 | Understand the algorithm | Code that "works" but nobody can state why | — |
| G22 | Make logical dependencies physical | An assumption about another package, unstated and unenforced | [boundaries](./boundaries.md) |
| G25 | Replace magic numbers with named constants | And a domain quantity is a value object, not a constant | [value objects](../ddd/value-objects.md) |
| G26 | Be precise | `float64` for money; `string` for a closed set | [value objects](../ddd/value-objects.md) |
| G28 | Encapsulate conditionals | A named condition, and when it has a business name, a **specification** | [specifications](../ddd/specifications.md) |
| G29 | Avoid negative conditionals | `IsPlaced()` over `!IsNotPlaced()` | [naming](./naming.md) |
| G30 | Functions should do one thing | The rule that replaces the line count | [functions](./functions.md) |
| G31 | Hidden temporal coupling | "Call `Recalculate` before `Save`" — make it impossible, not documented | [comments](./comments.md) |
| G32 | Don't be arbitrary | A file, package or layout with no reason behind it | [formatting](./formatting.md) |
| G33 | Encapsulate boundary conditions | `+1`/`-1` scattered; off-by-one logic repeated | [value objects](../ddd/value-objects.md) |
| G34 | Functions should descend one level of abstraction | Rule 2 on the functions page | [functions](./functions.md) |
| G35 | Keep configurable data at high levels | Config is read in `composition` and passed down as values | [boundaries](./boundaries.md) |
| G36 | Avoid transitive navigation | The Law of Demeter; across aggregates, reference by identity | [types and packages](./types-and-packages.md) |

### Tests

T1–T9 — insufficient tests, no coverage tool, skipping trivial tests, ignored
failing tests, untested boundary conditions, incomplete coverage of a bug's
neighbourhood, patterns in failures, test speed — all bind, and all route to
[tests](./tests.md). Two are worth restating because they are the ones skipped:

- **An ignored or skipped test is a lie in the suite.** Delete it or fix it; a
  permanently skipped test is worse than a missing one because it reports as
  present.
- **A bug gets a test in the neighbourhood of the bug**, not only on the exact
  input that was reported.

## The heuristics that do not bind

| | Heuristic | Why not |
|---|---|---|
| G23 | Prefer polymorphism to `if`/`else` or `switch`/`case` | A type switch or a `switch` over a closed set is idiomatic Go. Settled for the smell baseline in [`vocabulary.md`](../vocabulary.md) |
| — | "Functions should be four lines / under twenty" (ch. 3) | Rejected on [functions](./functions.md) and on the [index](../clean-code.md) |
| — | "Comments are always failures" (ch. 4) | Inverted for doc comments on [comments](./comments.md) |
| — | "Use exceptions rather than return codes" (ch. 7) | Go has none. [error handling](./error-handling.md) |
| — | "One assert per test" (ch. 9) | Inverted to one **concept** per test. [tests](./tests.md) |
| G17 | Misplaced responsibility, applied to the anaemic/rich split | The DDD rule is stricter and more specific: [aggregates](../ddd/aggregates.md) |
| N6 | Avoid encodings | Mostly a rule against Hungarian notation, which nobody writes; the Go rule about type-in-name is on [naming](./naming.md) |
| E1–E2 | "Build requires more than one step", "Tests require more than one step" | True and trivially satisfied: `go build ./...`, `go test ./...` |

## Against the `/code-review` smell baseline

`/code-review`'s Standards axis carries a fixed set of Fowler smells and binds
them with one rule: **the repo overrides — a documented repo standard always
wins.** archify is that documented standard.

| Smell | Here |
|---|---|
| **Middle Man** | **Suppressed.** A thin application service is correct by design |
| **Repeated Switches** | **Suppressed.** A type switch over domain events is idiomatic Go |
| **Primitive Obsession** | **Reinforced** → [value objects](../ddd/value-objects.md) |
| **Data Clumps** | **Reinforced** → [value objects](../ddd/value-objects.md) |
| **Message Chains** | **Reinforced** → reference other aggregates by identity |
| **Feature Envy** | **Reinforced** → behaviour belongs with the state it reads |

The reasoning for both suppressions is on
[`vocabulary.md`](../vocabulary.md). **Cite it; do not re-argue it in a review**
— that is exactly the argument this corpus exists to have once.

Where a reinforced smell and an archify page both apply, the finding cites the
archify page, because it names a rule the author can act on rather than a
tendency.

## How to run the sweep

1. Read the diff once for **intent**: can you say what it does without reading
   the ticket?
2. Read it again for **duplicated knowledge** — is a rule here also somewhere
   else?
3. Check **names** against `CONTEXT.md`.
4. Check **imports** against the region table — cheapest, catches the most
   expensive problems.
5. Walk the tables above for anything the diff introduced.
6. Stop. A sweep that produces twenty findings has become a rewrite proposal,
   and [`archify:review-passes`](../../skills/review-passes/SKILL.md) is
   explicit that the standard is a ratchet applied to the diff, not to the tree.

## Checklist

- [ ] No business rule appears in two places
- [ ] Nothing was merged because it looked alike rather than meant the same
- [ ] No dead code, no commented-out code, no obsolete comment
- [ ] No magic number and no primitive standing in for a domain concept
- [ ] Every non-obvious condition is named, and a business rule is a specification
- [ ] No temporal coupling documented rather than prevented
- [ ] No function whose name understates what it does
- [ ] No skipped or ignored test
- [ ] Suppressed smells were not reported; reinforced ones cite the archify page
- [ ] The sweep stayed inside the diff

## Sources

**Books.** Martin, _Clean Code_, ch. 17 — "Smells and Heuristics", the list this
page filters, and ch. 12 — "Emergence", for the four rules of simple design.
Kent Beck, _Extreme Programming Explained_ (2nd ed.), for those four rules in
their original form and order. Fowler, _Refactoring_ (2nd ed.), ch. 3 — the
smell catalogue, and chs. 6–12 for the named remedies; the catalogue is the
baseline `/code-review` carries.

**Online.** Every link below was reachable when this page was written.

- [CodeSmell](https://martinfowler.com/bliki/CodeSmell.html) — Fowler's
  definition, including the caveat that a smell is a hint and not a rule
- [Refactoring catalog](https://refactoring.com/catalog/) — the free, canonical
  list of smells and the refactorings that address them
- [Go Proverbs](https://go-proverbs.github.io/) — "A little copying is better
  than a little dependency", the qualification on G5 above
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — what Go
  reviewers actually raise, which is the closest thing to a Go-native version of
  chapter 17
- [golangci-lint](https://golangci-lint.run/) — the linters that catch the
  mechanical entries here (`unused`, `ineffassign`, `errcheck`, `gocritic`) so
  that human review is spent on the ones that need judgement
