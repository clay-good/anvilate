# Artifact Export Specification (delta)

## MODIFIED Requirements

### Requirement: STEP AP242 with validation properties

The primary CAD export SHALL be STEP AP242 at the latest edition the writer's kernel supports (with an AP214 fallback flag), written per the published CAx-IF/MBx-IF Recommended Practices, and MUST embed geometric validation properties — volume, surface area, centroid — so receiving CAD systems can verify import integrity. The edition actually written SHALL be recorded in the evidence bundle rather than assumed, so a bundle states which schema edition produced it. CI SHALL conformance-check exported files with an independent STEP analyzer and regression-test the reader/writer against the freely available CAx-IF/NIST MBE PMI test models.

#### Scenario: Receiving CAD verifies integrity

- **WHEN** an exported STEP is imported into a target CAD system
- **THEN** the embedded volume, area, and centroid match the received geometry within the recommended-practice tolerances

#### Scenario: AP242 is the default schema

- **WHEN** a STEP file is written with default settings
- **THEN** the file declares the AP242 schema, and PMI/validation-property content is not silently dropped by a legacy schema default

#### Scenario: The written edition is recorded, not assumed

- **WHEN** a STEP file is exported
- **THEN** the evidence bundle records the AP242 edition the writer emitted and the kernel version that emitted it, so a claim about the edition can be checked against the file rather than against a roadmap

#### Scenario: Independent referee in CI

- **WHEN** the nightly export suite runs
- **THEN** every exported STEP passes the independent analyzer's conformance checks, and any new finding against the recommended practices blocks release

## ADDED Requirements

### Requirement: 3MF export cites its standard

Additive export SHALL produce 3MF conforming to ISO/IEC 25422 semantics via the reference implementation or an equivalent validated writer, with the standard and the writer version cited in export metadata; lattice content, when shipped, SHALL use the Beam Lattice extension rather than tessellated approximations.

#### Scenario: Standard-cited print file

- **WHEN** a validated part exports as 3MF
- **THEN** the file conforms to the ISO/IEC 25422 semantics and the evidence records the standard and writer version
