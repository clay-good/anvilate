# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Everyday parts are elements a document can declare

The packs SHALL provide element types for the everyday parts the drawable catalog adds:
angle bracket, mounting plate, plate flange, spacer, bushing, standoff, shaft collar,
stepped shaft, pulley, clevis, tube, extrusion profile, sheet-metal bracket and enclosure.
Each element SHALL be a typed model with unit-checked fields published as an element
schema. Where a closed-form check with a citable source applies (bracket leg bending, bolt
bearing and edge distance, flange bolt load, clevis pin shear and bearing, shaft stress at
a shoulder with a stress concentration factor), the element SHALL ship with that screen;
where none is shipped, the element SHALL declare so and be reported not evaluated.

#### Scenario: An angle bracket is checked and drawn

- **WHEN** a spec declares an angle bracket with its load and a required safety factor
- **THEN** the card reports leg bending and bolt-hole bearing with their sources, and the
  bracket builds as a solid

#### Scenario: No screen is stated, not implied

- **WHEN** an element ships with no screen
- **THEN** its manifest says so, and a document declaring it is told the part will be
  drawn and not checked
