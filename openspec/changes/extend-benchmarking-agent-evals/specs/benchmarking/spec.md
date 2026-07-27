# Benchmarking & Quality Assurance Specification (delta)

## MODIFIED Requirements

### Requirement: External benchmark evaluation

Each release SHALL additionally be evaluated against at least one license-clean public text-to-CAD benchmark (e.g., CADGenBench-class or Text2CAD-Bench-class suites) and, where the benchmark provides structured design specifications and staged scoring (MUSE-class: execution, geometric validity, design-intent/engineering-criteria stages), Anvilate SHALL report the per-stage funnel results; scores and benchmark versions SHALL be published alongside AnvilateBench results so progress is comparable to the wider field, and out-of-scope tasks (part classes Anvilate does not claim) SHALL be reported as out-of-scope rather than silently averaged in.

#### Scenario: Public comparability

- **WHEN** a release is published
- **THEN** its external-benchmark scores and the benchmark versions used are recorded in the release notes

#### Scenario: Funnel reported per stage

- **WHEN** a structured-spec benchmark with staged scoring is evaluated
- **THEN** the published results show each stage's pass rate separately, with out-of-scope tasks counted and disclosed, never folded into an averaged headline number

## ADDED Requirements

### Requirement: Agent-driving evaluation

AnvilateBench SHALL include an agent-driving suite that scores model-plus-client combinations operating Anvilate's exposed tool surface end to end (compile, build, validate, read scorecard, repair within budget), reporting task completion, iteration count, and tool-call error rates per combination; results SHALL feed the published local-model recommendation, and the report MUST document harness sensitivity (client, prompt scaffold, and settings used) so scores are not misread as model-only properties.

#### Scenario: Local model recommendation is evidence-based

- **WHEN** the monthly model evaluation runs the agent-driving suite
- **THEN** the published recommendation shows, per model, the completion rate and iteration cost on the suite with the exact client and scaffold documented

#### Scenario: Harness sensitivity disclosed

- **WHEN** agent-driving results are published
- **THEN** the report names the client version, scaffold, and settings, and states that scores apply to that harness configuration
