# Frame Analysis Specification

## Purpose

Member forces solved from the declared frame by the direct stiffness method, linear
elastic, so a skid, a base, a guardrail run or a product's indeterminate load path is
screened on forces the frame actually carries rather than forces somebody typed. The
solve is deterministic, verified against closed-form cases, and produces records in the
shape the existing member-force doorway accepts, with every convention declared.

## ADDED Requirements

### Requirement: A frame is declared over tagged items

A frame SHALL be declarable as typed data over a frame-of-members combination or over a
product's connections: nodes, members each with a resolved section, material and
orientation, supports naming the restrained freedoms, member end releases, and loads
(nodal, distributed along a member, point on a member, and self-weight derived from
density). Every member and support SHALL resolve to a declared node, and a member whose
section or material does not resolve SHALL be refused naming it.

#### Scenario: A skid frame declared

- **WHEN** a skid of six rolled members declares its corner nodes, four pinned supports and
  a pump mass at two nodes
- **THEN** the frame resolves every member's section from the section library and is ready
  to solve

#### Scenario: A member on a node nobody declared

- **WHEN** a member names a node the frame does not declare
- **THEN** the declaration is refused naming the member and the node

### Requirement: The solve is linear elastic, deterministic and honest about mechanisms

The system SHALL solve the frame by the direct stiffness method in three dimensions,
first order by default, producing nodal displacements, reactions and member end forces.
A frame whose stiffness matrix is singular SHALL be refused naming the free rigid-body or
mechanism mode and the nodes involved, never solved with an added artificial restraint.
The solve SHALL report the equilibrium residual between reactions and applied loads.
Second-order (P-Δ) analysis SHALL run only when the document declares it, with the method
named on every result, so a code's own moment amplification is never applied on top of
it unknowingly.

#### Scenario: A portal frame with no lateral restraint

- **WHEN** a two-column frame is declared with both bases released in rotation and no
  bracing
- **THEN** the solve is refused naming the sway mechanism and the two base nodes

#### Scenario: Second order is a declaration

- **WHEN** a frame declares second-order analysis
- **THEN** every member force record and downstream check states that its forces include
  second-order effects by the named method

### Requirement: Solved forces feed the member checks as dependent entries

The system SHALL produce, for every member, a member-force record at stations along its
length — axial force, shears, moments and torsion with units — in the shape the
member-force ingestion contract defines, with Anvilate's own axis convention and sign
convention declared on the record and the solve recorded as the provenance. The existing
member checks SHALL run on these records, and each check's card entry SHALL depend on the
frame entry, so a frame that could not be solved leaves every member check not evaluated
naming the frame.

#### Scenario: A typo has nowhere to hide

- **WHEN** a skid's members are screened and the frame is declared
- **THEN** each member's demand comes from the solve, a moment typed on a member inside a
  declared frame is refused naming the solved value, and each entry names the frame entry
  it depends on

#### Scenario: The frame did not solve

- **WHEN** the frame is refused as a mechanism
- **THEN** every member check in it is not evaluated naming the frame, and the card does
  not pass

### Requirement: A declared frame resolves an indeterminate product load path

The system SHALL take the load split from the solve where a product's load path is
statically indeterminate and the product declares a frame over its connections, attribute each
part's interface load to the frame entry, and name on every downstream entry the
stiffnesses the split rests on. A placeholder item in the path SHALL carry a declared
stiffness with its basis or the frame SHALL be refused naming it. Without a declared
frame, the existing rule stands: the path is named indeterminate and no share is guessed.

#### Scenario: Four casters, one frame

- **WHEN** a cart on four casters, indeterminate by statics, declares a frame over its
  chassis members and caster mounts
- **THEN** each caster's load comes from the solve, each caster check names the frame entry
  and the chassis stiffnesses, and the card reports the split as solved rather than
  declared

#### Scenario: A placeholder with no stiffness

- **WHEN** the declared frame passes through a placeholder item with no declared stiffness
- **THEN** the frame is refused naming the placeholder and the stiffness it needs

### Requirement: Deflections are checked against declared limits only

The system SHALL report nodal displacements and the maximum deflection along each member,
and SHALL check them against deflection limits the document declares with their source.
With no declared limit, the deflection SHALL be reported with a not-evaluated verdict
naming the limit it needs; the system MUST NOT apply a span-ratio default.

#### Scenario: A mezzanine beam with no limit

- **WHEN** a frame is solved and no deflection limit is declared for its beams
- **THEN** each beam's deflection is reported, the entry is not evaluated naming the limit,
  and the card does not pass

### Requirement: The solve is verified against closed-form cases and an independent engine

The frame solve SHALL be regression-tested against closed-form cases re-derived from
public textbook solutions — at minimum a propped cantilever, a fixed-fixed beam, a
continuous beam, a portal frame under lateral load, and a space frame with torsion —
pinned to stated tolerances, and SHALL be cross-checked in CI against an independent
open frame engine whose identity, version and license are recorded. A drift in either
comparison SHALL fail the build naming the case.

#### Scenario: The textbook holds

- **WHEN** the test suite runs
- **THEN** each verification case reproduces its pinned reactions, moments and deflections
  within tolerance, and the independent engine agrees within the stated tolerance
