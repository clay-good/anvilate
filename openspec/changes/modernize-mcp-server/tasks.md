# Tasks: MCP server on the 2026-07-28 protocol

## 1. Contracts

- [x] 1.1 Publish the Spec IR and scorecard JSON Schemas as standalone versioned artifacts
      — `anvilate.contracts` generates both as JSON Schema 2020-12 from the models, and
      `docs/api/schemas/` carries the artifacts. The gate has two halves: the artifact must
      match the model, **and** a changed artifact must carry a moved version, because a
      client pinned to a version fetching different content under the same `$id` is the
      silent breaking change this task exists to prevent. `jsonschema` is a dev dependency,
      so the meta-schema check and a real-scorecard round trip run in CI on every push to
      `main` and every pull request, rather than skipping the way an opt-in check would
- [x] 1.2 Map pipeline operations to tool definitions with 2020-12 input/output schemas
      — `anvilate.mcp` carries the eight operations the headless-automation spec names,
      each with a closed 2020-12 object schema in and out. A tool that consumes a spec or
      returns a scorecard `$ref`s the published artifact at its version rather than
      describing it, so the tool surface and the structured-output constraint resolve to
      one document
- [x] 1.3 Define the task-exposed operation set (FEA-class) vs. synchronous set (T0–T2)
      — decided by one declared property, `Cost`, and cross-checked in the constructor
      rather than assigned tool by tool

## 2. Implementation (when the server is built)

- [x] 2.1 Stateless server skeleton on the 2026-07-28 revision — `handle_request`
      (transport-agnostic) and `serve_stdio` (newline-delimited JSON). **Both servable
      operations are now dispatched**: `compile_spec`, and `run_validation` over
      `anvilate.screening.screen_spec`. The other six are refused for a structural reason
      rather than for want of a handler — two are task-dispatched by declared cost and four
      cannot be served statelessly at all (below). The "not dispatched yet" refusal is
      unreached by any catalogued tool and asserted so in both directions.
- [x] 2.2 structuredContent results — **done**; preview-image attachments are blocked on
      `render_viewport`, which is one of the four operations a stateless server cannot serve
      (see 2.1), so there is nothing to attach an image to yet. Both dispatched tools return
      `structuredContent` beside the text content, and `result_issues` now holds it to the
      tool's own published `outputSchema` before it goes on the wire: a non-conforming result
      is `-32603` naming the property rather than a payload a client validating against the
      contract would reject without knowing which side was wrong. The gate was written while
      both handlers already conformed — the only state in which one can be added and stay
      green — so the evidence it can say no is three mutated handlers, one per forbidden
      shape. The in-process check stops at the envelope for the same reason the argument
      check does; CI resolves the spec and scorecard `$ref`s against the **released
      artifacts** (not `spec_json_schema()`, which would agree by construction) and validates
      a real result of every dispatched tool whole. Two findings fell out of writing it: the
      constraint checker did not know `pattern`, so `export_artifact` could have returned
      `"deadbeef"` as a 64-hex digest; and `run_validation` still declared
      `anvilate.bundle:assemble_evidence_bundle` as its `backing` after being dispatched to
      `anvilate.screening:screen_spec`, because an import check cannot tell a symbol a
      handler calls from one it merely resolves. The declaration is corrected and the named
      symbol is now replaced with one that raises, so the call has to raise through it
- [ ] 2.3 Tasks extension: handles, progress, cancellation with subprocess cleanup
- [ ] 2.4 Gate parity tests: sandbox/export gating identical to CLI paths — the export
      half is **done**, the sandbox half cannot be done yet. Writing the parity test found
      that the validation and watermark gates had no implementation on *either* side to be
      compared: `Gate.WATERMARK` appeared nowhere outside `mcp.py`, and the DXF exporters
      wrote a cuttable file from a width, a height and a list of holes. `anvilate.export.gate`
      is that gate, every artifact-emitting export entry point now requires an
      `ExportAuthorization`, and `tests/test_export_gate.py` resolves `export_artifact`'s
      `backing` symbol and requires it to take one — so "the MCP surface grants no bypass"
      is a claim that can fail. The sandbox gate is declared by `build_part`, which names no
      backing symbol because the operation is unbuilt; a test asserts it stays undischarged,
      so an implementation cannot land without someone deciding what discharges it.

