# Design Spec IR Specification

## Purpose

The Design Spec IR is Anvilate's typed, versioned intermediate representation of engineering intent: part identity, material, manufacturing method, interfaces, load cases, constraints, and acceptance criteria. Every downstream subsystem consumes the Spec IR, never raw prose. It is the durable, diffable, auditable artifact of the product — the spec is the product, not the chat.
## Requirements
### Requirement: Typed, schema-validated document

The Spec IR SHALL be a JSON-Schema-validated document (serialized as YAML or JSON) with a declared schema version (`anvilate_spec: "<semver>"`), and the system SHALL reject any spec that fails schema validation before any downstream processing occurs.

#### Scenario: Valid spec accepted

- **WHEN** a spec document conforming to the declared schema version is submitted to the pipeline
- **THEN** it is parsed into typed objects and passed to the geometry engine

#### Scenario: Invalid spec rejected with location

- **WHEN** a spec document contains a field that violates the schema (wrong type, unknown key, out-of-range value)
- **THEN** processing stops before geometry generation
- **AND** the error identifies the offending path (e.g., `constraints.mass.max`) and the violated rule in human-readable form

### Requirement: Complete engineering intent coverage

The Spec IR schema SHALL express, at minimum: part name and description, material reference, manufacturing process and its DFM parameters, interfaces (standard components and imported mating geometry), load cases (static, quasi-static factor, remote mass), constraints (mass, envelope, safety factor, cost budget), and acceptance criteria (validation tiers to run, FEA convergence and displacement limits).

#### Scenario: Golden-path bracket expressible

- **WHEN** a user intent of the form "aluminum 6061 bracket mounting a NEMA 23 stepper to a 4040 extrusion, 1.1 kg cantilevered motor, vibration environment, under 150 g, CNC machined, safety factor 2.0" is compiled
- **THEN** every stated fact maps to a dedicated typed field in the Spec IR with no information carried only in free-text comments

#### Scenario: Units are explicit

- **WHEN** any physical quantity is stored in the Spec IR
- **THEN** it carries an explicit unit (e.g., `150 g`, `3.0 mm`, `240 MPa`)
- **AND** unit-inconsistent values are rejected at validation time

### Requirement: References resolve against curated databases

Material references and standard-component interface references in the Spec IR SHALL be database identifiers (e.g., `AA-6061-T6`, `NEMA23`, `ISO4762-M5`) that resolve against the bundled materials and standards databases; the Spec IR MUST NOT embed free-form numeric dimensions for standard components.

#### Scenario: Standard component resolved

- **WHEN** a spec declares `interfaces: [{type: standard_component, ref: "NEMA23"}]`
- **THEN** the bolt-circle diameter, pilot bore, and face dimensions are resolved from the standards database at build time
- **AND** the resolved values are recorded in the build provenance, not copied into the spec

#### Scenario: Unknown reference rejected

- **WHEN** a spec references a material or component ID absent from the databases
- **THEN** validation fails with the unknown ID named and near-miss suggestions offered

### Requirement: Reproducible and diffable

A Spec IR document plus a pinned toolchain version set SHALL be sufficient to regenerate the identical part and validation verdicts; specs MUST be plain-text serializable so that standard line-based diff tools produce meaningful diffs between revisions.

#### Scenario: CI regeneration

- **WHEN** `anvilate build spec.yaml` runs twice with the same spec, seed, and pinned toolchain versions
- **THEN** the resulting STEP artifacts are identical bit-for-bit where the geometry kernel permits
- **AND** the validation scorecards are identical

#### Scenario: Meaningful diff

- **WHEN** a user changes a single constraint (e.g., mass 150 g → 170 g) and diffs the two spec files
- **THEN** the diff shows only that semantic change

### Requirement: Spec composition via interface imports

The Spec IR SHALL support importing another part's published interface contract, so that mating parts can be designed against each other without duplicating dimensions.

#### Scenario: Mating-part contract import

