# Design Space Exploration Specification (delta)

## ADDED Requirements

### Requirement: A study may search instead of sweep

A study SHALL be able to declare a search strategy in place of a sweep: a seeded
evolutionary search for mixed variables and one or more objectives, or a derivative-free
local refinement for continuous variables from a declared start. A search SHALL obey
every rule a sweep obeys: identical study, seed and toolchain versions SHALL produce an
identical sequence of evaluated points; every evaluated point SHALL be recorded with its
values and feasibility; and feasibility SHALL be decided by the scorecard, with a
not-evaluated check counting as infeasible. Candidates evaluated in parallel SHALL be
committed to the record in a deterministic order.

#### Scenario: A search reruns identically

- **WHEN** the same reducer study with seed 7 runs twice on the same versions, once on one
  worker and once on four
- **THEN** both runs record the same evaluated points in the same order and return the same
  result

#### Scenario: A point whose FEA did not converge

- **WHEN** a candidate's housing FEA does not converge
- **THEN** the candidate is recorded as infeasible naming the non-converged check, and it
  cannot be the result

### Requirement: Variables come from declared ranges or bundled tables

A study variable SHALL be continuous with bounds and units, integer with bounds, or a
choice from a bundled table or a list the document declares with its source. A choice
variable SHALL only take values its table holds, and the result SHALL cite the table entry
for each. A study SHALL be refused if a choice variable names a table that does not exist
or a value outside it.

#### Scenario: A module from the preferred series

- **WHEN** a gear stage's module is declared as a choice from the bundled preferred-module
  table
- **THEN** every evaluated candidate's module is a tabulated value, and the result cites the
  table row for the module it chose

#### Scenario: An invented stock size

- **WHEN** a study declares a plate thickness choice list containing 7.3 mm with no source
- **THEN** the study is refused naming the value and asking for its source

### Requirement: Evaluation runs cheapest tier first and is cached

Each candidate SHALL be screened tier by tier in cost order, and a candidate that fails a
cheaper tier SHALL NOT be sent to a more expensive one; the record SHALL state which tiers
ran for each point. Evaluations SHALL be cached by the content digest of the candidate's
resolved document and toolchain versions, and a cached evaluation SHALL be reported as
such. A study's budget SHALL be declared in evaluations, solver runs and wall-clock, and
exhausting any one SHALL end the search with the coverage achieved stated.

#### Scenario: FEA only where it can matter

- **WHEN** 400 reducer candidates are generated and 310 fail a gear or shaft check
- **THEN** at most 90 housing FEA runs are made, and the record shows the 310 as rejected at
  the analytical tier

#### Scenario: The solver budget ends the search

- **WHEN** a study with a budget of 40 solver runs reaches its fortieth run
- **THEN** the search stops, the result is labeled provisional, and the record states the
  runs, evaluations and time used against each budget

### Requirement: The result is the best found, with its neighborhood checked

A search result SHALL be the best feasible design found under the budget, never described
as optimal. It SHALL report its governing checks with their margins, the history of the
best objective value by evaluation, and a neighborhood check: each continuous variable
perturbed by a declared step in both directions and each choice variable moved to its
adjacent table entries, every neighbor evaluated for real. A feasible neighbor better than
the result SHALL be reported, and the result SHALL then be labeled not locally confirmed.

#### Scenario: A result that could still improve

- **WHEN** the neighborhood check finds a feasible neighbor 2% lighter
- **THEN** the result is labeled not locally confirmed and names that neighbor with its
  values

#### Scenario: The word optimal never appears

- **WHEN** a search result is rendered in a report or a tool result
- **THEN** it is called the best design found under the stated budget, with the screening
  label of the underlying checks

### Requirement: A study result is a proposed edit

A study result SHALL be returned as a diff against the study's base document. The base
document SHALL NOT change until the diff is applied as an ordinary spec edit, and an
applied diff SHALL be recorded in iteration provenance as study-derived, with the study's
identity, seed and record digest. Starting points SHALL include the base design and, where
its failed checks carry inverse repairs, the repaired design.

#### Scenario: Applying a result

- **WHEN** the agent applies a reducer study's result
- **THEN** the spec changes by exactly the diff, and its provenance names the study, seed
  and record digest

### Requirement: Search is verified against published benchmark problems

The search strategies SHALL be regression-tested against published constrained benchmark
problems with mixed variables, including the Golinski speed reducer, re-implemented from
the published definition. Each test SHALL hold the best feasible objective found within a
stated tolerance of the best-known published value and SHALL fail if any reported point
violates a constraint.

#### Scenario: The speed reducer

- **WHEN** the evolutionary search runs the speed-reducer problem with its fixed seed and
  budget
- **THEN** the best feasible weight is within the stated tolerance of the best-known value,
  and every reported point satisfies all eleven constraints

### Requirement: Topology results are seeds, not parts

A material-layout study's output SHALL be a seed: when it runs on a declared design space
with keep-in regions, loads and supports, its output SHALL be a density field, a rendered picture and a mesh labeled
as a seed. A seed SHALL NOT be buildable, screenable or exportable as a validated part,
and every surface that shows it SHALL say that the engineer must interpret it into a part
and screen that part.

#### Scenario: A seed cannot be exported as a part

- **WHEN** an agent asks to export a topology seed as STEP
- **THEN** the export is refused, naming the seed and saying that a part interpreted from it
  must be described and screened first
