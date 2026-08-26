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

## Four tools a stateless server cannot serve

The contracts were published before the server so that a mistake in the tool surface would
be cheap to fix. Writing the request handler found one, and it is not small:
**`render_viewport`, `measure_geometry`, `read_scorecard` and `export_artifact` name
nothing in their input to act on.** `read_scorecard` takes no arguments at all and returns
a scorecard; `export_artifact` takes a format and a destination and exports — what?

Each of them is asking the server to remember what the last call produced. That is a
session, and the headless-automation spec describes a **stateless** skeleton. The two are
different servers, and which one Anvilate ships is a design decision that had not been
made — so it is now written down as one:
[`openspec/changes/resolve-mcp-tool-subjects`](../openspec/changes/resolve-mcp-tool-subjects/proposal.md)
carries the three options and recommends content-addressed handles, which keep
protocol-level statelessness (any instance serves any call; a reconnect loses nothing)
while keeping whole geometries off the wire.

It is surfaced rather than papered over. `ToolDefinition` now declares a **`subject`**: the
required input property carrying the thing the operation acts on. The constructor refuses a
subject that is not a property of the input schema, and refuses one the schema does not
require — an optional subject is server-side state for exactly the calls that omit it.
`stateless_gaps()` is then derived from the declarations rather than listed, so giving a
tool an argument that carries its subject takes it off the list and nothing else changes.

| Tool | Subject | Servable statelessly |
| --- | --- | --- |
| `compile_spec` | `document` | yes |
| `build_part` | `spec` | yes (task-dispatched) |
| `run_validation` | `spec` | yes |
| `run_fea_validation` | `spec` | yes (task-dispatched) |
| `render_viewport` | — | **no** |
| `measure_geometry` | — | **no** |
| `read_scorecard` | — | **no** |
| `export_artifact` | — | **no** |

## The request handler

`handle_request()` is a pure function from a decoded JSON-RPC request to the object to
encode back, so a stdio loop, an HTTP handler and a test drive the same code. It serves
`initialize`, `tools/list` and `tools/call`, and returns `None` for a notification, which
the protocol says takes no response — including no error response.

**One operation is dispatched: `compile_spec`.** It is the only tool that is backed, bounded
and servable statelessly all at once, and it is the first thing an agent can call over the
wire and get an answer to. A document that does not validate comes back as a **result**,
not a transport error: the output schema requires `errors` and makes `spec` optional for
exactly that, because a JSON-RPC error would tell the client its *request* was malformed
when it was the document. `isError` on the result rides on `errors` being non-empty, so a
client reading only the protocol flag and one reading the structured content reach the same
verdict.

Everything else ends in a refusal, and the kinds are worth separating:

- **`-32602`, a bad argument.** Checked against the published input schema — required
  properties present, no property outside `properties`, each value's type, and every
  `enum`, numeric bound and length the schema declares. Deliberately partial: the `$ref`s
  to the spec and scorecard schemas are **not** resolved and nested objects are not
  descended, so a structurally wrong spec passes here and is caught by the operation. A
  handler that reported "valid" after checking three keys would be claiming the schema had
  been applied — which is what the first draft did, letting a `view` of `"sideways"` and a
  `width_px` of 1 through a surface whose own schema names four views and a floor of 64. A
  test now fails when a tool schema declares a constraint the check does not know, so the
  claim above cannot outrun the code.
- **`-32000`, task-dispatched.** An unbounded tool is refused synchronously rather than
  waited on, by its declared cost rather than by name.
- **`-32000`, stateless.** One of the four above.
- **`-32000`, not dispatched yet.** The contract and the handler exist; the operation does
  not. A result invented here would be indistinguishable from a real one, which is the
  failure a published tool contract makes most likely.

## The transport

`serve_stdio()` is the whole of it: newline-delimited JSON in, one line out per request,
flushed each time so a client blocked on a read is not waiting on a buffer. It holds no
state, so restarting it loses nothing.

Two behaviours a client depends on:

- **A notification produces no line at all.** A client waiting for one response per request
  stalls if a notification produces one.
- **A line that is not JSON does not take the stream down.** A stream is not a session: one
  client sending rubbish must not stop the server answering the message after it. The bad
  line gets a `-32700` with a null id and the loop continues.

## Running it

```bash
anvilate-mcp
```

or `python -m anvilate.mcp`. There is nothing to configure: the surface is the published
catalog, the transport is stdin and stdout, and there is no state to lose, so a client that
restarts the process is exactly where it was.

[`examples/mcp_server_session.py`](../examples/mcp_server_session.py) is the only example in
the repository that does not import the library. It starts the server as a subprocess the
way a client does and holds a short session with it — initialize, list, one real compile,
one document that fails as a *result*, and the three different things the server refuses.

A boolean is not a number, and `isinstance(True, int)` is True in Python — so `width_px:
true` would have been accepted as a pixel count by the obvious type check. Both `number`
and `integer` carry the exception.
