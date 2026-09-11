# Workbench UI Specification (delta)

## ADDED Requirements

### Requirement: The UI carries the same progress, cancellation, and remedy guarantees

The workbench SHALL surface the same progress, cancellation, remedy, and accessibility
guarantees the interaction-quality capability requires of every surface, so that neither
the UI nor the CLI is the better-behaved one. A long operation SHALL show its current
activity and be cancellable from the pane that started it, every refusal shown in the UI
SHALL carry its remedy rather than only its reason, and no status in the interface SHALL
be distinguishable by colour alone.

#### Scenario: The viewport does not freeze in silence

- **WHEN** a build runs a long solve
- **THEN** the workbench shows the current activity and offers cancellation without
  blocking the rest of the interface

#### Scenario: A refusal in the UI is actionable in the UI

- **WHEN** a not-evaluated entry appears in the report pane
- **THEN** its remedy is shown with the declaration it needs, and acting on it is possible
  from that pane

#### Scenario: Parity is tested, not asserted

- **WHEN** the parity suite runs
- **THEN** it checks that refusals reaching the UI carry the same remedies the CLI emits
  for the same condition
