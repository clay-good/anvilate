# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: Repair hints on failed checks

A failed check record MAY carry typed repair hints — the governing input parameter, the direction of change that improves the margin, and, where a paired design inverse exists, the corrective value that would satisfy the check — computed deterministically, never by an LLM; hints SHALL name spec parameters by their stable names.

#### Scenario: Inverse supplies the corrective value

- **WHEN** a bending check fails and a design inverse exists for the section dimension
- **THEN** the check record includes the parameter name, the direction, and the computed dimension that would pass at the required margin

#### Scenario: No inverse, still a direction

- **WHEN** a check with no paired inverse fails but is monotonic in a known parameter
- **THEN** the record names the parameter and direction, and omits the corrective value rather than estimating one

### Requirement: Two-sided acceptance bands

Acceptance criteria SHALL support an optional upper margin bound in addition to the required minimum; a check whose margin exceeds the declared upper bound SHALL report a distinct over-margin warning (never a failure) with the excess quantified, so over-engineered candidates are visible without blocking export.

#### Scenario: Over-engineering surfaced

- **WHEN** a spec declares a target safety-factor band of 2.0–3.0 and a check computes SF 8.7
- **THEN** the check passes with an over-margin warning stating the band and the excess

#### Scenario: No band declared, no noise

- **WHEN** a spec declares only a minimum safety factor
- **THEN** high margins produce no warning — the band is strictly opt-in

### Requirement: Governing check identification

Every scorecard SHALL identify the governing check — the smallest-margin check among those evaluated — and revalidation after a spec change SHALL report when the governing check has changed, naming the previous and new governing checks.

#### Scenario: Governing check named

- **WHEN** a scorecard with multiple passing checks is rendered
- **THEN** the governing check and its margin are identified in the scorecard and report

#### Scenario: Governing change on revision

- **WHEN** a revision thickens a flange and the governing check moves from bending to bolt bearing
- **THEN** the revalidation output states the governing-check change explicitly
