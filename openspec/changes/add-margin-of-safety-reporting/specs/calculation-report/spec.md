# Calculation Report Specification (delta)

## ADDED Requirements

### Requirement: Governing margins carry their free body

For each governing margin row, the calculation report SHALL be able to render the free
body that produced it: the item outline, the applied loads, the reactions at each
connection, and the equilibrium residual. A free body whose residual exceeds a stated
tolerance SHALL be reported as a finding on that row.

#### Scenario: A reviewer checks equilibrium first

- **WHEN** a reviewer opens the report at a fitting's governing row
- **THEN** the free body shows the applied load, the bolt reactions and a residual
  within tolerance
