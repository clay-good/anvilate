# Validation Gauntlet Specification

## Purpose

The validation engine runs every candidate part through a tiered, deterministic gauntlet — geometry checks, closed-form analytical checks, DFM rules, and finite-element analysis — and produces the scorecard: the machine-readable contract between validation and the repair loop, and the human-readable report in the UI. Cheap checks run first so FEA compute is never wasted on invalid geometry. Validation is screening-level and says so.

## Requirements

### Requirement: Tiered execution, cheapest first

Validation SHALL execute in tiers — T0 geometry, T1 analytical, T2 DFM, T3 FEA — in ascending cost order, and a tier MUST NOT run while a prior tier has unresolved hard failures.

#### Scenario: Bad geometry skips FEA

- **WHEN** T0 finds a wall below the manufacturing minimum
- **THEN** T3 FEA does not run for that iteration
- **AND** the scorecard shows T3 as "not evaluated — blocked by T0 failure"

### Requirement: T0 geometry checks

T0 SHALL verify: solid validity, envelope compliance, mass and center of gravity (from material density), minimum wall thickness, hole and edge clearance rules, and that generated interface geometry matches the resolved standard patterns exactly.

#### Scenario: Interface pattern verified

- **WHEN** a part claims a NEMA 23 interface
- **THEN** T0 measures the generated bolt pattern against the database record and fails on any deviation beyond tolerance

#### Scenario: Mass constraint checked

- **WHEN** the spec constrains mass to 150 g maximum
- **THEN** T0 reports measured mass, the threshold, and pass/fail

### Requirement: T1 analytical handbook checks

T1 SHALL run closed-form engineering checks bound to the part's patterns and interfaces — bolt shear/tension and thread engagement, bearing stress, beam deflection estimates, hole edge-distance rules, press-fit interference — implemented in pure code and unit-tested against published worked examples (Roark/Shigley class).

#### Scenario: Thread engagement check

- **WHEN** a spec fastens aluminum with M5 screws
- **THEN** T1 computes required thread engagement for the material pair and fails if the design's engagement length is insufficient

#### Scenario: Textbook regression

- **WHEN** the T1 test suite runs in CI
- **THEN** every check reproduces its published worked-example result within stated tolerance

### Requirement: T2 DFM rule packs

T2 SHALL evaluate process-specific manufacturability rules over the tagged B-Rep — CNC (tool access, internal corner radii, depth-to-diameter ratios), 3D printing (overhangs, minimum features), sheet metal (bend radii, K-factor), casting (draft angles) — selected by the spec's manufacturing process, with each rule traceable to a documented source.

#### Scenario: CNC internal corner

- **WHEN** a CNC-milled part contains an internal corner radius below the process profile's minimum
- **THEN** T2 fails with the offending edge identified by tag and location

#### Scenario: Process switch reruns rules

- **WHEN** the user changes the manufacturing process from CNC to FDM
- **THEN** the DFM tier re-evaluates under the new rule pack and the scorecard updates

### Requirement: T3 linear-static FEA per load case

T3 SHALL mesh the part and run linear-static structural analysis per spec load case, with boundary conditions and loads applied exclusively via semantic tags from audited patterns, reporting von Mises stress against yield with the required safety factor and maximum displacement against the spec limit.

#### Scenario: Cantilevered motor load

- **WHEN** the gravity and vibration quasi-static load cases run on the bracket
- **THEN** each load case reports max von Mises stress, its location by tag, the safety factor against yield, and max displacement, each with pass/fail against spec thresholds

#### Scenario: Untagged BC impossible

- **WHEN** a load case references a tag that does not resolve on the geometry
- **THEN** the FEA run is aborted and reported as a setup failure, never run with guessed boundary conditions

### Requirement: Mesh convergence gate

T3 results SHALL be accepted only after a mesh-convergence study of at least two refinements showing the governing metric changing below the gate threshold (default 5%); convergence status MUST always be displayed, and a non-converged result MUST NOT produce a green check. The convergence methodology SHALL follow recognized verification practice (Richardson-extrapolation/GCI-style grid studies).

#### Scenario: Converged result passes

- **WHEN** two successive refinements change max von Mises stress by less than 5%
- **THEN** the result is marked converged and eligible for a green check

#### Scenario: Non-converged result cannot pass

- **WHEN** refinement changes the governing metric by more than the gate
- **THEN** the check displays amber "not converged" regardless of the stress value
- **AND** export gating treats it as unpassed

### Requirement: Modal screening for vibration environments

When a spec declares a vibration environment, T3 SHALL additionally compute the first natural frequencies and compare the fundamental frequency against the spec's minimum (or a stated default separation from the declared excitation), reporting mode shapes by tagged region.

#### Scenario: Vibration prompt gets modal check

- **WHEN** the user says "machine vibrates" and the compiled spec carries a vibration environment
- **THEN** the scorecard includes a first-natural-frequency check with its threshold and provenance of the threshold (user or default)

### Requirement: Scorecard as typed contract

Every check SHALL return a typed record `{id, status, measured, threshold, units, location_tags, human_explanation}`; the full set forms the scorecard consumed by the repair loop and rendered in the report pane. Statuses SHALL be exactly: pass, fail, warning, not-evaluated.

#### Scenario: Machine-readable failure

- **WHEN** the repair loop reads a failed check
- **THEN** it receives the measured value, threshold, and the semantic tags locating the violation, sufficient to plan a repair without re-parsing prose

### Requirement: No silent green

Any check that could not run — mesh failure, missing material property, solver error — SHALL be reported as "not evaluated" with the reason; the system MUST never render a check as passed when it did not execute and complete.

#### Scenario: Mesh failure is visible

- **WHEN** meshing fails on a thin feature
- **THEN** all T3 checks show "not evaluated — mesh failure at <tag>"
- **AND** the part cannot export as validated

### Requirement: Stated assumptions on every physics result

Every FEA result SHALL carry its modeling assumptions in the report — linear elasticity, bonded contacts, idealized boundary conditions, load idealizations — and the persistent screening-analysis disclaimer; assumptions MUST appear on the rendered report, not only in metadata.

#### Scenario: Assumptions printed

- **WHEN** a validation report is rendered or exported
- **THEN** the linear-static assumptions and the "screening analysis — engineering sign-off remains with a qualified engineer" label are visible on the document

### Requirement: Extended physics tiers are roadmap-gated behind the same contract

Additional analysis types — thermal steady-state, linear buckling, fatigue screening (FKM-class), topology-optimization seeding — SHALL, when introduced, plug into the same tier/scorecard/convergence/no-silent-green contract rather than bypassing it.

#### Scenario: Buckling added later

- **WHEN** linear buckling analysis ships
- **THEN** its results appear as scorecard checks with thresholds, convergence status, and stated assumptions identical in structure to existing checks
