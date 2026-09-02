# Calculation Report Specification (delta)

## MODIFIED Requirements

### Requirement: Derivation metadata is part of the check contract

Analysis functions SHALL declare derivation metadata — symbolic form, symbol glossary, and citation — as a typed, versioned artifact alongside their implementation; a check lacking derivation metadata SHALL render as a tabular inputs/outputs fallback clearly labeled as such, and CI SHALL report the coverage ratio and fail when a newly added check ships without metadata.

A check that ships without derivation metadata SHALL be registered under one of **three** distinct kinds, and the registry SHALL NOT collapse them: a **lookup**, which has no formula to render and is complete as it stands; a **numeric result**, whose value comes from solving an equation rather than evaluating an expression, so there is no substitutable line to render and the fallback table is its correct rendering; and a **debt**, which is a closed form whose derivation has not been written. Filing a debt as either of the others converts an unfinished piece of work into a decision, which is a worse silence than the one the registry replaces.

The declaration SHALL be made where the check is, not in a file addressed by citation: a clause cited by more than one check cannot be answered once, and a registry that answers it once is wrong for every check but the first.

The debt list SHALL be downward-only: a check may leave it by acquiring a derivation, and SHALL NOT leave it by being reclassified unless the stated reason changes accordingly.

#### Scenario: New check without metadata is caught

- **WHEN** a new analysis check is merged without derivation metadata
- **THEN** CI fails naming the check, unless the check is explicitly registered as tabular-only with a stated reason

#### Scenario: Fallback is honest

- **WHEN** a tabular-only check appears in a calculation report
- **THEN** its section shows inputs, outputs, margin, and citation in a table labeled "derivation not rendered," never a fabricated formula

#### Scenario: A debt cannot be retired by relabelling

- **WHEN** a check on the debt list is moved to another kind without its stated reason changing to one that describes that kind
- **THEN** CI fails, because a formula does not become a table by being filed as one

#### Scenario: One clause, two checks, one of them worked

- **WHEN** a clause is cited by a check that renders a worked calculation and by another check that has nothing to compute
- **THEN** the coverage report counts the first as worked and the second as answered, and the clause requires no entry in a side file
