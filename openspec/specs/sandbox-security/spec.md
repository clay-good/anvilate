# Sandboxing, Security & Privacy Specification

## Purpose

Anvilate executes model-written code and handles IP-sensitive design data, so isolation and privacy are architectural properties, not features: sandboxed execution, a verified air-gapped mode, keychain-held credentials, and a signed, auditable supply chain.

## Requirements

### Requirement: Sandboxed execution of generated code

All model-generated code SHALL execute in a resource-limited sandbox with no network access, filesystem access restricted to a per-build scratch directory, and enforced CPU, memory, and wall-clock limits; sandbox violations SHALL terminate the execution and be logged in the iteration record.

#### Scenario: Filesystem escape blocked

- **WHEN** generated code attempts to read outside its scratch directory
- **THEN** the access fails, the iteration is marked failed with the violation, and no pipeline stage consumes its output

### Requirement: Verified air-gapped mode

In air-gapped mode, the entire pipeline — spec validation, screening, geometry, validation, export — SHALL complete with zero network calls, and this property SHALL be enforced by an automated test in CI that fails on any attempted network access.

#### Scenario: The one network path stays shut without consent

- **WHEN** a dataset fetch is requested without the user's consent for that dataset
- **THEN** it is refused before any connection is attempted, and no other code path in the package can open one

#### Scenario: CI network canary

- **WHEN** the air-gapped test suite runs the golden-path build under a network monitor
- **THEN** zero outbound connection attempts are observed, and any attempt fails the build

### Requirement: No model is called

Anvilate SHALL call no language model, local or remote: it SHALL ship no model adapter, hold no API keys, and send no spec text, file content or pipeline context off the machine. The language model is the user's own MCP agent, which sends Anvilate documents; Anvilate never sends the agent's model anything.

#### Scenario: No model client in the package

- **WHEN** the package's imports are scanned
- **THEN** only the consented dataset fetch imports a network client, so no module can reach a model endpoint

### Requirement: Solver subprocess isolation

External solvers and GPL-licensed tools SHALL run as separate subprocesses communicating through files in the build scratch directory, with the same resource limits as generated code; solver crashes MUST be contained and reported as not-evaluated checks.

#### Scenario: Solver crash contained

- **WHEN** the FEA solver segfaults on a pathological mesh
- **THEN** the application remains healthy and the scorecard reports the affected checks as not evaluated with the solver log attached

### Requirement: Supply chain integrity

Releases SHALL pin all dependency versions, publish signed artifacts and an SBOM per release, and record all bundled solver/kernel versions; the evidence bundle SHALL name the exact versions so results are attributable to a specific, verifiable toolchain.

#### Scenario: Release verification

- **WHEN** a user downloads a release
- **THEN** they can verify its signature and inspect the SBOM listing every bundled component and version

### Requirement: No default telemetry

Anvilate SHALL emit no usage data by default; any telemetry SHALL be opt-in, documented field-by-field, and disabled in air-gapped mode regardless of setting.

#### Scenario: Default install is silent

- **WHEN** a fresh install runs its first build
- **THEN** no analytics or usage events leave the machine
