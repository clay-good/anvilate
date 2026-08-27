# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Member-force ingestion from external analysis

The library SHALL accept typed member-force records — axial force, shears, moments, and torsion at member stations, with units — produced by external structural-analysis tools (Pynite-class), and feed them to the existing cited member checks; results SHALL carry provenance identifying the external tool, its version, and the load case or combination the forces came from.

#### Scenario: Pynite forces through AISC checks

- **WHEN** a user supplies member end forces computed by an external frame analysis for a declared section and length
- **THEN** the existing beam, column, and beam-column screens run with those demands and each scorecard entry cites its clause and records the external-analysis provenance

#### Scenario: Verdict states its demand source

- **WHEN** a check consuming external forces is rendered in a report
- **THEN** the report states that demands came from the named external analysis, not from Anvilate's own load derivation

### Requirement: Section-property ingestion

The library SHALL accept externally computed cross-section constants (area, second moments, torsion constant, section moduli, warping constant where relevant) as typed CrossSection inputs with source provenance, including an optional-dependency adapter for sectionproperties-class engines; ingested constants SHALL be dimensionally validated before use.

#### Scenario: Arbitrary section screened

- **WHEN** a user computes constants for a custom welded section with an external section engine and supplies them
- **THEN** beam and torsion checks accept the section with the engine and version recorded as the property source

#### Scenario: Adapter is optional

- **WHEN** the optional section-engine dependency is absent
- **THEN** manual typed entry of constants works identically, and nothing else in the library degrades

### Requirement: No silent conventions on imported analysis data

Ingestion of external forces and section properties SHALL require explicit declaration of the source's axis convention and unit system; the mapping to Anvilate's conventions SHALL be validated, and a record whose convention is undeclared or inconsistent MUST be rejected rather than assumed.

#### Scenario: Undeclared axes rejected

- **WHEN** a member-force record arrives without an axis-convention declaration
- **THEN** ingestion fails naming the missing declaration, and no check runs on assumed axes

#### Scenario: Strong/weak axis mix-up caught

- **WHEN** a declared convention maps the section's transverse moment to the bending axis inconsistently with the record's own labels
- **THEN** ingestion fails with the conflict described, rather than screening about the wrong axis
