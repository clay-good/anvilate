# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: DFM rules measure the built solid against a process profile

Each T2 DFM rule SHALL measure a property of the built solid (radius, depth ratio, wall
thickness, draft angle, overhang angle, distance) and compare it with a threshold from the
part's process profile. Each threshold SHALL carry a source, or be labeled a
practice-based default. A finding SHALL name the face or edge by tag, the measured value,
the limit, and the repair lever.

#### Scenario: A deep hole

- **WHEN** a milled part has a 4 mm hole 52 mm deep against a profile limit of 10
  diameters
- **THEN** the rule fails, naming the hole's tag, the ratio 13, the limit 10, and the
  hole diameter or depth as the levers

### Requirement: A shop's own numbers replace the defaults, with a source

A user SHALL be able to supply a process profile that overrides any threshold, each
override carrying its source (a shop's capability sheet, a supplier guideline). A rule
evaluated against an override SHALL say so on its entry. An override with no source
SHALL be refused naming the threshold.

#### Scenario: A shop with a smaller end mill

- **WHEN** a profile from the user's shop sets the smallest end mill diameter to 1.5 mm with
  the shop's sheet as source
- **THEN** a 0.5 mm internal radius fails against the 0.75 mm minimum radius, and the entry
  cites the shop sheet

### Requirement: Rule packs cover the common processes

The library SHALL ship rule packs for CNC milling and turning, sheet metal, injection
molding, die casting, additive processes (material extrusion, powder bed fusion) and
weldments, selected by the part's declared process. A rule that cannot measure its
property on the part's geometry SHALL be not evaluated, naming the property.

#### Scenario: A rib that will sink

- **WHEN** a molded part with a 2.5 mm nominal wall carries a 2.5 mm rib against a
  profile ratio of 0.6
- **THEN** the rib-ratio rule fails, naming the rib and the 1.5 mm maximum

#### Scenario: A flange too close to a bend

- **WHEN** a sheet-metal hole edge lies 1 mm from a bend in 2 mm steel against a profile
  minimum of 2.5 thicknesses plus the bend radius
- **THEN** the rule fails, naming the hole, the bend, and the required distance

### Requirement: DFM findings do not hide physics findings

DFM rules SHALL report alongside, not instead of, the physics checks, and a DFM failure
SHALL NOT make a physics check not evaluated. The scorecard SHALL let a reader filter
manufacturability findings from strength and stiffness findings.

#### Scenario: Both kinds on one card

- **WHEN** a bracket fails a corner-radius rule and passes its bending check
- **THEN** both entries appear, and the bending verdict is unchanged by the DFM failure
