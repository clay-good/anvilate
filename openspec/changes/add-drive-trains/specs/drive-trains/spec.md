# Drive Trains Specification

## Purpose

A product that moves, checked as a machine: shaft speeds, torques and gear forces
derived from one declared input, carried through every mesh, shaft and bearing, and held
against the output, life, heat and clearance the product must deliver.

## ADDED Requirements

### Requirement: A drive train is declared over a product's items

A product SHALL be able to declare a drive train naming its shafts, the gears, couplings
and bearings each shaft carries (by item path), the meshes between gears, one input (power
and speed, or torque and speed), and the required output (a speed band, and any torque or
life requirement). Every named item SHALL resolve in the product tree, and a gear SHALL
sit on exactly one shaft.

#### Scenario: A two-stage reducer is declared

- **WHEN** a reducer declares an input shaft, a countershaft and an output shaft, two meshes
  and an input of 15 kW at 1,750 rpm
- **THEN** the drive train resolves every item by path and is ready for flow derivation

#### Scenario: A gear on no shaft

- **WHEN** a mesh names a gear that no shaft carries
- **THEN** the declaration is refused naming the gear and the mesh

### Requirement: Speed, torque and power are derived, never typed

The system SHALL derive every shaft's speed, torque and power from the input through each
mesh's tooth ratio and a declared, cited mesh efficiency, and SHALL report the output speed
against the required band as a check. A mesh screen SHALL read its torque from this flow,
and its card entry SHALL depend on the flow entry. A torque typed on a mesh inside a
declared drive train SHALL be refused naming the flow value it would contradict.

#### Scenario: Output speed inside its band

- **WHEN** a reducer with 16/72 and 16/72 meshes is driven at 1,750 rpm with a required
  output band of 82 to 88 rpm
- **THEN** the output speed is reported as 86.42 rpm and the band check passes

#### Scenario: A stray torque

- **WHEN** the agent types a pinion torque on the second mesh that differs from the derived
  value
- **THEN** the document is refused naming both values

### Requirement: The speed graph is consistent

The gear graph SHALL determine every shaft's speed exactly once. The system SHALL refuse,
before any geometry is built: two paths that give one shaft different speeds; a mesh whose
declared center distance differs from the sum of its gears' operating pitch radii; and a
layout declared reverted whose stages do not share one center distance. A drive train
with more than one input or an undriven shaft SHALL be refused naming the shaft.

#### Scenario: A reverted layout that does not close

- **WHEN** a reverted reducer's first stage has a center distance of 175 mm and its second
  180 mm
- **THEN** the drive train is refused naming both stages and both distances

### Requirement: Mesh geometry is checked within its method's validity range

Each mesh SHALL be checked for transverse contact ratio, undercut against the basic rack,
tooth tip thickness, operating center distance and backlash, each cited to the geometry
standard it follows. Every gear rating screen SHALL refuse inputs outside the validity
range its method states (for example pressure angle, helix angle and transverse contact
ratio) and SHALL name the range, never extrapolate.

#### Scenario: Undercut on a small pinion

- **WHEN** a 12-tooth, 20-degree pinion with no profile shift is declared
- **THEN** the undercut check fails naming the minimum tooth count and the profile shift
  that would avoid it

#### Scenario: Outside the rating method

- **WHEN** a mesh with a transverse contact ratio below the method's lower limit is rated
- **THEN** the rating entry is not evaluated, naming the limit, and the card does not pass

### Requirement: Mesh forces load the shafts and the bearings

Each mesh SHALL apply its tangential, radial and axial forces to both shafts at the gears'
declared positions. A shaft on two bearings SHALL be solved by statics for its bearing
reactions and its bending moment along its length. A shaft on more than two radial
supports SHALL be reported as statically indeterminate naming the supports, and the
screens that need its reactions SHALL be not evaluated unless a split is declared with its
basis. Shaft, key and bearing screens SHALL run on these derived loads, and bearing life
SHALL be held against the product's required life.

#### Scenario: A countershaft bearing short of life

- **WHEN** the countershaft's derived bearing reaction gives a rated life below the 12,000 h
  the product requires
- **THEN** the bearing entry fails naming the derived load, the computed life and the
  required life, and the failure is reported at the bearing's path and at the product

### Requirement: Shaft deflection and slope are held at gears and bearings

The system SHALL compute the shaft's deflection and slope at each gear and each bearing
under the derived loads, and report each against a limit. A limit SHALL come from the
document or a cited table; with neither, the entry SHALL be not evaluated naming what is
missing.

#### Scenario: Slope at a bearing with no limit

- **WHEN** a shaft is screened and no slope limit is declared for its ball bearings
- **THEN** the slope is reported with a not-evaluated verdict asking for the limit

### Requirement: Thermal capacity is a rating

The system SHALL rate thermal capacity when a drive train declares its housing's
dissipating area, the ambient temperature and an oil temperature limit: it SHALL compute the power lost in meshes and bearings from
the declared efficiencies and the resulting steady oil temperature, and hold it against
the limit. The method SHALL be anchored to the text of the standard it cites before it
ships. Until then, the entry SHALL be not evaluated naming the standard.

#### Scenario: Strength passes, heat does not

- **WHEN** every strength check on a compact reducer passes and its computed steady oil
  temperature exceeds the declared limit
- **THEN** the card fails on thermal capacity, naming the loss, the dissipation and both
  temperatures

### Requirement: Rotating items clear what they pass

Every rotating item SHALL be represented by its envelope of revolution about its shaft
axis. The system SHALL report the minimum clearance between each swept envelope and every
stationary item, and between swept envelopes on different shafts, against the declared
clearance. Meshing gears SHALL be exempt from each other only across their declared
working depth.

#### Scenario: A gear blank grazing the housing

- **WHEN** the output gear's tip circle comes within 1 mm of an internal housing rib against
  a declared clearance of 3 mm
- **THEN** the clearance check fails naming the gear, the rib and the gap

### Requirement: Every gear carries a data table

Each gear in a drive train SHALL carry a data block with module, number of teeth, pressure
angle, helix angle and hand, profile shift coefficient, basic rack, accuracy class, and a
test dimension (span or over-pins), with each field's term cited to the geometry and
accuracy standards it follows. The block SHALL be written with the gear's drawing and in
the release package.

#### Scenario: The data block travels with the gear

- **WHEN** a reducer's release package is written
- **THEN** each gear's drawing carries its data block, and the block's values match the
  values the meshes were checked with

### Requirement: The drive-train chain is verified against a published case study

The chain from input to every downstream screen SHALL be regression-tested against a
published worked gearbox design, re-derived rather than redistributed: the Shigley power
transmission case study (a 20 hp, 1,750 rpm compound reverted reducer). The test SHALL hold
the derived speeds, torques, transmitted loads and bearing loads to the published values
within stated tolerances.

#### Scenario: The case study reproduces

- **WHEN** the case-study reducer is declared with its published teeth, pitch and face widths
- **THEN** the countershaft speed is 388.9 rpm, the output speed 86.42 rpm, and the
  transmitted loads 540 lbf and 2,431 lbf, each within the test's tolerance
