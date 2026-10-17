# Quality Artifacts Specification

## Purpose

The design-side quality records automotive, aerospace, medical and machinery engineers
must produce, filled from evidence Anvilate already computed, in open structures that
never reproduce a licensed table.

## ADDED Requirements

### Requirement: Design FMEA rows come from the design's own evidence

The system SHALL generate design FMEA rows per item and function: the failure modes the
failure-mode catalog lists for it, their effects and causes, the card checks that act as
prevention controls, and the verification items that act as detection controls. Each row
SHALL link to the check and verification entries it names.

#### Scenario: A bracket's FMEA

- **WHEN** an FMEA is generated for a bolted motor bracket
- **THEN** it has rows for fatigue cracking at the bend, joint loosening and bearing
  yield, each with its prevention check and detection test linked

### Requirement: Ratings use published open scales or the user's tables

Severity SHALL be supplied by the user and SHALL NOT be inferred. Occurrence and detection
SHALL be rated on Anvilate's own published scales, derived from margin and verification
strength. A user SHALL be able to load their organization's rating tables and
action-priority matrix, and the system SHALL NOT ship any licensed table.

#### Scenario: No severity, no priority

- **WHEN** an FMEA row has no user-supplied severity
- **THEN** its priority is not evaluated, naming severity as the missing input

#### Scenario: The user's own matrix

- **WHEN** a user loads their company's action-priority matrix with its source
- **THEN** priorities are computed with it, and the export names that source

### Requirement: Special characteristics flow everywhere they matter

Any toleranced dimension, geometric tolerance or material property SHALL be markable as
critical or significant, with a user-chosen symbol and a reason. A marked characteristic
SHALL carry its mark onto drawings, QIF characteristics, the inspection plan and the
control-plan seed. An unmarked characteristic SHALL NOT be shown as special.

#### Scenario: A safety-critical bore

- **WHEN** a brake caliper bore is marked critical with the customer's symbol
- **THEN** the drawing shows the symbol beside its callout, and the QIF export and
  control-plan seed carry the bore as critical

### Requirement: A control-plan seed hands design intent to manufacturing

For every special characteristic, the system SHALL write a control-plan seed row: the
characteristic, its specification and tolerance, the governing check, a suggested
measurement method, and empty process columns for manufacturing to fill. Rows SHALL be
written as CSV and XLSX.

#### Scenario: Process columns left to the plant

- **WHEN** a control-plan seed is exported
- **THEN** the process step, machine and reaction-plan columns are present and empty

### Requirement: Risk records follow the open hazard structure

A product SHALL be able to declare risk records in the structure shared by ISO 14971 and
ISO 12100. Each record holds a hazard, a hazardous situation, a harm, a user-supplied
severity and probability, its risk controls, and the verification of each control. A
control that is an Anvilate check SHALL link to its entry and inherit its verdict.

#### Scenario: A pinch point guarded

- **WHEN** a machine's pinch-point hazard is controlled by a guard whose clearance is an
  Anvilate check
- **THEN** the risk record shows the guard's clearance verdict as the control's
  verification

#### Scenario: A control whose check fails

- **WHEN** the guard clearance check fails
- **THEN** the risk record shows the control as not verified, naming the failing entry

### Requirement: Traceability exports to requirements tools

The system SHALL export the trace from each requirement to the items, checks,
verification items and evidence that address it, as CSV and as ReqIF. A requirement
with no check or verification SHALL appear marked uncovered. A check tracing to no
requirement SHALL be listed as untraced.

#### Scenario: An uncovered requirement

- **WHEN** a requirement for a 10-year life has no fatigue check and no test traced to it
- **THEN** the trace export marks it uncovered, and the ReqIF file carries that status
