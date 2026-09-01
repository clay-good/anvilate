# Spec IR

## ADDED Requirements

### Requirement: Element declaration

A Design Spec SHALL declare the engineering element it describes, in a form that selects one
discipline-pack screen without inference from the part's name; a spec that declares no
element SHALL be screened through the tiers that need none, and its analytical tier reported
as not evaluated with that reason, never as a pass.

#### Scenario: A declared element is screened

- **WHEN** a spec declaring an element is screened
- **THEN** the analytical tier runs the pack screen that element selects, and the scorecard
  carries its cited verdicts

#### Scenario: An undeclared element is a named gap

- **WHEN** a spec that declares no element is screened and demands the analytical tier
- **THEN** the scorecard carries one not-evaluated entry naming the missing declaration, and
  the card does not pass

#### Scenario: An unknown element is refused rather than guessed

- **WHEN** a spec declares an element no pack resolves
- **THEN** the analytical tier reports not evaluated naming the element, and no screen is
  selected by near-miss matching
