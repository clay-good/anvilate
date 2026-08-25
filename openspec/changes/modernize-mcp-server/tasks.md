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

- [ ] 2.1 Stateless server skeleton on the 2026-07-28 revision
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
