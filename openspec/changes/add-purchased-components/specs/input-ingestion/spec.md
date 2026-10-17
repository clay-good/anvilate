# Input Ingestion Specification (delta)

## ADDED Requirements

### Requirement: A vendor model becomes a draft component record

Given a vendor STEP file in the context folder, the system SHALL produce a draft
component record: its measured envelope, candidate interfaces from its measured holes,
bosses and planar faces, and its unit, each marked as measured from the named file. The
draft SHALL hold no rating and no part number until the user or agent supplies them with
provenance, and SHALL NOT be usable in a product until every candidate interface it keeps
is confirmed.

#### Scenario: A motor model in the folder

- **WHEN** an agent reads `vendor/motor_57.step` from the context folder
- **THEN** it receives a draft record with the envelope and a candidate four-hole
  pattern and pilot, each marked measured and unconfirmed
