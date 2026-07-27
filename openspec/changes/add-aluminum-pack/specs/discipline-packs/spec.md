# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Aluminum structural pack

The system SHALL provide, when shipped, an optional aluminum structural design pack with
ADM 2020 member screens — tensile yielding and rupture, local buckling resolved by
width-to-thickness slenderness class, member buckling, lateral-torsional buckling, and
combined loading interaction — each citing its ADM clause. Buckling constants SHALL be
computed from the ADM's cited formulas as functions of the alloy-temper properties, never
looked up from bundled reproductions of the standard's tables. Weld-affected-zone
reductions SHALL be first-class: when any part of a checked member is declared
weld-affected, the check SHALL evaluate with the reduced properties, state both the
parent and weld-affected values used, and identify which governed; a member with declared
welds whose weld-affected properties are not supplied SHALL report "not evaluated" naming
the missing values. Alloy-temper mechanical properties follow the user-supplied
allowables doctrine with provenance recorded.

#### Scenario: Governing limit state named

- **WHEN** a 6061-T6 rectangular-tube beam is screened under bending
- **THEN** yielding, local buckling, and lateral-torsional buckling are each evaluated
  with clauses cited, and the scorecard names the governing limit state and its margin

#### Scenario: Welded member uses reduced properties

- **WHEN** a member is declared welded within the checked region and weld-affected
  properties are supplied
- **THEN** the check evaluates with the weld-affected values, reports both property sets,
  and flags that the weld-affected zone governed if it did

#### Scenario: Missing weld-affected data is honest

- **WHEN** a member is declared welded but only parent-metal properties are supplied
- **THEN** affected checks report "not evaluated" naming the weld-affected properties
  required — never a check computed silently on parent-metal strength

#### Scenario: Buckling constants are computed, not recalled

- **WHEN** any buckling check runs
- **THEN** its buckling constants derive from the cited ADM formulas evaluated on the
  supplied properties, and the formula citation appears in the check provenance
