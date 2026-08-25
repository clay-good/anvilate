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

- [~] 2.1 Stateless server skeleton on the 2026-07-28 revision — `handle_request` is
      the transport-agnostic half: `initialize`, `tools/list` and a `tools/call` that
      validates and refuses. The transport and the dispatch are still open, and four tools
      cannot be served statelessly at all (below)
- [ ] 2.2 structuredContent results + preview-image attachments
- [ ] 2.3 Tasks extension: handles, progress, cancellation with subprocess cleanup
- [ ] 2.4 Gate parity tests: sandbox/export gating identical to CLI paths

## 3. Release

- [ ] 3.1 Registry publication automation per release
- [ ] 3.2 Conformance run against the protocol test suite

## 4. Docs

- [ ] 4.1 Agent-integration guide: driving Anvilate from a coding agent, with the
      build-validate-read-scorecard loop

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

Still open in 2.1: the transport (stdio and HTTP), and the dispatch of the four backed
operations — which waits on the session-versus-stateless decision above for three of them.
