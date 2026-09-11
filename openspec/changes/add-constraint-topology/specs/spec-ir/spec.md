# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: Typed constraint declaration

A Design Spec SHALL be able to declare a body's constraints as typed, schema-validated
elements naming the tagged feature each constraint acts at, the degrees of freedom it
removes, its kind, its reference frame, and any declared intentional redundancy with its
justification. A constraint referencing a tag that does not exist SHALL be rejected naming
the tag, and constraint declarations SHALL be diffable so a change in how a part is
located is visible as such rather than buried in geometry parameters.

#### Scenario: Constraint declaration round-trips

- **WHEN** a spec declaring a three-point mount is serialized and reloaded
- **THEN** every constraint, its feature tag, frame, and removed freedoms round-trip
  unchanged

#### Scenario: A relocation shows up in the diff

- **WHEN** a design change moves location duty from a pair of dowels to a machined boss
- **THEN** the spec diff shows the constraint change, not only the changed hole geometry

#### Scenario: Dangling feature reference rejected

- **WHEN** a constraint names a semantic tag the part does not carry
- **THEN** the spec is rejected naming the tag
