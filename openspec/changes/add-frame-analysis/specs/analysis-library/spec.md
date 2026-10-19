# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Internally solved member forces follow the ingestion contract

A member-force record produced by Anvilate's own frame solve SHALL carry the same
declared axis convention, sign convention, unit system and component list the external
ingestion contract requires, with the solve named as its source, so a member check
cannot distinguish a solved record from an imported one except by provenance, and every
rendered verdict states whether its demand was solved by Anvilate, imported from a named
external analysis, or declared.

#### Scenario: Solved and imported read the same

- **WHEN** a beam check runs once on a solved record and once on an imported record with
  the same forces
- **THEN** both verdicts are identical, and each report line names its demand source

#### Scenario: A solved record cannot drop a component

- **WHEN** the frame solve produces torsion on a member
- **THEN** the record carries it under the contract's name and the member check consumes
  or lists it by name, exactly as an imported record must
