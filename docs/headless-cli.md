# `anvilate` on the command line

One command is backed today. The other three the spec names are refused by name, with what
each is waiting on.

```bash
anvilate check part.yaml
```

```text
deck_plate: NOT_EVALUATED
  not_evaluated  T1 analytical
                 the Design Spec declares no structural element type, so no discipline-pack screen can be selected from it; build the pack's element and screen that
```

`--format json` prints the whole scorecard instead — every entry, every status, every
detail — for a script that wants more than the verdict.

## The exit code is the interface

A CI job reads the code, not the text, so the code follows the scorecard's own rule rather
than collapsing to pass/fail:

| Code | Meaning |
| --- | --- |
| 0 | every check passed (or passed with margin to spare) |
| 1 | a check failed |
| 2 | the card could not be fully evaluated — **not a pass**, and not a failure |
| 3 | the request was wrong: a missing file, a document that is not a valid spec |
| 4 | the operation is specified but unbuilt |

**Code 2 is the one that matters and No-silent-green settles it.** A screen that could not
run is not a screen that passed, so a merge gate on `anvilate check` must not go green on
it. Keeping it distinct from 1 lets a caller that genuinely wants "nothing failed" say so
deliberately, in one place, rather than getting it by accident everywhere:

```bash
anvilate check part.yaml || [ $? -eq 2 ]   # accept a not-evaluated card, on purpose
```

The mapping is a total map over the four scorecard statuses, so a fifth status is a
decision somebody has to make rather than a silent zero.

## The three that are refused

`build`, `export` and `diff` all need a built part, and the geometry kernel is not in this
package. Each is a named subcommand that exits 4 and says what it is waiting on:

```text
anvilate build: build runs the part's generating program, which needs a geometry kernel
this package does not ship. See openspec/specs/geometry-generation.
```

The alternative — leaving them out — makes the shell report `unknown command: build`, which
tells a script author they typed it wrong. They did not; the operation is specified and
unbuilt, and that is a different thing to be told. It is the same rule the
[MCP surface](mcp-tool-contracts.md) follows for the operations it cannot serve.

`export` is the one worth reading twice: the export gate and the writers *do* exist
([export gating](export-gating.md)), and what is missing is a built part to hand them from
a spec file alone.
