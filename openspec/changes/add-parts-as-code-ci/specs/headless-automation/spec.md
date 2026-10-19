# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: Findings are written as SARIF located on the spec's own lines

`anvilate check` and the repository sweep SHALL be able to write their findings as a
SARIF 2.1.0 log: one rule per check identifier carrying the check's citation as its help
text, and one result per failing or not-evaluated entry, located on the spec file and
the line and column of the field that governs the entry, with a partial fingerprint
stable across runs and machines for the same spec and check. Passing entries SHALL NOT be
results. A not-evaluated entry SHALL be a result at a level distinct from a failure, with
its reason as the message, never omitted.

#### Scenario: The annotation lands on the field

- **WHEN** a lifting lug's pin-bearing check fails and the SARIF log is uploaded to a code
  scanning service
- **THEN** the alert appears on the line of the spec declaring the hole diameter, titled
  with the check identifier, with the verdict line as its message and the clause in its
  help

#### Scenario: Not evaluated is visible, not green

- **WHEN** a spec's analytical tier is not evaluated for a missing declaration
- **THEN** the log carries a result at the note level on the line where the declaration
  belongs, naming what is missing

### Requirement: Check results are written in the report format CI dashboards read

`anvilate check` and the repository sweep SHALL be able to write a JUnit XML report with
one test case per check per spec, in which a failing check is a failure carrying the
verdict line, a not-evaluated check is a skipped case carrying its reason, and only a
passing check is a passing case. The report SHALL be byte-identical for the same card.

#### Scenario: A dashboard counts honestly

- **WHEN** forty specs are swept and three checks are not evaluated
- **THEN** the report shows three skipped cases with their reasons, and no dashboard reading
  it can count them as passed

### Requirement: A repository sweep compares against a committed baseline

The system SHALL provide a sweep that screens every spec and product under a folder and
compares each card's content-addressed digest and entries against a committed baseline,
reporting newly failing, newly passing, newly not-evaluated and changed-governing entries
per spec, with an exit code that distinguishes "changed for the worse" from "unchanged"
from "changed for the better", and a summary table suitable for a job summary or a review
comment. The baseline SHALL be updated only by an explicit command, and a baseline entry
whose spec no longer exists SHALL be reported rather than dropped.

#### Scenario: One newly failing check among known gaps

- **WHEN** a sweep finds the same twelve not-evaluated entries the baseline records and one
  check that passed in the baseline and now fails
- **THEN** the summary names that one check and its spec, the exit code says worse, and the
  twelve known entries are listed as unchanged

#### Scenario: The baseline does not move by itself

- **WHEN** a sweep runs in CI
- **THEN** the committed baseline file is unchanged, and the summary says how to update it
