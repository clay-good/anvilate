# Drawing Generation Specification (delta)

## ADDED Requirements

### Requirement: Every characteristic is numbered, and the numbers persist

Every dimension, tolerance, geometric tolerance and note on a part drawing SHALL carry a
characteristic number. The same characteristic SHALL keep its number across revisions,
and a new one SHALL get the next unused number. The system SHALL write a characteristic
accountability table: number, characteristic, nominal, tolerance, special mark, and an
empty measured-result column, shaped for first-article inspection.

#### Scenario: A revision adds a hole

- **WHEN** revision B of a plate adds a hole to the drawing
- **THEN** every characteristic from revision A keeps its number, and the new hole's
  characteristics take the next unused numbers
