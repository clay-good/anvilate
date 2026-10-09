# Headless Automation Specification (delta)

## MODIFIED Requirements

### Requirement: MCP server for agent integration

Anvilate SHALL ship an MCP server targeting the 2026-07-28 protocol revision, operating
statelessly, exposing the pipeline as tools — at minimum: compile spec, build/regenerate,
render viewport image, measure/inspect geometry, run validation, read scorecard, and export
— whose input and output schemas are the same published JSON Schemas (2020-12) that define
the Spec IR and scorecard; tool results SHALL return typed `structuredContent` (never
prose-only), include rendered preview images where visual feedback aids iteration, and MUST
NOT depend on protocol features deprecated in that revision (server-initiated sampling); the
same sandboxing, validation gating, and watermarking rules apply as in the UI — the MCP
surface grants no bypass.

**Every tool SHALL identify what it acts on through its own input.** A tool whose input
names no subject requires the server to remember what a previous call produced, which is
incompatible with stateless operation; the tool surface SHALL NOT contain one. Where the
subject is an artifact too large to send on every call, the tool SHALL take a
content-addressed digest of it and resolve that digest from a store reachable by every
server instance — which is not per-connection state: any instance can serve any call and a
reconnecting client loses nothing.

#### Scenario: Agent-driven iteration

- **WHEN** an external agent calls build, then render, then validate through MCP
- **THEN** each call names its subject — the spec it builds, the digest of the geometry it
  renders, the digest of the scorecard it reads — and it receives the geometry summary, a
  viewport image, and the typed scorecard as structured content conforming to the published
  schemas, sufficient to propose its next edit without human relay

#### Scenario: A reconnecting client loses nothing

- **WHEN** a client's connection drops between two calls and it reconnects to a different
  server instance
- **THEN** the second call succeeds, because everything it acts on is named in the call
  itself rather than remembered by the instance that served the first

#### Scenario: MCP inherits all gates

- **WHEN** any MCP tool triggers code execution or export
- **THEN** the same sandboxing, validation gating, and watermarking rules apply as in the UI — the MCP surface grants no bypass

#### Scenario: One schema, two enforcement points

- **WHEN** the Spec IR schema version changes
- **THEN** the MCP tool contracts and the structured-output constraints used for LLM compilation both derive from the same schema artifact, so they cannot drift apart

## ADDED Requirements

### Requirement: Long-running validation as tasks

Pipeline operations that exceed interactive latency (FEA-class runs, full converged builds) SHALL be exposed through the MCP Tasks extension: the tool call returns a task handle, progress is reportable, cancellation is honored, and results are retrievable after completion; quick closed-form checks SHALL remain ordinary synchronous calls. A client that does not declare the Tasks extension SHALL receive the same operation's result synchronously, from the same handler, under a deadline past which the affected checks are reported not evaluated, rather than be refused the tier.

#### Scenario: Agent dispatches and returns

- **WHEN** an agent triggers a converged FEA validation through MCP
- **THEN** it receives a task handle immediately, can poll progress, and retrieves the typed scorecard when the run completes

#### Scenario: A client without tasks still gets the tier

- **WHEN** a client that declares no Tasks extension calls the FEA validation tool
- **THEN** it receives the same typed scorecard a task would have completed with, in the reply,
  rather than a refusal

#### Scenario: Cancellation is clean

- **WHEN** an agent cancels a running validation task
- **THEN** solver subprocesses terminate, the scorecard reports affected checks as not evaluated, and the system remains healthy

#### Scenario: Worker lost after launcher exit

- **WHEN** the launching server exits and its worker terminates without recording a result
- **THEN** a reconnecting client's task poll records a durable failed outcome after proving
  execution ownership has ended, without mistaking a live worker or reused PID for abandonment
- **AND** an existing terminal result is preserved and no scorecard or exit code is invented

### Requirement: Registry publication

Each Anvilate release SHALL publish the MCP server to the official MCP registry with accurate metadata (capabilities, version, install command), so agent clients can discover and install it without repository archaeology.

#### Scenario: One-click discovery

- **WHEN** a user searches the official MCP registry for engineering validation
- **THEN** the current Anvilate server release appears with a working install command
