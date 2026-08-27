# Artifact Export Specification (delta)

## ADDED Requirements

### Requirement: QIF results export

The export layer SHALL export a validated part's scorecard and evidence as a QIF Results document (ISO 23952): each check maps to a characteristic with its requirement (threshold and units), evaluated actual, pass/fail status, and traceability to the spec revision and toolchain versions; the export SHALL validate against the QIF schemas, and checks that were not evaluated SHALL be represented as unevaluated characteristics, never omitted.

#### Scenario: Quality software reads the verdicts

- **WHEN** a validated part's evidence is exported as QIF Results
- **THEN** standard QIF-conformant quality software can enumerate every check as a characteristic with its requirement, actual, and status, and the document validates against the published schemas

#### Scenario: Not-evaluated survives the mapping

- **WHEN** a scorecard containing not-evaluated checks is exported
- **THEN** those checks appear as unevaluated characteristics with their reason, preserving the no-silent-green property in the interchange format