## 3. Release

- [ ] 3.1 Registry publication automation per release
- [ ] 3.2 Conformance run against the protocol test suite

## 4. Docs

- [x] 4.1 Agent-integration guide: driving Anvilate from a coding agent —
      `docs/agent-mcp-integration.md`. **The loop the task names is the thing the page has
      to say is missing.** Build-validate-read-scorecard is four steps and two of them are
      not callable: `build_part` is task-dispatched with the Tasks extension unbuilt, and
      `read_scorecard` takes no arguments and returns a scorecard, which is a session. So
      the shape that works is two calls with the card read out of the validation reply, and
      writing the guide around the four-step loop would have documented a client nobody can
      write. The page also gives the answer most agents will actually get — the analytical
      tier `not_evaluated` on every spec, naming the missing element type — because a guide
      whose worked example is the happy path teaches a status handling that reads a check
      which could not run as one that passed. Four worked examples, each executed in its own
      process in CI with its printed output compared byte for byte; the unservable and
      task-dispatched lists are derived from `stateless_gaps()` and the declared costs, so
      prose that outlives the surface fails; and every backticked tool name is resolved
      against the catalog, since a renamed tool leaves its old name in the prose reading
      exactly as right as the new one

## Scope as shipped (1.2, 1.3)

`src/anvilate/mcp.py`, `examples/mcp_tool_catalog.py`, `docs/mcp-tool-contracts.md`. The
contract half of the server, pinned before the server exists — the cheapest moment to
change a tool surface is before a client has integrated against it.

**The schema references are written out as literals, and the first draft did not do that.**
Deriving `$ref` from `anvilate.contracts` made the check that compares them vacuous: a
reference computed from the same call it is compared against agrees with itself at every
version, including the one where the tool surface should have moved and did not. Spelled
out, a schema bump fails `catalog_issues()` until someone re-reads the tool schemas and
decides what a client pinned to the old version is owed.

**The dispatch split is a property, not a per-tool judgement.** `Cost.UNBOUNDED` means the
work is bounded by a convergence criterion or by caller-supplied code; everything else
answers in the reply. A tool covering T3 that declares bounded cost is refused in the
constructor, because T3's stopping condition is a convergence tolerance and a convergence
tolerance is not a bound on wall time. That is why the validation tier is two tools rather
than one with a flag.

**Four of the eight operations are backed today and name the symbol**, which CI resolves
against the live importable surface — the same rule the agent skill follows. The other four
carry `None` rather than naming something that does not exist.

**One test was written and deleted.** A "declares no deprecated protocol feature" check that
grepped the rendered definitions for `sampling` matched the prose in `compile_spec`'s own
description, which says the server initiates no sampling. A gate satisfiable — or breakable
— by ordinary English is not a gate: the claim is about what the server does at run time,
and it belongs with section 2.

**Audited an hour later, and the gate had the blind spot the gate exists to prevent.**
`_schema_issues` walked only a schema's top-level `properties` for contract references —
which is where every reference in the shipped catalog happens to sit, so the check agreed
with the catalog it was written against and would go on reporting clean the moment a
reference moved inside an `items`, a `oneOf`, or a nested object. It walks the whole
document now, with three nested mutations asserting it. Second finding, the documented
pydantic trap again: `frozen=True` does not reach inside a `dict` field, so a definition's
schema dictionaries were writable and `to_wire` handed out the live ones. `to_wire`
deep-copies now, and the docstring says what `frozen` does and does not cover instead of
implying it covers everything.

## 2026-08-25 — the request handler, and the four tools it cannot serve

