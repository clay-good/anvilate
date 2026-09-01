# Calculation Report Specification (delta)

## MODIFIED Requirements

### Requirement: Derivation metadata is part of the check contract

Analysis functions SHALL declare derivation metadata — symbolic form, symbol glossary, and citation — as a typed, versioned artifact alongside their implementation; a check lacking derivation metadata SHALL render as a tabular inputs/outputs fallback clearly labeled as such, and CI SHALL report the coverage ratio and fail when a newly added check ships without metadata.

A check that ships without derivation metadata SHALL be registered under one of **two** distinct categories, and the registry SHALL NOT collapse them: a **lookup**, which has no formula to render and is complete as it stands, and a **debt**, which is a formula whose derivation has not been written. Filing a debt as a lookup converts an unfinished piece of work into a decision, which is a worse silence than the one the registry replaces.

The debt list SHALL be downward-only: a check may leave it by acquiring a derivation, and SHALL NOT leave it by being reclassified as a lookup unless the stated reason changes accordingly.

#### Scenario: New check without metadata is caught

- **WHEN** a new analysis check is merged without derivation metadata
- **THEN** CI fails naming the check, unless the check is explicitly registered as tabular-only with a stated reason

#### Scenario: Fallback is honest

- **WHEN** a tabular-only check appears in a calculation report
- **THEN** its section shows inputs, outputs, margin, and citation in a table labeled "derivation not rendered," never a fabricated formula

#### Scenario: A debt cannot be retired by relabelling

- **WHEN** a check on the debt list is moved to the lookup list without its stated reason changing to one that describes a lookup
- **THEN** CI fails, because a formula does not become a table by being filed as one
