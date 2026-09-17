# archify

The binding standard for Domain-Driven Design, Clean Architecture and Clean Code
in Go, shipped as a Claude Code plugin. The corpus is the product; the skills,
agent and hook are interfaces onto it.

## Language

These are the terms for talking about the standard *as an artifact*. The terms
the standard is *about* — aggregate, value object, repository — are defined on
their own pages under `standards/` and do not belong here.

**Corpus**:
Everything under `standards/`. The single source of truth; a rule that is not in
it does not bind.
_Avoid_: docs, the documentation, the guide

**Page**:
One file in the corpus, owning one topic end to end. A topic split across two
pages is a bug in the split.
_Avoid_: doc, article, section

**Rule**:
A numbered clause on a page. Findings and plans cite it as "page, rule N" —
citing the page alone is not a citation.
_Avoid_: guideline, convention, best practice

**Authority**:
A named book or author a rule descends from — Evans, Vernon, Martin, Cockburn.
Every page states its authorities; a rule with none is this project's own and
says so.
_Avoid_: source (reserved for the `## Sources` section), reference

**Precedence**:
The fixed order in which authorities win when they disagree. Averaging them
instead is the failure this project exists to prevent.
_Avoid_: hierarchy, priority

**Region**:
One of the four divisions of a bounded context — `domain`, `application`,
`adapters`, `composition` — each with a stated import rule.
_Avoid_: layer, tier, boundary

**Deviation**:
A project's deliberate departure from a rule, recorded as an ADR naming the rule
and arguing the trade-off. Unrecorded, it is a defect rather than a deviation.
_Avoid_: exception, override, waiver

**Pass**:
One ordered slice of a review, covering one rule set — direction, port
placement, transaction scope. Reviews are dispatched a pass at a time.
_Avoid_: check, phase, stage

**Standards layer**:
Where this plugin sits relative to the engineering workflow: beneath it, pulled
in by its steps, never replacing one. The same slot `/codebase-design` and
`/domain-modeling` occupy.
_Avoid_: framework, workflow, process

## Relationships

- The **Corpus** holds many **Pages**; a **Page** holds numbered **Rules**
- A **Page** names its **Authorities**, ordered by **Precedence**
- A **Deviation** names exactly one **Rule**
- A **Pass** checks a fixed set of **Rules** against a diff
- Every type in a project belongs to exactly one **Region**
