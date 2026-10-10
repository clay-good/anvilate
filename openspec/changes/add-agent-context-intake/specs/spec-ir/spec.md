# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: A value can cite the file it came from

A value in a Design Spec SHALL be able to record, beside its origin, a source reference:
the file's name and SHA-256, a locator within it (page and region, entity handle, face or
feature, sheet and cell), how it was obtained (measured by Anvilate, or read by an agent),
and its confirmation state (unconfirmed, or confirmed by a named person on a date). Two
origins SHALL be added for this: measured from a file, and agent-read. A source reference
SHALL survive round-trips, diffs and the evidence bundle, and a spec whose cited file no
longer matches its recorded digest SHALL say so when checked.

#### Scenario: Where did this 80 mm come from?

- **WHEN** a reviewer reads a spec's plate width
- **THEN** they see the file it was read from, where in that file, who read it and whether
  a person confirmed it

#### Scenario: The cited file changed

- **WHEN** a spec cites a DXF whose contents have since changed
- **THEN** checking the spec reports that the cited source no longer matches

### Requirement: An unconfirmed reading is used, and marked

A spec containing unconfirmed agent-read values SHALL still validate, draw and screen, so
an agent can show a first result quickly. Every check that depends on such a value SHALL
say so, the scorecard SHALL count the unconfirmed values, and export SHALL treat the card
as it treats one resting on unverified results: watermarked, never validated. Confirming a
value SHALL be an explicit act naming the person, MUST NOT be performable by the agent on
its own authority, and SHALL be recorded in the spec.

#### Scenario: A quick look is allowed

- **WHEN** a spec built from a sketch carries three unconfirmed dimensions
- **THEN** the part is drawn and screened, and the result states that it rests on three
  unconfirmed readings

#### Scenario: A draft cannot ship as validated

- **WHEN** that part is exported before the values are confirmed
- **THEN** the export is watermarked unvalidated and names the unconfirmed values

#### Scenario: Confirmation is a person's act

- **WHEN** an agent attempts to mark its own reading confirmed without a named person
- **THEN** the spec is refused
