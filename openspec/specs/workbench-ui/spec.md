# Workbench UI Specification

## Purpose

The workbench is the dead-simple three-pane screen most users ever see: Describe (chat/spec panel), Watch (live 3D viewport), Trust (validation report). One primary input, every AI decision visible and reversible, direct manipulation over re-prompting, and failure as a first-class citizen. It runs on localhost with no login and no default telemetry.

## Requirements

### Requirement: Three-pane core screen

The UI SHALL present exactly three primary panes — input/spec, live 3D viewport, and validation report — with all further functionality behind progressive disclosure; the golden-path user journey (describe → confirm → watch → trust → export) MUST be completable without leaving this screen.

#### Scenario: Golden path on one screen

- **WHEN** a new user describes a bracket, confirms the spec card, watches iterations, and exports
- **THEN** every step occurred on the core screen in under 5 minutes on a mid-range laptop with a local model

### Requirement: One primary input

The input pane SHALL accept prose, pasted dimension tables, and file drops (STEP, DXF, and roadmap-gated datasheet/drawing files) through a single text box and drop target.

#### Scenario: Mixed input

- **WHEN** the user types a description and drops a mating STEP file in the same exchange
- **THEN** both are compiled into one spec with the file registered as an interface source

### Requirement: Live viewport with engineering views

The viewport SHALL render the current B-Rep tessellation with edges, and provide section view, exploded view (assemblies), measurement probe, and a stress heat-map overlay toggle for FEA results; rendering SHALL update live as iterations complete.

#### Scenario: Stress overlay

- **WHEN** T3 completes a load case and the user toggles the stress overlay
- **THEN** the von Mises field renders on the part with a labeled color scale and the max-stress location marked by its tag

### Requirement: Visible, reversible assumptions

Every compiler assumption and default SHALL render as a tappable chip on the spec card (e.g., "SF 2.0 ▾"); changing a chip SHALL update the spec and trigger revalidation — the user never has to re-prompt to change an assumption.

#### Scenario: Changing a default

- **WHEN** the user taps the safety-factor chip and selects 1.5
- **THEN** the spec updates with the value re-tagged as user-stated and the pipeline revalidates

### Requirement: Parameter sliders bound to code

After generation, key dimensions SHALL appear as sliders/fields bound to the generated code's parameters within their pattern bounds; dragging a parameter SHALL regenerate and revalidate within seconds, while intent-level changes go through re-prompting.

#### Scenario: Thickness tuning

- **WHEN** the user drags "flange thickness" from 4 mm to 5 mm
- **THEN** the part regenerates, fast tiers re-run immediately, and the report pane updates without any LLM involvement

### Requirement: Click-to-reference geometry

The viewport SHALL let the user click a face, edge, or feature to reference it in the input pane, resolving the selection to its semantic tag; spatial references in conversation MUST be expressible by pointing, never only by prose descriptions like "the left side."

#### Scenario: Pointing beats describing

- **WHEN** the user clicks a hole in the viewport and types "make this one 8 mm"
- **THEN** the edit binds to that feature's semantic tag and the spec updates for exactly that feature, with the tag shown in the input as a removable reference chip

#### Scenario: Ambiguity eliminated

- **WHEN** a part has two similar flanges and the user references one by click
- **THEN** no clarifying question about which flange is needed — the reference is exact

### Requirement: Iteration timeline

The UI SHALL show the iteration history as a scrubbable timeline (v1 → v2 → v3 …); selecting an iteration SHALL display its geometry, spec delta, and scorecard.

#### Scenario: Comparing iterations

- **WHEN** the user scrubs between v2 and v3
- **THEN** the viewport and report update to each iteration's exact recorded state

### Requirement: Failure as a first-class citizen

When the agent cannot converge, the UI SHALL state the conflict plainly and present the Pareto alternatives as selectable cards; the UI MUST NOT bury non-convergence in a chat transcript.

#### Scenario: Conflict surfaced

- **WHEN** the loop exhausts its budget on an infeasible mass target
- **THEN** the report pane replaces the checklist with a plain-language conflict statement and option cards, each showing which constraint it relaxes

### Requirement: Report pane mirrors the scorecard

The report pane SHALL render every scorecard check with its status, measured value, threshold, and units, flipping live as checks complete, with one click opening the full evidence bundle.

#### Scenario: Live check updates

- **WHEN** validation is running
- **THEN** checks appear and transition (pending → pass/fail/warning/not-evaluated) in real time over the streaming connection

### Requirement: Local, loginless, telemetry-opt-in

The UI SHALL be served on localhost by the local backend with no account or login; usage telemetry MUST be strictly opt-in and default-off.

#### Scenario: First run

- **WHEN** the user installs the package and starts the UI
- **THEN** the workbench opens on localhost with no sign-in, and no telemetry is emitted unless explicitly enabled

### Requirement: Keyboard-first with CLI parity

Every UI action SHALL have a keyboard path, and every pipeline capability exposed in the UI SHALL be achievable headlessly via the CLI so teams can script identical behavior.

#### Scenario: UI/CLI equivalence

- **WHEN** a user exports STEP from the UI and another runs the equivalent CLI build on the same spec
- **THEN** the artifacts are identical
