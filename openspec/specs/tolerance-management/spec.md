# Tolerance Management Specification

## Purpose

Tolerance management makes every dimension's allowable variation explicit and analyzable: general tolerances applied by default, typed explicit tolerances and fits in the spec, and one-dimensional tolerance stack-up analysis across interfaces. No open-source library covers this ground; Anvilate encodes the public tolerance tables and stack-up math as a first-class, cited, versioned capability.

## Requirements

### Requirement: General tolerances by default

Every dimension without an explicit tolerance SHALL fall under a general-tolerance class (ISO 2768 linear/angular classes f/m/c/v) selected in the spec (default: medium), and the applied class MUST be stated on drawings and in the evidence bundle; the encoded tolerance tables SHALL carry source citations.

#### Scenario: Default class applied

- **WHEN** a spec omits tolerance information entirely
- **THEN** all dimensions are governed by the default general-tolerance class
- **AND** the class appears in the title block and evidence bundle

#### Scenario: Size-range lookup

- **WHEN** a 35 mm untoleranced dimension is evaluated under class m
- **THEN** the permissible deviation is resolved from the encoded ISO 2768-1 table for the 30–120 mm range with its citation

### Requirement: Typed explicit tolerances and fits

The Spec IR SHALL support explicit per-dimension tolerances as typed fields — symmetric (±), asymmetric limits, and ISO 286 fit designations (e.g., H7/g6) resolved from encoded fit tables — and explicit tolerances SHALL override the general class for that dimension.

#### Scenario: Fit resolution

- **WHEN** a spec declares a bearing bore as `fit: H7` at 22 mm nominal
- **THEN** the limit deviations are resolved from the encoded ISO 286 tables
- **AND** the drawing and DFM checks use those limits

### Requirement: Manufacturing process must achieve the tolerances

T2 DFM validation SHALL compare every explicit tolerance against the declared manufacturing process's achievable-tolerance profile and fail when a tolerance is tighter than the process can deliver, citing the rule source.

#### Scenario: Unachievable tolerance flagged

- **WHEN** a spec demands ±0.01 mm on an FDM-printed feature
- **THEN** validation fails that dimension with the process capability limit and source cited, and suggests either relaxing the tolerance or changing the process

### Requirement: One-dimensional tolerance stack-up analysis

The system SHALL compute 1D tolerance stack-ups over user-declared dimension chains (across one part or mating interfaces) using worst-case and root-sum-square methods, with optional Monte Carlo simulation, and report per-contributor sensitivities in the evidence bundle.

#### Scenario: Interface gap stack-up

- **WHEN** the user declares a chain from the mount face through the flange thickness to the motor pilot seat with a required clearance of 0.1–0.5 mm
- **THEN** the analysis reports the worst-case and RSS gap ranges, pass/fail against the requirement, and each dimension's contribution ranked

#### Scenario: Stack-up failure is a scorecard check

- **WHEN** a declared chain's worst-case range violates its requirement
- **THEN** the failure appears as a standard scorecard check with measured range, threshold, and contributing tags, eligible for the repair loop

### Requirement: Geometric tolerance declarations

The Spec IR SHALL support declaring geometric tolerances (flatness, perpendicularity, position with datum references) on tagged features, which flow to drawings as feature control frames and to STEP export as semantic PMI where supported.

#### Scenario: Datum scheme from interfaces

- **WHEN** a spec declares the ground interface as datum A and a position tolerance on the mating hole pattern
- **THEN** the declaration validates against the tag graph (datums must be real tagged features) and propagates to drawing and export layers
