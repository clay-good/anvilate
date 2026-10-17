# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: A profile may require packs, and says so

A profile SHALL be able to name the discipline packs its required checks live in. Binding
the profile SHALL load those packs. A required pack that is not installed SHALL make its
required checks not available, naming the pack and how to install it.

#### Scenario: A missing pack

- **WHEN** the industrial-machinery profile requires the machinery pack and it is not
  installed
- **THEN** each check from that pack appears as not available, naming the pack and the
  install command
