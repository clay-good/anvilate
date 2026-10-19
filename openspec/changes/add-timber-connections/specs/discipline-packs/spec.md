# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Timber pack dowel-type fastener connections

The timber pack SHALL provide, when shipped, a dowel-type fastener connection screen
computing single- and double-shear lateral capacity by every applicable yield mode of the
generalized yield limit equations — main- and side-member crushing, dowel rotation, one
plastic hinge with crushing, and two or three hinges — naming the governing mode and
citing the connection section of the declared NDS edition. The dowel bending yield
strength, each member's dowel bearing strength (parallel and perpendicular to grain), and
the per-mode reduction terms SHALL be user-supplied with their citation, or, for bearing
strength, computed from a cited formula with the specific gravity declared; the pack MUST
NOT bundle the standard's tabulated values. The connection factors (group action,
geometry, end grain, toe-nail where applicable) SHALL join the existing itemized
adjustment chain, each visible with its condition. A connection missing a required
strength SHALL be not evaluated naming it, and a configuration the yield equations do not
cover SHALL be refused naming the limitation.

#### Scenario: A double-shear bolt governed by three hinges

- **WHEN** a 19 mm bolt through a 38 mm side member, a 89 mm main member and a second side
  member is screened with user-cited bearing strengths and dowel bending yield strength
- **THEN** every applicable mode's capacity is reported, the governing mode is named with
  its reduction term, the adjusted design value lists each factor with its condition, and
  the section is cited

#### Scenario: No bending yield strength, no capacity

- **WHEN** a lag screw connection is declared without a dowel bending yield strength
- **THEN** the screen is not evaluated naming the value and its accepted sources, and the
  member checks still run

#### Scenario: Spacing below the declared minimum

- **WHEN** bolts in a row are spaced below the minimum the user cited from the table
- **THEN** the geometry check fails naming the spacing, the minimum and its citation, and
  states the factor consequence the cited section prescribes
