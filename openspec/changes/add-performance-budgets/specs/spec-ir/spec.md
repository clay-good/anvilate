# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: Typed performance budget declaration

A Design Spec SHALL be able to declare performance budgets as typed, schema-validated
elements: the budgeted quantity with its allocated limit and units, the combination rule,
and the contributors with their sources and correlation groups. Budget declarations SHALL
be diffable and versioned like every other part of the document, and a declaration whose
allocated limit carries no unit SHALL be rejected rather than defaulted.

#### Scenario: Budget travels with the document

- **WHEN** a spec declaring an angular-error budget is serialized and reloaded
- **THEN** the budget, its rule, and every contributor's source round-trip unchanged

#### Scenario: Budget change is legible in a diff

- **WHEN** a contributor's allocation is tightened
- **THEN** the spec diff shows the changed contributor and limit, not a reformatted
  document

#### Scenario: Unitless allocation refused

- **WHEN** a budget declares a bare numeric limit for a physical quantity
- **THEN** the spec is rejected naming the budget and offering the plausible units, as the
  unit layer requires for every load-bearing value