`handle_request`, `stateless_gaps` and `ToolDefinition.subject` in `src/anvilate/mcp.py`;
`docs/mcp-tool-contracts.md`.

**Publishing the contracts first paid, and the bill was bigger than expected.**
`render_viewport`, `measure_geometry`, `read_scorecard` and `export_artifact` name nothing
in their input to act on — `read_scorecard` takes no arguments at all and returns a
scorecard. Each is asking the server to remember what the last call produced. That is a
session, and 2.1 says stateless. **Which server Anvilate ships is a decision that had not
been made, and it is cheaper to make it now than after a client integrates.**

Surfaced rather than resolved by inventing arguments. `ToolDefinition.subject` names the
required input property carrying what the operation acts on; the constructor refuses a
subject that is not in the schema and refuses one the schema does not require, because an
optional subject is state for exactly the calls that omit it. `stateless_gaps()` is derived
from the declarations, so giving a tool its subject takes it off the list and nothing else
is edited.

**The handler dispatches nothing, and says so in the refusal.** A plausible-looking result
from an operation nobody wired is indistinguishable from a real one, which is the failure a
published tool contract makes most likely. Three refusal kinds are separated: a bad
argument (-32602), task-dispatched by declared cost (-32000), and not servable statelessly
(-32000).

**The argument check is deliberately partial and the docstring says which part.** It does
not resolve the `$ref`s to the published spec and scorecard schemas, so a structurally
wrong spec passes it. Reporting "valid" after checking three keys would be claiming the
schema had been applied.

**`isinstance(True, int)` is True in Python and a boolean is not a number in JSON.** The
first draft excepted `number` and not `integer`, so `width_px: true` would have been
accepted as a pixel count on the only integer field in the surface.

**One operation is dispatched, and it is the honest one to start with.** `compile_spec` is
the only tool that is backed, bounded *and* servable statelessly, so it is the first thing
an agent can call over the wire and get an answer to. A document that does not validate
comes back as a result with its error paths rather than a JSON-RPC error, because the
request was fine and the document was not — and `isError` rides on that same list so the
two cannot disagree.

**The transport is nine lines and two of them are behavioural.** A notification produces no
output line, because a client waiting for one response per request stalls otherwise; and a
line that is not JSON gets a parse error and the loop continues, because a stream is not a
session.

**Runnable as a process**: `anvilate-mcp` (a console script) or `python -m anvilate.mcp`,
with `examples/mcp_server_session.py` driving it as a real subprocess — the only example in
the repository that does not import the library, because a transport tested only through
its own function is a transport nobody has run.

**Audited an hour later, and both findings were in the handler's own edges.** The version
check ran *before* the notification check, so a notification with a missing or wrong
`jsonrpc` produced an error line — a spurious response in a stream a client reads one
response per request. A message with no `id` has nothing to answer to, so that check has to
come first; the half that must not be lost to the fix is that a request *with* an id and a
bad version is still an error, and both are pinned.

And the argument check enforced `type` and nothing else, so `view: "sideways"` and a
`width_px` of 1 reached the stateless refusal — which reports the wrong problem entirely.
`enum`, the four numeric bounds, `minLength` and `minItems` are checked now, and **a test
fails when a tool schema declares a constraint the check does not know**, so the
docstring's claim cannot outrun the code. That gate found two more constraints
(`minLength`, `minItems`) the moment it was written.

**The decision this surfaced is now its own change.** `resolve-mcp-tool-subjects` carries
the contradiction, the three options and a recommendation (content-addressed handles, which
keep protocol-level statelessness while keeping payloads off the wire). It is a design
choice about what Anvilate's MCP surface *is*, not an implementation detail, so it is
proposed rather than decided here — and the enforcement lives in code meanwhile:
`stateless_gaps()` derives the four and `handle_request` refuses them with the reason, so
nothing can quietly serve one by guessing.

Still open in 2.1: an HTTP transport, and the dispatch of the three remaining backed
operations — which waits on the session-versus-stateless decision above.
