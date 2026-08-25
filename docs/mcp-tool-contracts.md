# The MCP tool surface: eight operations, two dispatch modes

**An agent driving Anvilate over MCP gets typed documents, not prose — and knows before it
calls whether the answer arrives in the reply or through a task handle.**

This page describes the tool *contracts*. The server itself is not built yet, which is
exactly why the contracts are pinned now: the cheapest moment to change a tool surface is
before a client has integrated against it.

```python
from anvilate.mcp import catalog_issues, tool_catalog, wire_definitions
```

`tool_catalog()` returns the typed definitions; `wire_definitions()` returns the
`tools/list` payload a client receives; `catalog_issues()` is the gate, and CI asserts it
is empty. The worked table is
[`examples/mcp_tool_catalog.py`](../examples/mcp_tool_catalog.py).

## The surface

| Tool | Dispatch | Gates inherited | Backed today by |
| --- | --- | --- | --- |
| `compile_spec` | synchronous | — | `anvilate.spec:parse_spec` |
| `build_part` | task | sandbox | not built |
| `render_viewport` | synchronous | — | not built |
| `measure_geometry` | synchronous | — | not built |
| `run_validation` | synchronous | — | `anvilate.bundle:assemble_evidence_bundle` |
| `run_fea_validation` | task | — | not built |
| `read_scorecard` | synchronous | — | `anvilate.scorecard:Scorecard` |
| `export_artifact` | synchronous | validation, watermark | `anvilate.export.qif:export_qif_results` |

Four of the eight run today. The other four say so with `None` rather than naming a symbol
that does not exist, and the four that *are* backed name a dotted path CI resolves against
the live importable surface — so a rename fails the build instead of shipping as a promise.

## Referenced, not paraphrased

A tool that consumes a spec does not describe a spec. It `$ref`s
`https://anvilate.dev/schemas/design-spec/1.1.0.json`, the artifact
[published as JSON Schema 2020-12](published-contracts.md); a tool that returns a scorecard
`$ref`s the scorecard at its version. The tool contract an agent reads and the
structured-output constraint a compiler is decoded under therefore resolve to one document,
which is the "one schema, two enforcement points" requirement made mechanical.

**The reference is written out as a literal, and that is deliberate.** Computing it from
`anvilate.contracts` would make the check that compares them vacuous — a reference derived
from the same call it is compared against agrees with itself at every version, including
the one where the tool surface should have moved and did not. Spelled out, bumping a schema
version fails `catalog_issues()` until someone re-reads the tool schemas and decides what a
client pinned to the old version is owed.

Input schemas are closed (`additionalProperties: false`). A tool schema is also the shape a
constrained decoder is held to, and a permissive schema there means a model can emit a
misspelled field name and be told it was accepted.

## What decides a task

One rule, stated once and enforced, rather than assigned tool by tool:

- **Bounded cost** — the work is a function of the input's size, and finishes at
  interactive latency. Synchronous.
- **Unbounded cost** — the work is a function of a convergence criterion or of code the
  caller supplied. Task: handle, progress, cancellation.

That is why the validation tier splits into two tools rather than one with a flag.
`run_validation` covers T0 geometry, T1 analytical and T2 manufacturability — all
closed-form or a table lookup — and returns the scorecard in the reply. `run_fea_validation`
covers T3, whose stopping condition is a convergence tolerance, and returns a handle. A
cancelled run reports its affected checks as `not_evaluated`, never as passing.

The failure this avoids has two symmetric halves, and both are real: expose everything as a
task "for consistency" and an agent polls for a result that was ready before the first poll;
expose everything synchronously and the client times out on the one call that mattered. So
the classification is checked in the constructor — a tool covering T3 that declares bounded
cost is refused, and so is one that executes caller-supplied code, because nothing bounds
the runtime of code this library did not write.

## The gates are inherited, not re-implemented

The MCP surface grants no bypass. That claim has to be visible in the definitions or it is
only a sentence in a spec, so the gates are **derived from what an operation does**:
executing caller-supplied code carries the sandbox, emitting an artifact carries the
validation gate and the watermark. A tool cannot acquire a capability and forget the rule
that goes with it, and CI asserts that every gate is still carried by at least one tool — a
gate no tool declares is a rule the surface has quietly stopped inheriting.

## Still open

The server: the stateless skeleton on the 2026-07-28 revision, `structuredContent` results
with preview-image attachments, the Tasks extension wired to real subprocess cleanup, and
the parity tests that hold the MCP paths to the same gating as the CLI. The claim that no
deprecated protocol feature is used — server-initiated sampling — belongs there too: it is
a property of what the server does, and a tool definition has no place to declare it, so
asserting it here would be a check that reads prose rather than behavior.
