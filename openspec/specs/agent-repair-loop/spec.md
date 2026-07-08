# Agent Repair Loop Specification

## Purpose

The agent loop reads the validation scorecard and drives the part toward a fully passing state: a deterministic Planner handles most repairs through bounded parameter search; an LLM Critic is invoked only for non-trivial failures and only emits structured edits. The loop converges, or it honestly surfaces the trade-off to the user. It is the second and last subsystem permitted to call an LLM.

## Requirements

### Requirement: Deterministic planner first

Scorecard failures SHALL first be mapped by a deterministic planner to a repair strategy ordered by cost — parameter nudge, pattern feature addition (rib, gusset), pattern swap, then give-up-and-surface; when a failure is monotonic in a single parameter, the planner MUST repair it with bounded numeric search (bisection/golden-section) without any LLM call.

#### Scenario: Thickness nudge without LLM

- **WHEN** the only failure is a safety-factor shortfall monotonic in flange thickness
- **THEN** the planner converges the thickness by bounded search within the pattern's parameter bounds
- **AND** no LLM call occurs during the repair

#### Scenario: Cost-ordered escalation

- **WHEN** parameter nudges within bounds cannot clear a failure
- **THEN** the planner escalates to feature addition, then pattern swap, in that order

### Requirement: Critic emits only structured edits

The LLM Critic SHALL be invoked only for failures the planner cannot resolve, SHALL receive the scorecard with failure locations expressed as semantic tags, and MUST respond only with schema-validated structured edits (parameter patches or pattern-library operations) — never raw freeform code inside the loop.

#### Scenario: Critic proposes a rib

- **WHEN** the planner exhausts single-parameter repairs on a stiffness failure located "at fillet between `rib_1` and `base_plate`"
- **THEN** the Critic returns a validated pattern operation (e.g., add-gusset with parameters) that the geometry engine applies deterministically

#### Scenario: Invalid edit rejected

- **WHEN** the Critic emits an edit that fails schema validation or exceeds pattern parameter bounds
- **THEN** the edit is rejected and retried within budget, and is never applied unvalidated

### Requirement: Iteration budgets and monotonic progress

The loop SHALL enforce configurable budgets — maximum iterations (default 8) and maximum wall-clock (default 10 minutes) — and a monotonic-progress rule: a candidate iteration is retained only if the worst constraint violation improves.

#### Scenario: Regressing candidate discarded

- **WHEN** an iteration reduces mass but worsens the governing stress violation
- **THEN** the candidate is discarded and the search continues from the previous best

#### Scenario: Budget exhaustion is graceful

- **WHEN** the iteration or time budget is exhausted without full convergence
- **THEN** the loop stops and presents the trade-off outcome rather than looping indefinitely

### Requirement: Honest non-convergence with Pareto alternatives

When constraints are jointly unsatisfiable within budget, the system SHALL say so plainly and present the closest Pareto-optimal alternatives with their violated constraint made explicit, letting the user pick or amend the spec.

#### Scenario: Impossible mass target

- **WHEN** a 150 g mass target cannot be met at safety factor 2.0
- **THEN** the user is shown options such as "178 g at SF 2.0" and "150 g at SF 1.4" with the relaxed constraint highlighted
- **AND** selecting one updates the spec explicitly rather than silently

### Requirement: Full iteration provenance

Every iteration SHALL be snapshotted — spec delta, code delta, scorecard — and the sequence SHALL be replayable through the UI timeline and inspectable in the evidence bundle.

#### Scenario: Timeline scrubbing

- **WHEN** the user scrubs from v3 back to v1
- **THEN** the viewport and report pane show iteration v1's exact geometry and scorecard, regenerated or restored deterministically
