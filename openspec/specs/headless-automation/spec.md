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

Anvilate SHALL ship an MCP server exposing the pipeline as tools — at minimum: compile spec, build/regenerate, render viewport image, measure/inspect geometry, run validation, read scorecard, and export — so external coding agents can drive the design loop; tool responses SHALL include rendered images where visual feedback aids iteration.

#### Scenario: Agent-driven iteration

- **WHEN** an external agent calls build, then render, then validate through MCP
- **THEN** it receives the geometry summary, a viewport image, and the typed scorecard, sufficient to propose its next edit without human relay

#### Scenario: MCP inherits all gates

- **WHEN** any MCP tool triggers code execution or export
- **THEN** the same sandboxing, validation gating, and watermarking rules apply as in the UI — the MCP surface grants no bypass

### Requirement: Artifact provenance hashing

Every build SHALL record a provenance graph — input spec hash, database versions, toolchain versions, generated-code hash, artifact hashes — embedded in the evidence bundle so any artifact can be traced to its exact inputs.

#### Scenario: Artifact traceability

- **WHEN** an engineer questions a STEP file found in a release
- **THEN** its embedded provenance identifies the spec revision, Anvilate version, and solver versions that produced it, and a rebuild from those inputs reproduces the identical artifact
