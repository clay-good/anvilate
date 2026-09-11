# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: The card states what it did not look at

Every scorecard SHALL report, beside its verdict, the count of checks that were not
evaluated and the count that were out of the declared screening depth, and SHALL carry or
reference the consolidated needs report whenever either count is non-zero. A card MUST NOT
present a verdict in a form that reads as complete while either count is non-zero, because
the reader's question is not only what passed but what nobody looked at.

#### Scenario: Completeness is a stated quantity

- **WHEN** a card passes with three not-evaluated and eight out-of-depth entries
- **THEN** both counts appear beside the verdict, and the card is not rendered as a
  complete pass

#### Scenario: A fully screened card says so positively

- **WHEN** every applicable check evaluated within the declared depth
- **THEN** the card states that both counts are zero, so a complete result is
  distinguishable from one where nobody counted
