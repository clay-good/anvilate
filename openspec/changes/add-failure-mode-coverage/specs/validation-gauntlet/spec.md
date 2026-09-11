# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: A card with unaddressed applicable modes is not a complete answer

Every scorecard SHALL carry or reference its failure-mode coverage report, and a card with
unaddressed applicable modes SHALL state that fact beside its verdict rather than
presenting the verdict alone. A passing card MUST NOT be rendered in a form that reads as
"nothing is wrong" while modes applicable to the declared design were never addressed —
the reader's real question is what the analysis did not look at.

#### Scenario: A clean verdict carries its blind spots

- **WHEN** a part passes every check with four unaddressed applicable modes
- **THEN** the card states the verdict and the four unaddressed modes together, and is not
  rendered as an unqualified pass

#### Scenario: Export gating reads the coverage

- **WHEN** a part is exported as validated
- **THEN** the evidence bundle carries the coverage report, so a downstream reader sees
  the same blind spots the engineer saw
