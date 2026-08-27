# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: Declared callouts reach the checks that depend on them

A check whose method depends on a characteristic a declared callout provides SHALL
consume the declared value and SHALL state the value used and its effect on the result.
When a declared callout contradicts an assumption a check would otherwise make,
the contradiction SHALL be reported rather than silently resolved. A check whose method
depends on such a characteristic that is undeclared SHALL state the assumption it used,
per the existing stated-assumptions requirement.

#### Scenario: Finish drives the fatigue factor

- **WHEN** a fatigue check runs on a feature carrying a surface-finish callout
- **THEN** the check uses the surface factor derived from the declared finish, cites the
  derivation, and states both the finish consumed and the factor applied

#### Scenario: Plating thickness reaches the fit

- **WHEN** an interference-fit check runs on a shaft carrying a plating callout with a
  thickness range
- **THEN** the check evaluates over the plated dimensions across the declared range and
  reports the range used

#### Scenario: Heat-treat condition governs properties

- **WHEN** a heat-treatment callout declares a condition and the material database
  distinguishes properties by condition
- **THEN** the check resolves properties for the declared condition and names it; if the
  declared condition has no record, the check reports "not evaluated" naming it

#### Scenario: Contradiction surfaced

- **WHEN** a declared callout is inconsistent with a check's method assumption
- **THEN** the scorecard reports the conflict naming the callout, its characteristic
  identifier, and the assumption — never a result computed by quietly preferring one
