# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: A check that consumes another check declares it

A check SHALL declare every upstream check output it consumes, naming the upstream check
and the specific output, so that the dependency is inspectable data rather than an
implementation detail. The declared output's dimension SHALL agree with the consuming
parameter's dimension, checked when the declaration is registered rather than when the
chain first runs. CI SHALL fail a check that reads another check's result without
declaring it, detected structurally over the source rather than by naming convention.

#### Scenario: The dependency is readable without reading the body

- **WHEN** a shock screen consumes a fundamental frequency computed by a modal screen
- **THEN** the consumption is declared with the upstream check id and output name, and is
  retrievable without inspecting the implementation

#### Scenario: Dimension mismatch caught at registration

- **WHEN** a check declares consumption of an upstream output whose dimension does not
  match the consuming parameter
- **THEN** registration fails naming both dimensions, rather than failing at run time on
  the first spec that exercises the chain

#### Scenario: Undeclared consumption fails CI

- **WHEN** a check reads an upstream result without declaring the consumption
- **THEN** CI fails naming the check and the upstream result it read
