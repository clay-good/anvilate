# Presentation Craft Specification (delta)

## ADDED Requirements

### Requirement: Numbers are set so they can be compared at a glance

Every surface SHALL set numeric values in figures of fixed advance width, align columns of
values on the decimal separator, and place the unit in a consistent position relative to
the value. A value that updates in place SHALL retain its width and MUST NOT move itself
or its neighbours, and identical input SHALL produce character-identical rendering across
renders. Comparing a column of margins is the single most common thing a reader does with
this tool, and a column that cannot be scanned is a column that will be misread.

#### Scenario: A margin column scans

- **WHEN** a scorecard renders ten checks with values of differing magnitude
- **THEN** their decimals align and the digits occupy fixed-width positions

#### Scenario: A live value does not shove the layout

- **WHEN** a streaming value changes from one digit to three
- **THEN** its width is unchanged and nothing around it moves

#### Scenario: Rendering is stable

- **WHEN** the same result is rendered twice
- **THEN** the two renderings are character-identical

### Requirement: The layout does not move while it fills

Surfaces that populate progressively SHALL reserve the space their content will occupy, so
that results arriving do not reflow what is already on screen. A check transitioning from
pending to resolved SHALL change in place, and the arrival of a later result MUST NOT
displace an earlier one the reader may already be looking at. Layout stability SHALL be
checked in CI over a reference corpus rather than left to inspection.

#### Scenario: Reading is not interrupted by arrival

- **WHEN** a user is reading the third check while the eighth resolves
- **THEN** the third check does not move

#### Scenario: Stability is gated

- **WHEN** the layout-stability check runs over the reference corpus
- **THEN** a change that displaces settled content fails until acknowledged

### Requirement: The visual vocabulary is small and chrome earns its place

The interface SHALL be built from an enumerated set of visual elements, and any element
that encodes no information SHALL be removed unless it earns its place by separating,
grouping, or orienting. Decorative gradients, drop shadows used for ornament, illustration,
and background imagery MUST NOT appear. A lint SHALL reject elements outside the
enumerated vocabulary, so restraint is maintained by a gate rather than by whoever is
reviewing that week.

#### Scenario: Ornament is rejected

- **WHEN** a rendering introduces a decorative element carrying no information
- **THEN** the vocabulary lint fails naming the element

#### Scenario: Separation is information

- **WHEN** a rule or spacing distinguishes two groups of checks
- **THEN** it is permitted, because it encodes the grouping

### Requirement: One accent colour, reserved, and nothing depends on colour

The palette SHALL consist of a neutral ground and ink plus exactly one accent, and the
accent SHALL be reserved for the element the user is currently acting on. Status colours
SHALL be used only to carry status and never decoratively. No information SHALL depend on
colour, in keeping with the accessibility rules: every status carries a word or mark, and
the interface remains fully usable rendered in neutral tones alone.

#### Scenario: The accent means one thing

- **WHEN** the accent appears on screen
- **THEN** it marks the current focus or selection, and no other element uses it

#### Scenario: Neutral rendering loses nothing

- **WHEN** the interface is rendered with status colours suppressed
- **THEN** every status remains identifiable and every action remains available

### Requirement: Motion shows causality and nothing else

Motion SHALL be used only to show that one thing changed because of another — a value
updating in response to a parameter, a pane resolving from a state the user caused — with
a bounded duration. Nothing SHALL animate on a timer, loop, or celebrate an outcome, and a
reduced-motion preference SHALL remove all motion without removing information.

#### Scenario: The cause is visible, briefly

- **WHEN** dragging a parameter updates a margin
- **THEN** a brief transition connects the cause to the effect and then stops

#### Scenario: Nothing celebrates

- **WHEN** a card passes every check
- **THEN** the result is presented plainly, with no animation or emphasis beyond the
  verdict itself

#### Scenario: Reduced motion is complete

- **WHEN** the user's system requests reduced motion
- **THEN** no motion occurs anywhere and no information is lost with it

### Requirement: Light and dark are one design, derived from one source

