# Assembly & Robotics Export Specification

## Purpose

Small rigid assemblies as typed compositions of parts with declared joints, exported as STEP assemblies and as robot description formats (URDF, MJCF) with physically correct mass properties. Deterministic joint placement — not a numerical constraint solver — keeps assembly behavior reproducible for agents and CI. Full kinematic assembly design remains out of scope.

## Requirements

### Requirement: Typed assemblies of parts and joints

An assembly SHALL be a Spec IR document composing part specs with explicit joint declarations (rigid, revolute, linear, cylindrical, ball) between tagged interface features; joint placement SHALL be resolved by deterministic transforms, and declared joint-limit violations MUST fail the build.

#### Scenario: Motor on bracket assembly

- **WHEN** an assembly spec joins the motor (as an envelope model) to the bracket's `motor_mount_pattern` with a rigid joint
- **THEN** the assembly resolves deterministically with the motor positioned by the interface contract

#### Scenario: Joint limit violation

- **WHEN** a revolute joint's declared range is violated by the assembled pose
- **THEN** the build fails with the joint and violation identified

### Requirement: Assembly-level validation

Assembly builds SHALL run interference detection between all component pairs and verify that every joint's mating interfaces satisfy their contracts; detected interference MUST appear as a scorecard failure with the offending parts and overlap volume.

#### Scenario: Interference caught

- **WHEN** two components overlap by more than the declared fit allowance
- **THEN** validation fails with both part names, the overlap volume, and its location

### Requirement: STEP assembly export

Assemblies SHALL export as STEP AP242 with the assembly tree, per-component names, and transforms preserved, importing as a structured assembly (not a fused lump) in the supported CAD matrix.

#### Scenario: Assembly opens structured

- **WHEN** the exported assembly STEP opens in a target CAD system
- **THEN** components appear as named instances in an assembly tree with correct placement

### Requirement: URDF and MJCF export with exact mass properties

Robot-description export SHALL emit URDF and MJCF with: link mass, center of mass, and inertia tensors computed exactly from the B-Rep and material density; joint definitions mapped from the assembly's typed joints; separate visual meshes and convex-decomposed collision meshes.

#### Scenario: Simulation-ready URDF

- **WHEN** the bracket-motor assembly exports as URDF
- **THEN** each link carries geometry-derived inertial properties and the revolute joint maps with its axis and limits, loading without errors in standard robotics simulators

### Requirement: Inertia sanity gate

Robot-description exports SHALL pass a physical-plausibility gate before writing: positive-definite inertia tensors satisfying the triangle inequality, mass consistent with volume × density, and center of mass inside the convex hull; failures block export with the offending link named.

#### Scenario: Corrupt inertia blocked

- **WHEN** a computed inertia tensor violates the triangle inequality (indicating a geometry or density error)
- **THEN** the export aborts with the link and failed invariant reported, rather than emitting a simulator-crashing file
