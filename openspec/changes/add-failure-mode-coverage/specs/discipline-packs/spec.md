# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: A module contributes the failure modes of its domain

Every module SHALL contribute failure-mode catalog entries for its domain, each cited and
keyed on declared facts, and SHALL declare for every check it publishes which catalog
modes that check addresses. A module publishing checks that address no catalog mode SHALL
fail CI unless it declares why, because a domain's screens and its domain's known failure
modes are two descriptions of the same knowledge and they must agree.

#### Scenario: Enabling a module moves the denominator

- **WHEN** a module is enabled on a spec in its domain
- **THEN** its catalog entries become applicable and the coverage population grows to
  include them

#### Scenario: Screens and modes are reconciled in CI

- **WHEN** CI validates a module
- **THEN** every published check names the modes it addresses, and every contributed mode
  resolves to a check, a test archetype, or an explicit unaddressed marker with a reason
