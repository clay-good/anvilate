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

Two of the three gates now have code behind the declaration, and the parity is tested rather
than described. `export_artifact` declares validation and watermark; its `backing` symbol is
resolved and required to take a mandatory `authorization`, so the tool cannot declare a gate
its implementation does not have — see [the export gate](export-gating.md). The sandbox gate
is the honest exception: `build_part` declares it, names no backing symbol because the
operation is unbuilt, and a test asserts it stays that way, so the day an implementation
lands somebody has to decide what discharges it.

## Still open

The server: the stateless skeleton on the 2026-07-28 revision, `structuredContent` results
with preview-image attachments, and the Tasks extension wired to real subprocess cleanup.
Gate parity is closed for the validation and watermark halves and open for the sandbox,
which has no implementation to be held to anything yet. The claim that no
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

**Every operation that is servable at all is dispatched: `compile_spec` and
`run_validation`.** Those are the two tools that are backed, bounded and servable
statelessly all at once; the other six are refused for a structural reason rather than for
want of a handler.

`compile_spec` answers with a spec or with the paths that stopped it. A document that does
not validate comes back as a **result**, not a transport error: the output schema requires
`errors` and makes `spec` optional for exactly that, because a JSON-RPC error would tell the
client its *request* was malformed when it was the document. `isError` rides on `errors`
being non-empty, so a client reading only the protocol flag and one reading the structured
content reach the same verdict.

`run_validation` answers with a scorecard — see [screening a spec](spec-screening.md) for
what a Design Spec can and cannot be screened on. Two of its decisions differ from
`compile_spec`'s and the difference is the point:

- **A document that is not a Design Spec is a malformed request here.** Its input property
  is declared as the *published Design Spec schema*, not as "a candidate document", so a
  document that does not match it fails the contract the client was handed. `-32602` with
  the paths is where that client should look.
- **`tiers` replaces the spec's own acceptance tiers rather than intersecting them.** A
  caller asking for a tier the document did not demand is asking a question, and today's
  answer for T0 and T1 — a named gap — is more useful than a silent omission.

Everything else ends in a refusal, and the kinds are worth separating:

- **`-32602`, a bad argument.** Checked against the published input schema — required
  properties present, no property outside `properties`, each value's type, and every
  `enum`, numeric bound and length the schema declares. Deliberately partial: the `$ref`s
  to the spec and scorecard schemas are **not** resolved and nested objects are not
  descended, so a structurally wrong spec passes here and is caught by the operation. A
  handler that reported "valid" after checking three keys would be claiming the schema had
  been applied — which is what the first draft did, letting a `view` of `"sideways"` and a
  `width_px` of 1 through a surface whose own schema names four views and a floor of 64.
  Array elements are held to their `items` schema, which the surface uses in exactly one
  place: `run_validation.tiers` names three tiers because the fourth is task-dispatched.
  Until that was enforced, `T3_fea` was accepted on the synchronous tool, and a misspelled
  tier reached the spec parser and came back as `spec.acceptance.tiers.0` — sending a client
  to look at its *document* for a problem in a different argument.
- **`-32000`, task-dispatched.** An unbounded tool is refused synchronously rather than
  waited on, by its declared cost rather than by name.
- **`-32000`, stateless.** One of the four above.
- **`-32000`, not dispatched yet.** The contract and the handler exist; the operation does
  not. A result invented here would be indistinguishable from a real one, which is the
  failure a published tool contract makes most likely. **No tool in today's catalog reaches
  this branch** — every servable one is wired. It stays as the net for the next tool that
  becomes servable before it is built, and a test asserts both halves: that no catalogued
  tool hits it, and that the branch itself still refuses when it is hit.

## The result is held to the same contract as the request

A published `outputSchema` is a promise about what comes back, and until `result_issues()`
existed the server made that promise and checked nothing. Now a call is checked at both
ends against the same document the client was handed: arguments in, `structuredContent`
out.

**A non-conforming result is refused, not sent.** It comes back as `-32603` naming the
offending property. A client that validates against the published `outputSchema` — which is
the entire point of publishing one — would reject the payload anyway, and it would reject it
without knowing whether the server was wrong or its own pin was.

Both dispatched handlers already conformed when the gate was written, which is the only
state in which a gate like this can be added and stay green. The evidence that it can say
no is three mutated handlers, one per shape the schema forbids: an extra property, a missing
required one, and a value of the wrong type.

The in-process check stops at the envelope, for the same reason the argument check does: it
does not resolve the `$ref`s to the spec and scorecard schemas, so a scorecard that had
drifted from the published document would cross it untouched. That half runs in CI, where
`jsonschema` resolves both references against the **released artifacts** under
`docs/api/schemas/released/` — not against `spec_json_schema()`, which is the same code that
produced the result and would agree by construction — and validates a real result of every
dispatched tool whole.

Writing the gate found a hole it was not looking for, and then the hole turned out to be
the *gate's own shape*. `export_artifact` publishes a `pattern` on its sha256 digest that
the constraint checker did not know, so `"deadbeef"` would have passed as a 64-hex digest.
The check that was supposed to catch that — "every constraint the published schemas declare
is one the check knows" — was a comparison between two **sets of keyword names**, and
adding `"pattern"` to the known set satisfied it while nothing enforced a pattern. `items`
had been sitting in that set unenforced the whole time for the same reason.

So the coverage gate is now a table of probes rather than a set of names: each keyword
carries a schema, a value that schema accepts, and every value it must refuse, and a
keyword with no probe fails. Two more mutations died on the way in — an element check that
skipped the element's *type* passes if the probe's element also declares an enum, because
the enum catches the wrong value first. `pattern` is enforced with `re.search` rather than
`re.fullmatch`, because JSON Schema's `pattern` is an unanchored match and the one pattern
in the surface anchors itself.

### A backing symbol that resolves is not a handler that calls it

`ToolDefinition.backing` names the symbol implementing an operation, and CI has always
imported it. That check cannot see the difference between a symbol a handler calls and one
it does not: `run_validation` declared `anvilate.bundle:assemble_evidence_bundle` for as
long as nothing was dispatched, and went on resolving perfectly well after the handler was
wired to `anvilate.screening:screen_spec`. The declaration is corrected, and what holds it
now is a test that replaces the named symbol with one that raises and requires the call to
raise through it.


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

[The headless CLI](headless-cli.md) follows the same rule at the shell — one backed command, three refused by name — and its exit codes are the interface a CI job reads.

[Driving Anvilate from a coding agent](agent-mcp-integration.md) is the operator's half of this page: the two-call loop that works today, the two steps of the obvious four-step loop that are not callable, and how to tell the three refusals apart.

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
