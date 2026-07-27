# Verification Planning Specification (delta)

## ADDED Requirements

### Requirement: Checks map to test archetypes deterministically

The system SHALL maintain a registry mapping check classes to physical verification
archetypes — at minimum proof load, functional demonstration, dimensional inspection,
nondestructive examination, preload or torque verification, and material certification
review — and SHALL emit a verification plan from a scorecard by deterministic lookup. The
mapping MUST NOT be produced by a language model. A registry entry SHALL cite the source
prescribing the test where one exists, and SHALL be marked as a practice-based default
where none does.

#### Scenario: Proof test emitted for a lifter

- **WHEN** a lifting device's strength checks pass and a plan is generated
- **THEN** the plan contains a proof-load test naming the driving checks, the load
  derived from the rated load and the governing clause, and the citation prescribing it

#### Scenario: Practice-based defaults are labeled

- **WHEN** an archetype has no prescribing standard for that check class
- **THEN** the emitted item is labeled a practice-based default, distinguishable from a
  standard-prescribed test

### Requirement: Test items carry criteria derived from the check

Every emitted test item SHALL identify the check or checks that drive it, the test
method with citation, the acceptance criteria derived from the check's own allowable and
units, and the measurement accuracy required for the test to be able to discriminate a
pass from a failure at that margin. Where the required accuracy cannot be derived, the
item SHALL say so rather than omitting the field.

#### Scenario: Criteria trace to the calculation

- **WHEN** a bolted-joint preload check emits a torque-verification item
- **THEN** the item states the target preload, the tolerance band traced to the check's
  allowable, and the driving check identifier

#### Scenario: Accuracy makes the test meaningful

- **WHEN** a check passes with a 4% margin
- **THEN** the emitted item states the measurement accuracy needed to resolve that
  margin, or states plainly that it could not be derived

### Requirement: Verification matrix with honest coverage

The evidence bundle SHALL be able to include a verification matrix listing every check,
its verification method, and the emitted test item where one exists; checks that map to
no physical test SHALL be listed as verified by analysis only, and the matrix SHALL
report that count explicitly. A plan MUST NOT imply full physical coverage it does not
have.

#### Scenario: Analysis-only checks are counted

- **WHEN** a matrix is generated for a part where most checks have no physical
  counterpart
- **THEN** those checks appear as analysis-only and the matrix states how many are so
  covered

#### Scenario: Not-evaluated checks propagate

- **WHEN** a check reports "not evaluated"
- **THEN** the matrix shows no verification derived from it and names it as unresolved —
  a missing check never yields a confident test plan

### Requirement: A plan is not evidence until results are recorded

Emitted test items SHALL be planned items with no result. A user SHALL be able to record
an outcome — result value, date, performer, and instrument identity — against an item,
and only recorded outcomes SHALL count as verification evidence. A plan with no recorded
outcomes MUST NOT render as verified, and recorded outcomes MUST NOT alter any
analytical verdict.

#### Scenario: Empty plan is not a pass

- **WHEN** a bundle contains a verification plan with no recorded outcomes
- **THEN** the verification status renders as planned, never as verified

#### Scenario: Recorded outcome is attributed

- **WHEN** a proof-test result is recorded
- **THEN** the bundle carries the value, date, performer, and instrument identity, and
  the analytical scorecard entries are unchanged
