# Discipline Packs Specification (delta)

## MODIFIED Requirements

### Requirement: Packs are optional, lazily loaded, and invisible when disabled

Discipline packs SHALL be individually enable-able, add nothing to install size requirements of the core beyond their own data, and contribute no vocabulary, patterns, samples, or checks while disabled; the core mechanical experience MUST remain unchanged when no pack is enabled.

#### Scenario: Mechanical user never sees structural jargon

- **WHEN** a user with no packs enabled lists what Anvilate can screen or draw
- **THEN** no structural or industrial pack terms, samples, or check categories appear in the catalog, the tool descriptions or any result

#### Scenario: Enabling a pack is one action

- **WHEN** a user enables the structural pack
- **THEN** its samples and archetypes appear in the catalog, and its unit default (US customary) is offered for new specs
