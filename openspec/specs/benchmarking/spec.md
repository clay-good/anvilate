# Benchmarking & Quality Assurance Specification

## Purpose

AnvilateBench is the measurable definition of "it works": a CI-run suite of prompt→validated-part tasks, solver verification cases, and export-fidelity checks. It gates releases, tracks the local-model recommendation, and enforces the zero-tolerance escaped-defect process.

## Requirements

### Requirement: End-to-end prompt-to-part benchmark

AnvilateBench SHALL contain at least 100 prompt→validated-part tasks spanning the pattern library, personas, and manufacturing processes, scored on: convergence (spec compiled, part validated within budget), spec conformance, geometric validity rate, wall-clock time, and iteration count; scores SHALL be tracked per release and regressions beyond documented thresholds MUST block release.

#### Scenario: Release gate

- **WHEN** a release candidate scores below the previous release on convergence rate beyond the tolerance band
- **THEN** the release is blocked pending investigation

#### Scenario: Model evaluation

- **WHEN** a new local model is evaluated monthly against AnvilateBench
- **THEN** results update the published local-model recommendation with scores per task class

### Requirement: Solver verification suite

The FEA pipeline SHALL be continuously verified against closed-form analytical cases (beam deflection, plate bending, stress concentration) and standard verification problems re-implemented from public reproductions with citations, each asserting agreement within a stated tolerance band; copyrighted benchmark publications MUST NOT be redistributed.

#### Scenario: Analytical agreement

- **WHEN** the cantilever verification case runs in CI
- **THEN** the FEA tip deflection matches the closed-form solution within its tolerance band, else the build fails

#### Scenario: Solver version bump

- **WHEN** a bundled solver version changes
- **THEN** the full verification suite runs and any drifted result blocks the upgrade until dispositioned

### Requirement: Export fidelity regression

CI SHALL verify exported artifacts continuously: STEP validity and validation-property consistency, PMI conformance checking, DXF conformance, and the automated CAD import matrix; the proprietary-CAD manual matrix SHALL run on a documented cadence with recorded results.

#### Scenario: Validation-property check

- **WHEN** a nightly build exports the benchmark part set
- **THEN** each STEP file's embedded volume/area/centroid matches independently recomputed values within tolerance

### Requirement: Dataset licensing discipline

Benchmark datasets bundled or referenced by AnvilateBench SHALL have verified redistribution-compatible licenses; non-commercial-licensed datasets MUST NOT ship in the repository and MAY only be referenced as optional external evaluations.

#### Scenario: NC dataset excluded

- **WHEN** a proposed benchmark task depends on a non-commercially-licensed dataset
- **THEN** the task is rejected or rebuilt on license-clean geometry before merge

### Requirement: External benchmark evaluation

Each release SHALL additionally be evaluated against at least one license-clean public text-to-CAD benchmark (e.g., CADGenBench-class or Text2CAD-Bench-class suites), with scores published alongside AnvilateBench results so progress is comparable to the wider field.

#### Scenario: Public comparability

- **WHEN** a release is published
- **THEN** its external-benchmark scores and the benchmark versions used are recorded in the release notes

### Requirement: Zero-tolerance escaped-defect process

An escaped defect — a green-checked part that failed physically for a reason the validation claims to model — SHALL trigger a published post-mortem and a permanent regression test reproducing the failure; the count of unresolved escaped defects MUST be zero at every release.

#### Scenario: Field failure report

- **WHEN** a user reports a validated part that failed under its modeled load case
- **THEN** the case is reproduced, root-caused, added to AnvilateBench as a regression, and the post-mortem published before the next release

### Requirement: Performance budgets in CI

The golden-path performance targets (prose→spec, spec→first solid, tier runtimes, full converged path) SHALL be measured in CI on a reference hardware profile, with sustained regressions beyond thresholds blocking release.

#### Scenario: Latency regression caught

- **WHEN** a change pushes spec→first-solid beyond its budget on the reference profile
- **THEN** CI flags the regression and the release is blocked until resolved or the budget is consciously revised
