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

### Requirement: Combination-aware evaluation with a named governing combination

When a spec declares a combination set, the gauntlet SHALL evaluate applicable checks
under every combination in the set, report the enveloped (worst-case) result per check,
and name the governing combination in the scorecard entry and evidence bundle; results
under non-governing combinations SHALL remain retrievable. Evaluating a subset of the
declared combinations SHALL render the affected checks "not evaluated" for the skipped
combinations — never a pass computed from a silent subset. When no combination set is
declared, per-load-case evaluation proceeds exactly as today.

#### Scenario: Governing combination named

- **WHEN** a beam check runs under a declared LRFD set where 1.2D + 1.6L governs
- **THEN** the scorecard entry reports the enveloped margin and names 1.2D + 1.6L as
  governing, with the per-combination results retrievable

#### Scenario: Counteracting combination catches uplift

- **WHEN** a wind case opposes gravity and the 0.9D + 1.0W combination produces the
  worst margin
- **THEN** the envelope reflects it — minimum-load combinations are evaluated, not only
  additive maxima

#### Scenario: No silent subset

- **WHEN** a run evaluates only 3 of 7 declared combinations
- **THEN** affected checks show "not evaluated" for the remainder and cannot render an
  unqualified pass

### Requirement: Declared callouts reach the checks that depend on them

A check whose method depends on a characteristic a declared callout provides SHALL
consume the declared value and SHALL state the value used and its effect on the result.
When a declared callout contradicts an assumption a check would otherwise make,
the contradiction SHALL be reported rather than silently resolved. A check whose method
depends on such a characteristic that is undeclared SHALL state the assumption it used,
per the existing stated-assumptions requirement.

#### Scenario: Finish drives the fatigue factor

- **WHEN** a fatigue check runs on a feature carrying a surface-finish callout
- **THEN** the check uses the surface factor derived from the declared finish, cites the
  derivation, and states both the finish consumed and the factor applied

#### Scenario: Plating thickness reaches the fit

- **WHEN** an interference-fit check runs on a shaft carrying a plating callout with a
  thickness range
- **THEN** the check evaluates over the plated dimensions across the declared range and
  reports the range used

#### Scenario: Heat-treat condition governs properties

- **WHEN** a heat-treatment callout declares a condition and the material database
  distinguishes properties by condition
- **THEN** the check resolves properties for the declared condition and names it; if the
  declared condition has no record, the check reports "not evaluated" naming it

#### Scenario: Contradiction surfaced

- **WHEN** a declared callout is inconsistent with a check's method assumption
- **THEN** the scorecard reports the conflict naming the callout, its characteristic
  identifier, and the assumption — never a result computed by quietly preferring one

### Requirement: Repair hints on failed checks

A failed check record MAY carry typed repair hints — the governing input parameter, the direction of change that improves the margin, and, where a paired design inverse exists, the corrective value that would satisfy the check — computed deterministically, never by an LLM; hints SHALL name spec parameters by their stable names.

#### Scenario: Inverse supplies the corrective value

- **WHEN** a bending check fails and a design inverse exists for the section dimension
- **THEN** the check record includes the parameter name, the direction, and the computed dimension that would pass at the required margin

#### Scenario: No inverse, still a direction

- **WHEN** a check with no paired inverse fails but is monotonic in a known parameter
- **THEN** the record names the parameter and direction, and omits the corrective value rather than estimating one

### Requirement: Two-sided acceptance bands

Acceptance criteria SHALL support an optional upper margin bound in addition to the required minimum; a check whose margin exceeds the declared upper bound SHALL report a distinct over-margin warning (never a failure) with the excess quantified, so over-engineered candidates are visible without blocking export.

#### Scenario: Over-engineering surfaced

- **WHEN** a spec declares a target safety-factor band of 2.0–3.0 and a check computes SF 8.7
- **THEN** the check passes with an over-margin warning stating the band and the excess

#### Scenario: No band declared, no noise

- **WHEN** a spec declares only a minimum safety factor
- **THEN** high margins produce no warning — the band is strictly opt-in

### Requirement: Governing check identification

Every scorecard SHALL identify the governing check — the smallest-margin check among those evaluated — and revalidation after a spec change SHALL report when the governing check has changed, naming the previous and new governing checks.

#### Scenario: Governing check named

- **WHEN** a scorecard with multiple passing checks is rendered
- **THEN** the governing check and its margin are identified in the scorecard and report

#### Scenario: Governing change on revision

- **WHEN** a revision thickens a flange and the governing check moves from bending to bolt bearing
- **THEN** the revalidation output states the governing-check change explicitly

