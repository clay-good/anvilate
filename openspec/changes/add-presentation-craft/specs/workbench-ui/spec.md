# Workbench UI Specification (delta)

## ADDED Requirements

### Requirement: The workbench is built to the presentation-craft rules

The workbench SHALL conform to the presentation-craft rules in full: engineering numeric
setting with decimal alignment and stable widths, reserved layout that does not move as
results stream into the report pane, the enumerated visual vocabulary with a single
reserved accent, motion only where it shows causality, both themes from one token set, and
designed empty, waiting, and failed states for each of the three panes. The three panes
SHALL hold a stable relationship to one another, so that a pane populating does not resize
the others.

#### Scenario: Checks resolve without disturbing the reader

- **WHEN** checks stream into the report pane during a build
- **THEN** each resolves in place, the pane does not reflow, and the viewport and input
  panes do not resize

#### Scenario: Each pane has a designed nothing-yet

- **WHEN** the workbench opens with no part
- **THEN** each pane presents its designed empty state naming what starts it, rather than
  a blank area or a spinner
