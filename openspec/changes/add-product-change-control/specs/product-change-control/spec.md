# Product Change Control Specification

## Purpose

What a change to a product touches, stated with evidence, in the form an engineer's change
process consumes.

## ADDED Requirements

### Requirement: Two revisions of a product are compared item by item

The system SHALL compare two product documents, or a product against the manifest of its
last release, and report each item definition as added, removed, unchanged, or changed.
For each changed item it SHALL say what changed: parameters, geometry (volume and
envelope deltas), interfaces, ratings, identity fields, and check verdicts.

#### Scenario: A longer stroke

- **WHEN** a stage's stroke parameter grows from 300 mm to 400 mm
- **THEN** the diff lists the rail, the base plate and the cover as changed geometry, the
  stage as changed, and the motor as unchanged

### Requirement: Changes are classified by form, fit and function

Each changed item SHALL be classified: fit, when any of its published interfaces changed;
function, when a rating or a check verdict on it or its parent changed; form, when only
its geometry inside its envelope or its non-interface features changed. An item changed
in fit or function SHALL be flagged as needing a new part number; an item changed only in
form SHALL be flagged for a new revision. The flag SHALL state the evidence and SHALL NOT
change the identity itself.

#### Scenario: A grown bore

- **WHEN** a housing's bearing bore changes from 47 mm to 52 mm
- **THEN** the housing is classified a fit change, flagged for a new part number, with
  the bore interface named as the evidence

#### Scenario: A pocket for weight

- **WHEN** a lightening pocket is added inside a plate and no interface or verdict changes
- **THEN** the plate is classified a form change, flagged for a revision

### Requirement: Every changed item lists where it is used

For each changed item, the system SHALL list every instance path that uses it across the
product and its variants, and every file in the baseline release manifest that contains
or references it.

#### Scenario: A shared bracket

- **WHEN** a bracket used in all four drive modules changes
- **THEN** the change lists four paths and the per-part STEP, the assembly STEP, the BOM
  and the drawings it appears in

### Requirement: A diff writes a change record

Every comparison SHALL write a change record as Markdown and JSON: the two revisions
compared, each changed item with its classification and evidence, checks newly failing and
newly passing, mass and cost deltas, affected files, and a reason field the user or agent
supplies. A record with no reason SHALL be marked reason missing, not left blank.

#### Scenario: An ECO seed

- **WHEN** an engineer compares their working product with the last release
- **THEN** the record lists every change with its evidence, ready to attach to the
  change order in their PLM

### Requirement: A changed item cannot be released under its old revision

A release SHALL be refused when an item's content differs from the same part number and
revision in the baseline release manifest, naming the item and the change. Regeneration of
unchanged content SHALL produce identical files and SHALL NOT need a revision.

#### Scenario: A silent change

- **WHEN** a plate's hole moves and its revision stays B
- **THEN** the release is refused naming the plate, the hole, and revision B
