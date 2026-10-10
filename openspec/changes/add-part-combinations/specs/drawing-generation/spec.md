# Drawing Generation Specification (delta)

## ADDED Requirements

### Requirement: A combination is drawn so each part can be told apart

A combination SHALL render in the same views and formats as a single part, with each part
in a distinguishable tone that survives greyscale printing, numbered with a balloon, and
with a parts list beside or beneath the view matching the bill of materials. An optional
exploded view SHALL separate parts along their mating axes by a stated factor. Envelope
hardware SHALL be drawn in a lighter line weight than designed parts, and a failing mate
SHALL be marked at the features involved.

#### Scenario: The picture answers "what is in it?"

- **WHEN** a bolted bracket combination is rendered
- **THEN** the bracket, plate and hardware are each numbered and listed, and the numbers
  match the bill of materials

#### Scenario: A mismatch is visible

- **WHEN** a hole-pattern mate fails
- **THEN** the rendered view marks the two patterns that disagree
