# Artifact Export Specification (delta)

## ADDED Requirements

### Requirement: Keepouts export as labeled non-manufacturing geometry

Exported artifacts SHALL carry declared keepout envelopes as separate, clearly labeled
non-manufacturing entities — a dedicated layer in DXF, a distinct named body or product in
STEP — never merged into the manufactured solid and never silently dropped. Each exported
keepout SHALL carry its tag and its stated reason where the format permits, and the
evidence bundle SHALL record every keepout with its reason and its intrusion verdict.

#### Scenario: Downstream reader sees the constraint

- **WHEN** a validated part with two keepouts is exported to STEP and opened in a
  mainstream CAD system
- **THEN** the keepouts appear as separately named non-manufacturing bodies alongside the
  part, identifiable by tag

#### Scenario: A keepout is never machinable

- **WHEN** an exported artifact is consumed as manufacturing geometry
- **THEN** the manufactured solid contains no keepout material, and the keepout entities
  are on a layer or product marked non-manufacturing

#### Scenario: Dropping a keepout is not silent

- **WHEN** an export format cannot represent a declared keepout
- **THEN** the export states which keepouts were omitted and why, and the omission is
  recorded in the evidence bundle
