# Calculation Report Specification (delta)

## MODIFIED Requirements

### Requirement: Derivation metadata is part of the check contract

Analysis functions SHALL declare derivation metadata — symbolic form, symbol glossary, and citation — as a typed, versioned artifact alongside their implementation; a check lacking derivation metadata SHALL render as a tabular inputs/outputs fallback clearly labeled as such, and CI SHALL report the coverage ratio and fail when a newly added check ships without metadata.

A check that ships without derivation metadata SHALL be registered under one of **three** distinct kinds, and the registry SHALL NOT collapse them: a **lookup**, which has no formula to render and is complete as it stands; a **numeric result**, whose value comes from solving an equation rather than evaluating an expression, so there is no substitutable line to render and the fallback table is its correct rendering; and a **debt**, which is a closed form whose derivation has not been written. Filing a debt as either of the others converts an unfinished piece of work into a decision, which is a worse silence than the one the registry replaces.

The two **complete** kinds SHALL be declared where the check is and travel with the entry, not in a file addressed by citation: a clause cited by more than one check cannot be answered once, and a registry that answers it once is wrong for every check but the first. A check SHALL NOT be able to declare itself a **debt**: debt is the absence of any declaration, recorded per clause in the ratchet's own list, and a check that could file its own debt would retire it by describing it.

A check SHALL be counted as having answered when it carries a derivation or declares one of the two complete kinds, and a clause SHALL clear the list when every entry citing it has answered.

The debt list SHALL be downward-only: a check may leave it by acquiring a derivation, and SHALL NOT leave it by being reclassified unless the stated reason changes accordingly. A check carrying a computed safety factor SHALL NOT be able to declare that it has no formula, in any kind: a safety factor is a quotient and a quotient is a formula, so the relabelling is refused on the data rather than on the wording.

#### Scenario: New check without metadata is caught

- **WHEN** a new analysis check is merged without derivation metadata
- **THEN** CI fails naming the check, unless the check is explicitly registered as tabular-only with a stated reason

#### Scenario: Fallback is honest

- **WHEN** a tabular-only check appears in a calculation report
- **THEN** its section shows inputs, outputs, margin, and citation in a table labeled "derivation not rendered," never a fabricated formula

#### Scenario: A debt cannot be retired by relabelling

- **WHEN** a check carrying a computed safety factor declares that it has no formula
- **THEN** the entry is refused at construction, and on a copy, because a formula does not become a table by being filed as one

#### Scenario: A declaration with no reason is refused

- **WHEN** a check declares that it has no formula and states no reason
- **THEN** the declaration is refused, because a reason that says nothing is the silence the declaration exists to replace

#### Scenario: One clause, two checks, one of them worked

- **WHEN** a clause is cited by a check that renders a worked calculation and by another check that has nothing to compute
- **THEN** the coverage report counts the first as worked and the second as answered, and the clause requires no entry in a side file
