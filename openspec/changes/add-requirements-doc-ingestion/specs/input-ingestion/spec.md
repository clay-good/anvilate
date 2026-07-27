# Input Ingestion Specification (delta)

## ADDED Requirements

### Requirement: Requirements-document ingestion with confirmation

The system SHALL extract candidate specification fields — loads, masses, environments, materials, interface references, constraints, and acceptance criteria — from requirement-class documents (requirement sheets, RFQs, design briefs) locally, assembling them into a draft Design Spec where every extracted value carries its source location and document provenance; each value SHALL require explicit per-value confirmation before becoming load-bearing, and the draft spec MUST be visibly distinguished from a confirmed spec in every surface that renders it.

#### Scenario: Requirement sheet to draft spec

- **WHEN** the user drops a PDF requirement sheet stating a payload mass, a vibration environment, a material family, and a mass budget
- **THEN** a draft spec is assembled with each extracted value linked to its page location, presented as a confirmation checklist, and nothing builds until the load-bearing values are confirmed

#### Scenario: Unconfirmed values cannot drive validation

- **WHEN** a draft spec with unconfirmed extracted loads is submitted to the pipeline
- **THEN** compilation refuses with the unconfirmed load-bearing values enumerated, rather than validating against draft numbers

#### Scenario: Conflicting statements surfaced

- **WHEN** the document states two inconsistent values for the same quantity (e.g., a load given differently in text and in a table)
- **THEN** both candidates are presented with their locations for the user to resolve, and neither is auto-selected
