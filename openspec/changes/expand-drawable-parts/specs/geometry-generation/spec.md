# Geometry Generation Specification (delta)

## ADDED Requirements

### Requirement: Patterns share one feature vocabulary

Holes and edge treatments SHALL be built from one shared feature library used by every
pattern: through hole, blind hole, counterbore, countersink, slot, rectangular hole
pattern, bolt-circle hole pattern, fillet and chamfer. Each feature SHALL be created with
a semantic tag, SHALL be measurable by that tag (diameter, depth, position, count, pitch),
and SHALL refuse parameters that cannot be made in the host body (a hole larger than the
face it is in, an edge distance below zero, overlapping holes). A pattern MUST NOT
implement its own hole or edge treatment. A tapped hole SHALL be a hole carrying its
thread designation as data; thread helices MUST NOT be modelled.

#### Scenario: The same hole in two patterns

- **WHEN** an angle bracket and a flange each declare an M10 clearance hole
- **THEN** both are built by the same feature, carry the same tag vocabulary, and answer
  the same measurement queries

#### Scenario: A hole that does not fit is refused

- **WHEN** a pattern is asked for a hole whose edge would fall outside its face
- **THEN** the build is refused, naming the hole, the face and the shortfall, and no solid
  is produced

### Requirement: A catalog of drawable parts that covers what engineers ask for

The pattern library SHALL provide, each under the pattern contribution contract, the
single-part archetypes in the table below. Every pattern SHALL state its parameters with
units and bounds, its semantic face and feature tags, and which outputs it supports.

| Family | Patterns | Flat profile (DXF) |
| --- | --- | --- |
| Plates | base plate, cover plate, mounting plate (holes and slots), gusset plate, shear plate, tension member (flat bar) | yes |
| Lugs and clevises | lifting lug / padeye, clevis with pin hole | lug: yes |
| Brackets | angle bracket (two legs, holes, optional stiffening rib), sheet-metal bracket (L, U, Z) | sheet metal: flat pattern |
| Round parts | spacer, bushing, standoff, shaft collar, plate flange with bolt circle, pulley | no |
| Shafts | plain shaft, stepped shaft with shoulders, keyways and end chamfers, shaft key | no |
| Sections | structural member cut to length from a named section (I, channel, angle, HSS, round tube, flat bar), tube, T-slot extrusion, timber beam, pipe run | section outline |
| Catalog envelopes | rolling bearing (bore, outside diameter, width), helical compression spring | no |
| Gears | spur gear and spur gear pair, with pitch, root and tip circles | no |
| Enclosures | box and lid as a shell with wall thickness and mounting holes | no |

A named section, bearing or thread SHALL be resolved from the bundled standards data, and
a name the data does not carry SHALL be refused with near matches rather than drawn from a
guess. A catalog envelope SHALL be labelled as an envelope: it shows where the component
goes, and MUST NOT be presented as the component's manufactured geometry.

#### Scenario: A screened part is now drawn

- **WHEN** a spec declares a lifting lug that the structural pack already screens
- **THEN** it builds to one valid solid with its pin hole tagged, and its scorecard is
  unchanged by having been drawn

#### Scenario: A named section is drawn from the tables

- **WHEN** a beam member names `IPE 200` and a length
- **THEN** the solid's cross-section is that profile's tabulated outline and its length is
  the declared one

#### Scenario: An envelope says it is one

- **WHEN** a rolling bearing is drawn from its catalog designation
- **THEN** the result is labelled an envelope in the geometry summary, the rendered view
  and the STEP product name

### Requirement: Sheet-metal parts carry their flat pattern

A sheet-metal pattern SHALL be defined by its thickness, inside bend radius, bend angles
and flange lengths, and SHALL produce both the formed solid and its flat pattern. The flat
pattern SHALL be computed with a stated bend allowance method and K-factor, the K-factor
SHALL be a declared input with its source, and a bend radius below the minimum for the
declared material and thickness SHALL be reported through the existing bend-radius screen
rather than silently drawn.

#### Scenario: Flat length is stated with its basis

- **WHEN** an L-bracket in 2 mm steel with a 2 mm inside radius is built
- **THEN** the flat pattern's developed length is reported with the K-factor and bend
  allowance used to compute it

#### Scenario: The K-factor is never invented

- **WHEN** a sheet-metal part is declared without a K-factor
- **THEN** the formed solid is still built, and the flat pattern is reported not evaluated,
  naming the K-factor as what it needs

### Requirement: The catalog can be asked what it draws

A caller SHALL be able to list the drawable patterns and read, for each, its element type,
parameters with units and bounds, face and feature tags, supported outputs (views, STEP,
3MF, DXF profile, flat pattern), and whether a screen exists for it, without building
anything. The listing SHALL be generated from the pattern registry, so a pattern cannot
ship without appearing in it or appear without shipping.

#### Scenario: An agent finds the right pattern

- **WHEN** an agent asks what can be drawn
- **THEN** it receives every pattern with the parameters it must supply, and can choose
  one without trial and error

#### Scenario: A part outside the catalog

- **WHEN** a spec declares an element type no pattern draws
- **THEN** the refusal names the element type, lists the closest patterns, and states that
  shapes beyond the catalog belong in the user's CAD starting from the STEP export

### Requirement: Drawn is not screened

A pattern SHALL be buildable whether or not a discipline screen exists for its element
type. Where none exists, the scorecard SHALL carry a not-evaluated entry stating that the
part was drawn and not checked, and the rendered view and exported files SHALL carry the
same unvalidated mark a failing part carries. A drawn part MUST NOT read as a checked one.

#### Scenario: A spacer with no screen

- **WHEN** a spacer is built and no screen covers it
- **THEN** the views and STEP are produced, the card says the spacer was not evaluated, and
  the export is watermarked unvalidated

## MODIFIED Requirements

### Requirement: Pattern library contribution contract

Every pattern in the library SHALL ship with: a parametric implementation built only from
kernel primitives and the shared feature library, semantic tags, declared parameter bounds,
a default DFM profile, analytical check bindings or an explicit statement that no screen
exists, an entry in the drawable-parts catalog, a worked example spec, and at least 5
golden-file tests covering volume, tags, bounds refusals and determinism; community
contributions MUST meet the same contract to merge.

#### Scenario: Contribution without tests rejected

- **WHEN** a community pattern is submitted without golden-file tests or tag declarations
- **THEN** CI rejects the contribution with the missing contract items enumerated

#### Scenario: A pattern with its own hole code is rejected

- **WHEN** a submitted pattern cuts a hole without using the shared feature library
- **THEN** CI rejects it, naming the feature it should have used
