# Comments

The one chapter of _Clean Code_ this standard inverts outright, and the rules
that replace it.

**Authority.** [Go Doc Comments](https://go.dev/doc/comment) and
[Effective Go](https://go.dev/doc/effective_go#commentary) — binding. Martin,
_Clean Code_, ch. 4 — binding for comments *inside* a function body, void for
doc comments. John Ousterhout, _A Philosophy of Software Design_, ch. 12–13 —
the counter-argument, and the one this standard follows.

## Why the inversion

Martin's chapter 4 states its thesis in its second paragraph:

> Comments are always failures.

The reasoning: a comment exists because the code did not say it, so the code
should be changed instead. Comments rot, code does not, and a stale comment is
worse than none.

All of that is true **of comments inside a function body**. None of it is true
of a Go doc comment, for a reason that has nothing to do with taste:

**A doc comment is not commentary on the code. It is the package's published
interface.** It is extracted by `go doc`, rendered on pkg.go.dev, shown in every
editor on hover, and is the only thing a caller who has not read your source
will ever see. Deleting it does not make the code speak for itself; it makes the
API undocumented.

Ousterhout puts the same point from the design side: the doc comment is where
the **abstraction** lives, and the abstraction is by definition not in the code
— the code is the implementation the abstraction hides. A caller who must read
your function body to learn what it does is using a shallow module.

So the rule here is the opposite of Martin's for one specific category, and
his for every other:

| Kind of comment | Verdict |
|---|---|
| Doc comment on an exported identifier | **Mandatory** |
| Package comment | **Mandatory** |
| Doc comment stating an aggregate's invariant | **Mandatory** — see below |
| Comment explaining **why** a non-obvious decision was made | **Encouraged** |
| Comment warning of a consequence (`// not safe for concurrent use`) | **Encouraged** |
| `TODO` with an owner and an issue | **Permitted** |
| Comment explaining **what** the code does | **Martin is right. Delete it** |
| Commented-out code | **Delete it** |
| Journal, changelog, attribution, section banners | **Delete it** |

## The rules

1. **Every exported identifier has a doc comment.** Type, function, method,
   constant, variable, package. No exceptions for "it's obvious" — obviousness
   is judged by a caller who cannot see the body.
2. **A doc comment begins with the identifier's name** and is a complete
   sentence: `// Place moves the order to placed. It returns ErrNoLines if …`.
   This is what makes `go doc Place` read correctly.
3. **Every package has a package comment**, on one file only. For a package of
   more than a few files, it goes in `doc.go` and nowhere else.
4. **The doc comment states behaviour, guarantees and failure modes** — what the
   caller needs to use the thing correctly. Not how it is implemented; the
   implementation is free to change and the comment must survive it.
5. **Errors are documented at the function that returns them.** "Returns
   `ErrOrderNotFound` if no order exists" is part of the contract, and a caller
   cannot write `errors.Is` against an undocumented sentinel with any
   confidence.
6. **An aggregate's doc comment states its invariant in one sentence.**
   [Aggregates](../ddd/aggregates.md) requires the invariant to be statable in
   one sentence; this is where the sentence is written down. A reviewer with no
   context must be able to read it and check the code against it.
7. **An in-body comment explains *why*, never *what*.** If it explains what,
   Martin is right and the code needs a better name, not a comment.
8. **No commented-out code.** Ever. Version control has it, and nobody deletes
   somebody else's commented-out block, so it accumulates forever.
9. **No attribution, no dates, no changelogs.** `git blame` and `git log` are
   authoritative and comments are not.
10. **`TODO` carries an owner and an issue**: `// TODO(ayman): handle partial
    shipment — #142`. A bare `TODO` is a comment nobody will ever act on.
11. **Deprecation uses the recognised marker.** A paragraph beginning
    `// Deprecated: ` is understood by tooling; prose saying "don't use this" is
    not.
12. **A comment that disagrees with the code is a defect**, reported like any
    other. It is not a style note, because the reader believed it.

## In Go

### The shape of a doc comment

```go
// Package order holds the Order aggregate: the unit of consistency for placing,
// amending and cancelling a customer's order.
//
// Nothing in this package imports outside the standard library. Persistence,
// transport and time all enter through Repository and through arguments.
package order

// Order is a customer's request to buy, from draft through to cancellation.
//
// The invariant: an order in any status other than draft has at least one line,
// and its total equals the sum of its lines. Nothing outside this package can
// construct an Order that breaks it — every field is unexported and every
// transition goes through a method.
//
// An Order is not safe for concurrent use.
type Order struct {
	id     OrderID
	status Status
	lines  []Line
	total  Money
	events []any
}

// Place moves a draft order to placed and records an OrderPlaced event, using
// now as the placement time.
//
// It returns ErrOrderNotDraft if the order has already been placed or
// cancelled, and ErrNoLines if the order is empty. On any error the order is
// unchanged.
func (o *Order) Place(now time.Time) error { ... }
```

Four things a caller learns here that the signature cannot tell them: the
invariant, the two named errors and when each occurs, that failure leaves the
aggregate untouched, and that the type is not concurrency-safe. None of that is
"a failure of the code". It is the contract.

### Why, not what

```go
// Wrong. Every one of these restates its line, and every one will survive the
// line being changed.
func (o *Order) AddLine(l Line) error {
	// check the status
	if o.status != StatusDraft {
		// return an error
		return ErrOrderNotDraft
	}
	// append the line
	o.lines = append(o.lines, l)
	// recompute the total
	o.total = o.recompute()
	return nil
}
```

```go
// Correct. The only comment left is the one the code genuinely cannot say.
func (o *Order) AddLine(l Line) error {
	if o.status != StatusDraft {
		return ErrOrderNotDraft
	}
	o.lines = append(o.lines, l)

	// Recomputed eagerly rather than on read: Total() is called from the
	// pricing path on every line change, and a lazy total would make a query
	// mutate the aggregate. See clean-code/functions.md rule 7.
	o.total = o.recompute()
	return nil
}
```

The surviving comment answers a question the reader will actually have — "why
not compute this on demand?" — and it survives a rename, a refactor and a
reformat, because it is about a decision rather than about a line.

### Comments that are a design smell

Some comments are correct and still indicate a problem:

```go
// Must be called before Save. Calling it twice corrupts the total.
func (o *Order) Recalculate() { ... }
```

A comment describing a **temporal coupling** is a true comment about a broken
design. The fix is the design: make the ordering impossible, not documented.
Same for `// don't pass nil here`, `// caller must hold the mutex`, and
`// keep this in sync with orderRow`. Each is worth writing *and* worth a ticket.

## Where comments carry weight in this standard

| Location | What the comment must say |
|---|---|
| Aggregate type | The invariant, in one sentence — [aggregates](../ddd/aggregates.md) |
| Value object constructor | What makes a value valid, if the code is not self-evident — [value objects](../ddd/value-objects.md) |
| Repository interface | Which error means "not found"; whether `Save` is optimistic — [repositories](../ddd/repositories.md) |
| Port in `application` | What the caller needs, in the caller's vocabulary — not what implements it |
| Anti-corruption layer | Which foreign concept maps to which local one, and what is deliberately dropped — [context mapping](../ddd/context-mapping.md) |
| Domain event | That it is a fact in the past, and what it does **not** promise |
| Adapter | Only the technology-specific surprises: retry behaviour, isolation level, encoding quirks |

## Formatting

Since Go 1.19, doc comments have a small, gofmt-canonicalised syntax: blank-line
paragraphs, indented code blocks, `#` headings, `- ` lists, and automatic links
to other identifiers written as `[Order]` or `[order.Repository]`. Run `gofmt`
and let it decide; it reformats doc comments as well as code. See
[formatting](./formatting.md).

Do not build section banners out of `//////` or box-drawing. A file that needs
a banner to be navigable is a file that should be two files.

## Common mistakes

| Mistake | Consequence |
|---|---|
| No doc comment on an exported identifier | The API is undocumented on pkg.go.dev and on hover |
| Doc comment not starting with the name | `go doc` output reads as a fragment |
| Restating the code | Rots on the next edit; adds reading cost and no information |
| Commented-out code | Accumulates permanently; nobody dares delete it |
| Package comment on three files | `go vet` and the renderer both object |
| Undocumented sentinel error | Callers match on message text instead |
| `// TODO` with no owner | Never done; becomes archaeology |
| "Don't use this any more" prose | Tools do not see it; `// Deprecated: ` is the marker |
| A comment that lies | The reader trusts it over the code. This is a defect, not a style note |
| Comments used to excuse a bad name | Rename the thing — this is where Martin is right |

## Checklist

- [ ] Every exported identifier has a doc comment beginning with its name
- [ ] Every package has exactly one package comment
- [ ] Each aggregate's doc comment states its invariant in one sentence
- [ ] Every returned sentinel or typed error is documented at its function
- [ ] No in-body comment restates what the line does
- [ ] Every surviving in-body comment explains a decision
- [ ] No commented-out code, no changelog, no attribution
- [ ] Every `TODO` has an owner and an issue number
- [ ] Deprecations use `// Deprecated: `
- [ ] `gofmt` has canonicalised every doc comment

## Sources

**Books.** Martin, _Clean Code_, ch. 4 — "Comments", for the taxonomy of bad
comments, which is accurate and which this page keeps in full. Its thesis that
comments are failures is the part rejected, for doc comments only. Ousterhout,
_A Philosophy of Software Design_, ch. 12–13, which argues the opposite case —
that comments are where an abstraction is defined, and that code alone cannot
express one — and which this standard follows for exported API.

**Online.** Every link below was reachable when this page was written.

- [Go Doc Comments](https://go.dev/doc/comment) — the Go team's specification of
  doc comment syntax and conventions, including the `Deprecated:` marker and
  the linking syntax
- [Effective Go: commentary](https://go.dev/doc/effective_go#commentary) — the
  original statement of the "begins with the name" convention
- [Go Doc Comments (blog)](https://go.dev/blog/godoc) — why doc comments are
  written as prose for the reader rather than as markup
- [Google Go Style Decisions: commentary](https://google.github.io/styleguide/go/decisions#commentary)
  — the most detailed published guidance on what a Go doc comment should
  contain, including documenting errors and concurrency safety
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — the
  doc-comment and comment-sentence sections, which are what Go reviewers cite
