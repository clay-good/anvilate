# Units & Quantities Specification (delta)

## ADDED Requirements

### Requirement: Angle is a first-class dimensioned quantity

The unit layer SHALL treat plane angle as a first-class quantity with its own unit set —
radian, milliradian, microradian, degree, arcminute, arcsecond, and minute of angle — and
SHALL carry that unit through storage, computation, comparison, and rendering. An angular
value SHALL NOT be accepted bare, SHALL NOT be rendered bare, and SHALL NOT be silently
treated as dimensionless because radians are a ratio of lengths. Solid angle SHALL be
distinguished from plane angle, and a comparison between the two SHALL be rejected naming
both.

#### Scenario: Bare angular input is challenged

- **WHEN** a spec field expecting an angular limit receives a bare number
- **THEN** the compiler asks one question offering the plausible angular units rather than
  assuming radians

#### Scenario: Angular results render with their unit

- **WHEN** a line-of-sight result computed in radians is rendered for a reader whose
  declared angular unit is milliradians
- **THEN** the value is converted and shown with the unit, and no angular value anywhere
  on the surface appears without one

#### Scenario: A dimensionless value cannot become an angle

- **WHEN** a dimensionless ratio is supplied where an angle is expected
- **THEN** validation rejects it naming the field and the expected dimension, rather than
  accepting it as radians

#### Scenario: Plane and solid angle do not mix

- **WHEN** a steradian value is compared against a radian limit
- **THEN** the comparison is rejected naming both quantities

### Requirement: Small-angle conversions state that they are approximations

A result SHALL state that the small-angle approximation was used, and the angle at which
it was applied, wherever a screen converts between a linear displacement and an angle by
the small-angle relation, so that a reader can see when a result sits near the edge
of the approximation's validity.

#### Scenario: Approximation is disclosed

- **WHEN** a decenter is converted to an angular shift by the small-angle relation
- **THEN** the result states the approximation used and the resulting angle
