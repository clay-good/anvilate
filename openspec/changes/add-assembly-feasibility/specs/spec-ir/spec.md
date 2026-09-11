# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: Typed assembly-state, access, and insertion declarations

A Design Spec SHALL be able to declare the ordered assembly states a build passes through,
each part's insertion direction and the features it occupies, and per-feature access
requirements naming the tool, the approach direction, and the required swing arc — all as
typed, schema-validated, diffable elements. An operation declared to occur in a state the
spec does not define SHALL be rejected naming the state, so that access can never be
evaluated against an assembly configuration nobody described.

#### Scenario: States and access round-trip

- **WHEN** a spec declaring three assembly states and two access requirements is
  serialized and reloaded
- **THEN** every state, insertion direction, tool, approach, and arc round-trips unchanged

#### Scenario: An operation in an undefined state is rejected

- **WHEN** an adjustment declares that it is performed in a state the spec does not define
- **THEN** the spec is rejected naming the state

#### Scenario: Changing the build order is visible in the diff

- **WHEN** a revision moves an operation from one assembly state to another
- **THEN** the spec diff shows the state change rather than only the changed geometry