- **WHEN** spec B declares an import of spec A's `mount_pattern` interface
- **THEN** spec B's geometry is generated against the exact hole pattern and mating plane published by spec A
- **AND** a later change to spec A's interface causes spec B's next build to fail validation with an interface-mismatch report rather than silently diverging

### Requirement: Assumption provenance

Every value in a compiled Spec IR SHALL be tagged with its origin: user-stated, database-resolved, or system-default; defaulted values MUST carry a human-readable rationale.

#### Scenario: Default is visible

- **WHEN** the user's prose omits a safety factor and the compiler applies the default of 2.0
- **THEN** the spec records `safety_factor: {min: 2.0, origin: default, rationale: "standard screening default; edit to override"}`
- **AND** the UI renders the value as an editable assumption chip

### Requirement: Schema versioning and migration

The Spec IR schema SHALL be versioned with semantic versioning, and Anvilate SHALL load any spec whose major schema version it supports, applying documented automatic migrations for older minor versions.

#### Scenario: Older spec loads

- **WHEN** a spec written against schema 1.0 is opened by an Anvilate release whose current schema is 1.3
- **THEN** the spec loads with migrations applied
- **AND** the user is offered a one-click rewrite of the file to the current schema version

### Requirement: Typed load combinations

The Spec IR SHALL allow load cases to carry a load-nature classification (at minimum
dead, live, roof live, snow, wind, seismic, thermal, fluid/other) and SHALL allow a spec
to declare a combination set: named combinations, each a factored sum over declared load
cases. A combination set MAY be generated from a named code basis — at minimum ASCE 7-22
strength (LRFD) and allowable-stress (ASD) combinations, with seismic system parameters
(redundancy, overstrength, vertical component) as typed user inputs — or authored fully
custom; generated sets SHALL cite the code clause per combination and record the
generator inputs. A combination referencing an undeclared load case or a case with no
nature classification where the basis requires one SHALL be rejected naming the gap.

#### Scenario: Generated LRFD set

- **WHEN** a spec declares dead, live, and wind cases and requests ASCE 7-22 LRFD
  combinations
- **THEN** the standard combinations over those natures are generated with per-combination
  clause citations, including both maximum and counteracting (0.9D) forms, and appear in
  the spec as ordinary typed data the user can inspect and edit

#### Scenario: Custom combination is first-class

- **WHEN** a user authors a custom combination 1.0D + 1.5L_test for a proof condition
- **THEN** it is stored, cited as user-defined, and evaluated identically to generated
  combinations

#### Scenario: Unclassified case rejected

- **WHEN** generation from a code basis is requested but a declared load case has no
  nature classification
- **THEN** generation is rejected naming the case — natures are never guessed from case
  names

### Requirement: Typed non-geometric callouts with persistent identity

The Spec IR SHALL support typed non-geometric callouts — at minimum surface finish
(roughness value, parameter, and production method), coating or plating (specification,
class or type, and thickness range), heat treatment (specification and resulting
condition or hardness range), and structured process notes with a category and typed
parameters — each scoped to the whole part or resolved against semantic tags, and each
rejected with a named field when its specification reference or units are invalid. Every
callout SHALL carry a persistent characteristic identifier that survives geometry
regeneration and spec revision, so a callout, the checks that consume it, and any
inspection or test that verifies it refer to the same characteristic over time.

#### Scenario: Finish scoped to a face

- **WHEN** a finish callout is applied to the `bearing_bore` tag
- **THEN** it resolves against the semantic tag graph, stores its roughness parameter and
  value with units, and is rejected naming the tag if that tag does not exist

#### Scenario: Identity survives regeneration

- **WHEN** geometry is regenerated from scratch and the spec is revised elsewhere
- **THEN** each existing callout keeps its characteristic identifier, and a diff can
  report which characteristics changed, were added, or were removed

#### Scenario: Free text stays free text

- **WHEN** a note carries no recognized category or typed parameters
- **THEN** it is stored as an unstructured note, clearly distinguished from typed
  callouts, and no check may consume it

