# Validation Gauntlet

## MODIFIED Requirements

### Requirement: No silent green

Any check that could not run — mesh failure, missing material property, solver error — SHALL be reported as "not evaluated" with the reason; the system MUST never render a check as passed when it did not execute and complete.

A screen SHALL further answer every claim the document makes. A declaration that no demanded tier screens, and a bound that nothing in the system can screen at all, SHALL each be reported as "not evaluated" naming what was declared and what checking it would take — never omitted from the card, because a claim nobody looked at must not be indistinguishable from one that passed.

#### Scenario: Mesh failure is visible

- **WHEN** meshing fails on a thin feature
- **THEN** all T3 checks show "not evaluated — mesh failure at <tag>"
- **AND** the part cannot export as validated

#### Scenario: A declaration no demanded tier screens is named

- **WHEN** a spec declares an element, or a toleranced dimension, and its acceptance criteria do not demand the tier that would screen it
- **THEN** the scorecard carries a not-evaluated entry naming what was declared and the tier that would have screened it
- **AND** the card does not pass

#### Scenario: A bound nothing can screen is named with its reason

- **WHEN** a spec declares a bound the system cannot evaluate, such as a maximum mass, an envelope, a cost, a minimum wall thickness, or a displacement limit no screen reads
- **THEN** the scorecard carries a not-evaluated entry stating the declared value and what checking it would take
- **AND** the card does not pass

#### Scenario: An identifier the document states is resolved wherever it is resolved

- **WHEN** a document states an identifier that any downstream surface resolves, such as a general tolerance class
- **THEN** the screen resolves it too and reports a verdict with the near misses named, so two surfaces cannot disagree about the same document
