# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: The scorecard carries its margin ledger

Every scorecard SHALL be accompanied by the margin ledger for the checks it contains, and
every check entry SHALL be able to name the ledger entries bearing on it. A check that
applied a factor with no corresponding ledger entry SHALL be a defect: the card SHALL
report the check as "not evaluated" naming the unledgered factor, on the same principle
that a check which did not run is never rendered as passed.

#### Scenario: Ledger travels with the verdict

- **WHEN** a scorecard is rendered or exported
- **THEN** the ledger is present, and each check's entries are reachable from that check

#### Scenario: An unledgered factor is a defect, not a detail

- **WHEN** a check applies a factor that produced no ledger entry
- **THEN** the check reports "not evaluated" naming the factor, and the card does not pass

#### Scenario: Over-margin is reportable without being a failure

- **WHEN** a check passes with a large cumulative factor
- **THEN** the card reports the cumulative factor alongside the pass, and the pass stands
  — conservatism is surfaced, never converted into a failure the engineer did not ask for
