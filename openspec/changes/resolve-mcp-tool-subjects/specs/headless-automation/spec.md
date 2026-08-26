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
