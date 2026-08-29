# `anvilate` on the command line

Two of the four commands the spec names are backed. The other two are refused by name, with
what each is waiting on.

```bash
anvilate check part.yaml
anvilate check parts/            # every spec under a directory, recursively
anvilate check a.yaml b.yaml
```

```text
deck_plate: NOT_EVALUATED
  not_evaluated  T1 analytical
                 the Design Spec declares no structural element type, so no discipline-pack screen can be selected from it; build the pack's element and screen that
```

**A directory is searched; a file you name is taken at your word.** The difference
matters. A document *found* by searching that carries no `anvilate_spec` key is some other
YAML file — a CI config, a lockfile — and is skipped, with a line saying so rather than
silently. One you *named* is an error: you said it was a spec and it is not. An empty
search is a bad request rather than a pass, because "nothing found, nothing failed, exit 0"
is the silent green this command exists to avoid.

Over many specs the exit code is the worst verdict found, so one failing part fails the
run — what a merge gate needs.

**Every blocking check goes to stderr**, with the spec it came from, which is what a CI log
shows:

```text
anvilate check: parts/deck.yaml: not_evaluated: T1 analytical — the Design Spec declares no structural element type...
```

A check that could not run is listed too and labelled as such. It blocks exactly as hard,
and calling it a failure would be a different claim. A passing card writes nothing to
stderr at all.

`--format json` prints `{"specs": [...]}` — one object per spec with its path, its name and
its whole scorecard. A list whatever the count, because a shape that changes with the number
of arguments is a shape every caller has to branch on, and the branch is wrong the first time
a directory happens to hold exactly one spec.

`anvilate --version` reports what is **installed**, not `anvilate.__version__`. A script
asking a tool its version is asking what it is running, and a module constant answers what
somebody last typed — the same defect as a hand-written bill of materials, one file over.
The two are kept equal by a gate over all three places the version is written:
`pyproject.toml`, the module constant, and the installed distribution.

## The exit code is the interface

A CI job reads the code, not the text, so the code follows the scorecard's own rule rather
than collapsing to pass/fail:

| Code | Meaning |
| --- | --- |
| 0 | every check passed (or passed with margin to spare) |
| 1 | a check failed |
| 2 | the card could not be fully evaluated — **not a pass**, and not a failure |
| 3 | the request was wrong: a usage error, a missing file, a document that is not a spec |
| 4 | the operation is specified but unbuilt |

**Code 2 is the one that matters and No-silent-green settles it.** A screen that could not
run is not a screen that passed, so a merge gate on `anvilate check` must not go green on
it. Keeping it distinct from 1 lets a caller that genuinely wants "nothing failed" say so
deliberately, in one place, rather than getting it by accident everywhere:

```bash
anvilate check part.yaml || [ $? -eq 2 ]   # accept a not-evaluated card, on purpose
```

**A usage error is a bad request, not a verdict.** `ArgumentParser.error` exits 2,
hardcoded — so for one commit `anvilate frobnicate`, `anvilate` with no command, and
`anvilate check` with no file all came back with the code the line above tells a CI job it
may accept, and a typo read as a screen that ran and could not conclude. Every usage error
is 3 now. `--help` still exits 0, because asking for help is not a failure.

The mapping is a total map over the four scorecard statuses, so a fifth status is a
decision somebody has to make rather than a silent zero.

## `anvilate export`

```bash
anvilate export part.yaml              # the evidence bundle, rendered
anvilate export part.yaml --format json
```

The evidence bundle is assembled from a scorecard, so it needs no geometry — and the exit
code is the bundle's own roll-up, which is never better than its worst section. A DXF or a
QIF results file does need a built part, and each is refused by name:

```text
anvilate export --artifact dxf: a DXF is drawn from built geometry, and there is no built
part to draw. See openspec/specs/geometry-generation.
```

The three artifact names are the same three `export_artifact`'s published MCP schema
declares, held equal by a test — a CLI offering a fourth, or silently dropping one, is a
surface saying something different from the contract. Dropping one is how this went wrong
the first time: `export` was refused whole on the reasoning that it "writes a downstream
artifact from a built part", which is true of a DXF and false of the bundle. A refusal wide
enough to cover something that works is as misleading as a missing one.

**The bundle goes to stdout, and that is deliberate.** Every artifact-emitting entry point
in the package takes a mandatory `ExportAuthorization` ([export gating](export-gating.md)),
and there is no bundle *writer* behind that gate. Printing is not emitting — a caller
redirecting the output is doing their own act — and a file-writing path here would be the
first one outside `anvilate.export`, which is exactly the bypass the gate exists to prevent.
A test asserts the command creates no file anywhere.

## The two that are refused

`build` and `diff` need a built part, and the geometry kernel is not in this package. Each
is a named subcommand that exits 4 and says what it is waiting on:

```text
anvilate build: build runs the part's generating program, which needs a geometry kernel
this package does not ship. See openspec/specs/geometry-generation.
```

The alternative — leaving them out — makes the shell report `unknown command: build`, which
tells a script author they typed it wrong. They did not; the operation is specified and
unbuilt, and that is a different thing to be told. It is the same rule the
[MCP surface](mcp-tool-contracts.md) follows for the operations it cannot serve.


