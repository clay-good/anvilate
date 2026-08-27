# design-space-exploration Specification

## Purpose
Sweeping the closed-form checks over a parameter space and returning the exact non-dominated set — a sweep, not an optimiser. Because every point is evaluated by the same cited checks, feasibility is a verdict rather than a penalty term, and a design that did not pass is never on the front. The sampling is deterministic and recorded, a truncated budget says so, and nothing in the output is surrogate-modelled or called optimal.

## Requirements
### Requirement: Typed study declaration

A trade study SHALL be declared as typed data: the parameters to vary with their bounds
and units, the objectives to minimize or maximize, the constraints that define
feasibility, and the sampling strategy with its budget. A study SHALL be storable,
diffable, and re-runnable as an ordinary spec artifact; a parameter whose bounds carry
units inconsistent with the underlying field SHALL be rejected per the units capability.

#### Scenario: Study round-trips

- **WHEN** a study over wall thickness and rib count minimizing mass subject to a
  utilization limit is declared and saved
- **THEN** it reloads identically and re-runs to the same result

#### Scenario: Objective must be computable

- **WHEN** a study names an objective no registered check or property produces
- **THEN** the study is rejected naming the objective — objectives are never improvised

### Requirement: Deterministic sampling with the sweep recorded

Sampling SHALL be seeded and reproducible: identical study, seed, and toolchain versions
SHALL produce an identical set of evaluated points in an identical order. The evaluated
points, their objective and constraint values, and their feasibility SHALL be recorded in
full and available in the evidence bundle, so a reviewer can audit the space rather than
only the winner.

#### Scenario: Reproducible sweep

- **WHEN** the same study reruns with the same seed and versions
- **THEN** every evaluated point and value is identical

#### Scenario: The whole space is auditable

- **WHEN** a study completes
- **THEN** the full evaluated set, not only the front, is retrievable and exportable

### Requirement: Exact Pareto extraction with governing constraints named

The system SHALL extract the non-dominated set exactly from the evaluated feasible
points, and SHALL report for each point on the front which constraint is governing and
its margin. Infeasible points SHALL be retained and marked with the constraint they
violate, never silently dropped.

#### Scenario: Front with governing constraints

- **WHEN** a mass-versus-cost study completes
- **THEN** the non-dominated set is reported, each point naming its governing constraint
  and margin

#### Scenario: Infeasible points are visible

- **WHEN** points violate a constraint
- **THEN** they are reported as infeasible with the violated constraint named, so the
  user can see where the feasible region ends

### Requirement: Every number comes from the deterministic engine

Objective and constraint values SHALL be produced only by deterministic evaluation of
registered checks and properties. A language model MAY propose parameters, bounds,
objectives, and sampling strategies, and MAY interpret or narrate a completed front, but
MUST NOT supply, estimate, adjust, or interpolate any objective, constraint, or margin
value; any narration SHALL be traceable to recorded evaluated points.

#### Scenario: Model proposes, engine disposes

- **WHEN** the agent suggests a study and narrates the resulting front
- **THEN** every quantity in the narration matches a recorded evaluated point, and no
  value originates in the model

#### Scenario: Interpolated claim refused

- **WHEN** a narration would state a value between evaluated points
- **THEN** it is refused or the point is evaluated for real — the front is never
  smoothed into claims the engine did not compute

### Requirement: Budgets and truncation are honest

A study SHALL enforce its declared evaluation budget and time limit, and a study that
terminates before exhausting its declared sampling plan SHALL report the coverage
achieved and that the front is provisional. A truncated study MUST NOT present its front
as complete.

#### Scenario: Truncated study says so

- **WHEN** a study hits its budget with a third of its plan unevaluated
- **THEN** the result states the coverage achieved and labels the front provisional

#### Scenario: Screening framing preserved

- **WHEN** a front is rendered in a report
- **THEN** it carries the screening label of the underlying checks — a Pareto front of
  screening results is not a certified optimum

