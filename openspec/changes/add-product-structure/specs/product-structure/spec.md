# Product Structure Specification

## Purpose

A product as a tree: reusable definitions placed as instances, each with an identity the
user's PDM, PLM and ERP can carry, any of which may still be a placeholder. The tree is
what every product-level check, export and change record addresses.

## ADDED Requirements

### Requirement: A product is a tree of placed items

A product document SHALL name its items: catalog parts, combinations, other products,
purchased components, or placeholders. Exactly one item SHALL be the ground, and every
other item SHALL be placed through mates to an item already placed, using the combination
mate vocabulary; a product MUST NOT need to state a coordinate. A product SHALL be usable
as an item in another product unchanged, and a containment cycle SHALL be refused.

#### Scenario: A sub-assembly is placed as one item

- **WHEN** a linear-stage product places a drive-module product on its base plate through
  a hole-pattern mate
- **THEN** the drive module's own parts move with it, and its internal mates are not
  restated in the stage document

#### Scenario: A product that contains itself

- **WHEN** product A places product B and product B places product A
- **THEN** the document is refused naming both, before any geometry is built

### Requirement: Defined once, placed many times

An item SHALL be defined once and referenced by any number of instances. A linear or
circular pattern SHALL be declared by count, spacing or angle, and the reference it
repeats along. A change to a definition SHALL reach every instance in the next build, and
an instance SHALL NOT alter its definition's geometry. A mirrored item SHALL be its own
definition, never a negatively scaled instance, because an opposite-hand part is a
different part to make and to buy.

#### Scenario: Four feet from one definition

- **WHEN** a frame declares a foot once and a rectangular pattern of four
- **THEN** the tree holds one foot definition with four instances, and the parts list
  counts four

#### Scenario: A mirrored bracket

- **WHEN** a document places a left-hand bracket by mirroring the right-hand one
- **THEN** the document is refused, saying the mirror needs its own definition and part
  number

### Requirement: Every definition carries an item identity

Every definition SHALL carry an item identity: a part number, a revision, a description,
and a source of make, buy or reference. Part numbers SHALL be unique within a product
tree. A definition with no part number SHALL be given a deterministic provisional one,
marked provisional on every surface that shows it. Every instance SHALL be addressable by
a path of instance names (`stage/drive[2]/motor`) that does not change when siblings are
added or reordered.

#### Scenario: Provisional numbers are visible

- **WHEN** an agent builds a product without assigning part numbers
- **THEN** every item has a provisional number, and the parts list and the STEP product
  names mark each one provisional

#### Scenario: A duplicated part number

- **WHEN** two different brackets are both numbered `100-0012`
- **THEN** the product is refused naming both paths and the shared number

### Requirement: A placeholder is a declared envelope, and its conclusions say so

An item SHALL be allowed to be a placeholder: an envelope solid, a mass with a center of
mass, the interfaces it offers, and a stated reason it is not yet detailed. Placeholders
SHALL take part in placement, interference, keepout and mass roll-up exactly as detailed
items do. Every check whose result depends on a placeholder SHALL say which placeholder
and that the result is provisional. A product containing placeholders SHALL NOT export as
released (see `release-package`).

#### Scenario: Layout before detail

- **WHEN** a product is built with the gearbox as a 120 x 90 x 80 mm, 2.4 kg placeholder
- **THEN** interference and mass roll-up run, and each result touching the gearbox names
  it as a placeholder

### Requirement: A layout holds shared datums and driving parameters

A product SHALL be able to declare a layout: named datums (points, axes, planes) and named
driving parameters with units and provenance. Items SHALL be able to mate to layout datums
and read layout parameters by name, resolved before the item is built. The layout SHALL
NOT appear in any parts list, mass roll-up or manufacturing export. A parameter that no
item reads SHALL be reported as unused.

#### Scenario: One shaft diameter drives three parts

- **WHEN** a layout declares `shaft_dia = 20 mm` and the shaft, the bearing seat and the
  collar each read it
- **THEN** changing the layout to 25 mm changes all three in the next build, and no part
  document is edited

### Requirement: Variants are named and each is checked

A product SHALL be able to declare named variants, each a set of item substitutions and
parameter overrides against the base product. Each variant SHALL resolve to a complete
product and SHALL be built, checked and exported as its own product with its own card. A
variant that substitutes an item with one that does not offer the interfaces its mates
use SHALL be refused naming the mate.

#### Scenario: A long-stroke variant

- **WHEN** a stage declares a `long` variant overriding the stroke parameter and
  substituting a longer rail
- **THEN** both the base stage and the long stage get their own cards, and a check that
  fails only on the long stage is reported against it alone

### Requirement: Every node of the tree has a card, rolled up

Building a product SHALL produce a card for every node of the tree: its own checks, its
children's verdicts, and checks that span its children. A parent's verdict SHALL be the
worst of its own entries and its children's verdicts, with "not evaluated" never counted
as a pass. A finding SHALL be reported once at the node that owns it, and referenced, not
repeated, at every ancestor.

#### Scenario: A failure deep in the tree

- **WHEN** a bolt in the third drive module's motor mount is too short
- **THEN** the motor-mount combination's card fails, the drive module and the product
  fail by reference to it, and the finding is stated once with its path

### Requirement: Unchanged items are not rebuilt

A product build SHALL key each definition's built geometry and card on the content of its
resolved inputs, so that a rebuild after a change rebuilds only the definitions whose
inputs changed and the checks that span them. A reused result SHALL be byte-identical to
the one a full rebuild would produce, and the build summary SHALL state how many
definitions were rebuilt and how many reused.

#### Scenario: One parameter, one rebuild

- **WHEN** an agent changes the collar's bore in a 40-item product
- **THEN** the collar and the checks touching it are rebuilt, the summary says one of
  forty definitions was rebuilt, and the final card equals a cold build's
