# Headless Automation Specification

## Purpose

Headless automation makes parts behave like code: a CLI with full pipeline parity, CI-friendly regeneration and validation, an official container image and CI action, geometric diffing, and an MCP server that exposes Anvilate's build/validate/export loop to coding agents. This is the "parts as code" lane no incumbent occupies.
## Requirements
### Requirement: CLI parity with the UI

The CLI SHALL expose every pipeline capability headlessly — at minimum `anvilate build`, `anvilate check`, `anvilate export`, `anvilate diff` — operating on spec files and producing the same artifacts, scorecards, and exit codes deterministically.

#### Scenario: Headless build

- **WHEN** `anvilate build spec.yaml --export step` runs on a machine with no display
- **THEN** the pipeline compiles, generates, validates, and exports exactly as the UI would, with a machine-readable scorecard written alongside

#### Scenario: Exit codes gate CI

- **WHEN** any acceptance check fails during `anvilate check`
- **THEN** the process exits non-zero with the failing checks listed on stderr and in the JSON report

### Requirement: CI regeneration of versioned parts

The system SHALL support regenerating and revalidating all specs in a repository on push — via a documented container image and a reusable CI action — publishing evidence bundles and export artifacts as CI outputs.

#### Scenario: Part regressions block merge

- **WHEN** a commit changes a shared pattern and a downstream part's validation now fails
- **THEN** the CI run fails on that part with its scorecard attached to the pipeline results

#### Scenario: Container just works

- **WHEN** the official image runs `anvilate build` on a mounted spec
- **THEN** all bundled solvers and databases resolve inside the container with no host installation

### Requirement: Geometric diff

`anvilate diff` SHALL compare two builds of a part (or a spec change) and report mass/volume/CG deltas, changed-dimension summary, and validation-verdict changes; a rendered before/after visual comparison SHALL be producible for review workflows.

#### Scenario: PR review diff

- **WHEN** a pull request changes a flange thickness
- **THEN** the diff output states the parameter change, the mass delta, and any checks that changed status, suitable for posting as a review comment

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

### Requirement: Artifact provenance hashing

Every build SHALL record a provenance graph — input spec hash, database versions, toolchain versions, generated-code hash, artifact hashes — embedded in the evidence bundle so any artifact can be traced to its exact inputs.

#### Scenario: Artifact traceability

- **WHEN** an engineer questions a STEP file found in a release
- **THEN** its embedded provenance identifies the spec revision, Anvilate version, and solver versions that produced it, and a rebuild from those inputs reproduces the identical artifact

