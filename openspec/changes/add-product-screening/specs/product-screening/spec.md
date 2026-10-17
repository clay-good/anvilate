# Product Screening Specification

## Purpose

Screening checks that exist only at the level of a product: how load travels through it,
what it weighs and where, how close its items come, and what it costs to put together.

## ADDED Requirements

### Requirement: Product loads travel through connections to ground

A product SHALL be able to declare loads and accelerations on items and interfaces. Where
the connections from those items to ground form a statically determinate path, the system
SHALL solve rigid-body equilibrium and report the force and moment at every connection on
the path, each with the equilibrium it came from. Each part SHALL then be screened with
the interface loads it carries, as an entry downstream of the load-path entry.

#### Scenario: A payload reaches the feet

- **WHEN** a frame on four casters carries a declared 50 kg payload on its top plate
- **THEN** the load at each connection from plate to casters is reported, and each caster
  is checked against its rating with the share it carries

#### Scenario: A part screened with its share

- **WHEN** the same load passes through a bolted bracket
- **THEN** the bracket's bending and its bolted-joint entries read the connection load,
  and name the load-path entry they depend on

### Requirement: An indeterminate load path is named, not split by guess

Where the path from a load to ground is statically indeterminate, the system SHALL report
the load path indeterminate, name the redundant connections, and mark every part screen
that would read a share from it as not evaluated. It SHALL NOT divide load between
redundant connections by any default rule. A user-declared split with a stated basis
SHALL be accepted and carried as that declaration.

#### Scenario: A plate on six supports

- **WHEN** a plate is held to ground by six connections where three would determine it
- **THEN** the card reports the path indeterminate, names the redundant connections, and
  the downstream screens are not evaluated until a split is declared

### Requirement: Mass properties roll up with their basis

Every node SHALL report mass, center of mass and inertia about its own frame, rolled up
from its children. Each contribution SHALL state its basis: computed from geometry and
density, declared by a component record, or a placeholder. A child with no mass SHALL make
the parent's mass not evaluated, naming the child. A declared mass or center-of-mass limit
SHALL be evaluated through the budget mechanism.

#### Scenario: A placeholder in the total

- **WHEN** a 14.2 kg product includes a 2.4 kg placeholder gearbox
- **THEN** the total is reported with the placeholder's share named as provisional

#### Scenario: A CG limit for a tip-over check

- **WHEN** a cart declares that its center of mass must lie within the caster footprint
  up to 8 degrees of tilt
- **THEN** the entry reports the tilt at which the center of mass leaves the footprint

### Requirement: Minimum clearance is reported between every pair

Every product build SHALL report the minimum distance between each pair of items that do
not share a connection, against a declared minimum clearance, with the location of the
closest approach. Over each declared joint range, the swept clearance SHALL be reported at
the worst sampled position, with the sampling stated.

#### Scenario: A cable cover too close to a pulley

- **WHEN** a pulley passes within 0.8 mm of a cover against a declared 2 mm clearance
- **THEN** the entry fails, naming both items, the gap and its location

### Requirement: Mobility is counted honestly

The system SHALL report a Grübler–Kutzbach mobility count from the declared joints, with
the formula and each joint's freedoms. Where the count is zero or negative, or two joint
axes are parallel or coincident, the entry SHALL say the count may be wrong for that
reason and name the joints. It SHALL NOT state that a product cannot move.

#### Scenario: A door on three hinges

- **WHEN** a lid is held by three coaxial revolute joints
- **THEN** the count is reported as negative, the three coaxial joints are named, and the
  entry states the count is unreliable because the axes are coincident

### Requirement: Dissimilar joints are checked for thermal mismatch

For each connection between items of different materials, under a declared temperature
range, the system SHALL report the differential growth across the connection's span and
compare it with the connection's clearance or declared slip allowance, citing the
expansion coefficients used. A connection with no declared range SHALL be listed as not
evaluated.

#### Scenario: Aluminum plate on a steel frame

- **WHEN** a 600 mm aluminum plate is bolted at its ends to a steel frame over a 60 K
  range
- **THEN** the entry reports about 0.4 mm of differential growth against the hole clearance,
  citing both coefficients

### Requirement: Assembly economy is reported as candidates

Every product build SHALL report its part count, the count of unique fastener
designations, and the count of distinct tools the fasteners need. It SHALL list merge
candidates: pairs of connected items that do not move relative to each other, share a
material, and are not separated for service, by the three classic part-count questions.
These SHALL be advisory entries and SHALL NOT affect the verdict.

#### Scenario: Eleven fastener sizes

- **WHEN** a product uses eleven fastener designations where three sizes would serve
- **THEN** the report lists the eleven with their counts and the tools each needs

### Requirement: Cost rolls up as a screening estimate

Every node SHALL report a screening-grade cost rolled up from its children: part
estimates from the cost-estimation capability and component unit prices the user
supplies with a source and date. A child with no estimate SHALL be listed, and the total
SHALL be labeled incomplete rather than summed as zero.

#### Scenario: A motor with no price

- **WHEN** a product's motor record carries no price
- **THEN** the cost total is labeled incomplete, naming the motor