Light and dark SHALL both be first-class and SHALL be generated from a single token set,
so that a colour changed in one is changed in both and the two cannot drift. Contrast
SHALL be checked in CI in both themes, and every state that is distinguishable in one
SHALL be distinguishable in the other.

#### Scenario: A palette change reaches both themes

- **WHEN** a status colour is adjusted
- **THEN** both themes update from the shared token, and neither is edited independently

#### Scenario: Contrast is a gate in both

- **WHEN** the contrast check runs
- **THEN** it evaluates both themes and fails on either

### Requirement: Empty, waiting, and failed states are designed, not defaults

Every pane SHALL have a designed state for having nothing yet, for waiting, and for having
failed, each stating what the state is and what the user can do from it. A pane MUST NOT
present a bare spinner where it could present content, and a failed state MUST NOT be a
blank pane, because an interface that goes empty is indistinguishable from one that broke.

#### Scenario: Empty is an invitation, not a void

- **WHEN** the report pane has no results yet
- **THEN** it states that no build has run and names the action that starts one

#### Scenario: Failure is legible in place

- **WHEN** a pane's operation fails
- **THEN** the pane states what failed and its remedy, rather than clearing

### Requirement: The tool's voice is an instrument's voice

User-facing text SHALL be plain, specific, and free of jokes, congratulation,
anthropomorphism, and easter eggs, and a CI gate SHALL check user-facing strings for those
registers. A passing verdict SHALL be reported as a result and never as praise, and a
failure SHALL be reported without apology or sympathy: an engineer reading a failed check
wants the value, the threshold, and the remedy, and everything else is in the way.

#### Scenario: A pass is a result

- **WHEN** every check passes
- **THEN** the surface states the verdict and its basis, with no congratulatory language

#### Scenario: A failure is information, not an apology

- **WHEN** a check fails
- **THEN** the message gives the measured value, the threshold, and the remedy, and says
  nothing else

### Requirement: The report prints as a document

The rendered report SHALL paginate as a document: a check's derivation is not split across
a page break, tables repeat their headers on each page, no content depends on colour, and
page furniture carries the part identity, revision, and page numbering. Identical input
SHALL produce a byte-identical PDF, so a reissued submittal differs only where the
engineering differs.

#### Scenario: A derivation stays whole

- **WHEN** a derivation would straddle a page boundary
- **THEN** it moves to the next page rather than splitting

#### Scenario: Reissue diffs only where the work changed

- **WHEN** an unchanged report is regenerated
- **THEN** the PDF is byte-identical to the previous one

#### Scenario: Printed in monochrome, complete

- **WHEN** the report is printed without colour
- **THEN** every verdict, grouping, and emphasis survives

### Requirement: The viewport reads as an engineering object

The viewport SHALL default to an orthographic projection with legible edges, present a
scale reference the user can read a size from, and use lighting that reveals form without
implying a material or finish the part does not have. Any overlaid field SHALL carry a
labelled scale with units, and no view SHALL present the model in a way that flatters its
geometry at the expense of reading it accurately.

#### Scenario: The default view is the engineering view

- **WHEN** a part first renders
- **THEN** it is orthographic with visible edges and a readable scale reference

#### Scenario: A field is never an unlabelled gradient

- **WHEN** a result field is overlaid on the model
- **THEN** it carries a labelled scale with units and its extreme located by tag

### Requirement: Craft is gated, not asserted

A visual-regression corpus SHALL cover every pane state and both themes, and a change to
any rendering SHALL fail until acknowledged with its diff shown. The numeric-alignment,
layout-stability, contrast, vocabulary, and voice checks SHALL run in CI with a stated
population size, so that a gate which stopped examining anything fails rather than passes.

#### Scenario: A rendering change is a deliberate act

- **WHEN** a change alters how a card renders
- **THEN** CI fails showing the visual diff, and passes only once the new rendering is
  accepted

#### Scenario: The gates report what they examined

- **WHEN** the craft gates run
- **THEN** each reports the number of surfaces, strings, or states it examined against a
  floor
