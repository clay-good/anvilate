# Assembly & Robotics Specification (delta)

## ADDED Requirements

### Requirement: Parts are placed by the features they share

A combination SHALL be a document that names its parts (each a catalog part with its own
spec) and, for each placed part, a mate between a tagged feature on it and a tagged
feature on a part already placed: face to face, hole pattern to hole pattern, shaft in
bore, or edge flush, with an optional declared offset and rotation step. Positions SHALL
be computed from the mates deterministically. A document MUST NOT need to state a
coordinate, and a mate that leaves a part's position ambiguous or contradicts another mate
SHALL be refused naming the mates involved.

#### Scenario: A bracket lands on its holes

- **WHEN** a bracket's hole pattern is mated to a plate's hole pattern
- **THEN** the bracket is placed with the holes coaxial and the faces in contact, with no
  coordinates in the document

#### Scenario: An under-constrained mate is refused

- **WHEN** a part is mated by a single face-to-face contact that leaves it free to slide
- **THEN** the combination is refused, saying which freedoms remain and which second mate
  would remove them

### Requirement: Standard hardware fills the holes

A combination SHALL be able to place standard fasteners and keys (bolt, screw, nut,
washer, dowel pin, parallel key) by designation from the bundled standards data into the
features they fill. Hardware SHALL be drawn as an envelope from its tabulated dimensions
and labelled as one. A designation the data does not carry SHALL be refused with near
matches.

#### Scenario: Bolts through a pattern

- **WHEN** four M10 bolts with washers and nuts are placed in a mated four-hole pattern
- **THEN** each hole receives its hardware stack, positioned from the hole and the clamped
  thickness

#### Scenario: Hardware that is not in the tables

- **WHEN** a combination names a fastener designation the standards data lacks
- **THEN** the refusal lists the nearest designations and nothing is drawn from a guess

### Requirement: A meeting of parts is checked, and a mismatch is named

Building a combination SHALL check every mate and report each as a scorecard entry: hole
patterns agree in count, pitch and position within the declared tolerance; a hole admits
its fastener with the declared clearance class; a bolt's length reaches full nut
engagement through the clamped stack; a shaft and bore report their fit class; a key fits
its keyway and seat; and no two parts interfere, with the overlap volume named when they
do. A check that cannot run SHALL be reported not evaluated. Where a discipline screen
exists for the joint (bolted connection, shaft key, interference fit), the combination
SHALL supply its inputs from the mated parts and include its result.

#### Scenario: Patterns that do not match

- **WHEN** a motor's 47.14 mm bolt pattern is mated to a bracket drilled at 50 mm
- **THEN** the mate fails, naming both patterns and the difference

#### Scenario: A bolt that is too short

- **WHEN** a 25 mm bolt is placed through a 22 mm clamped stack with a washer and nut
- **THEN** the engagement check fails, stating the length needed

#### Scenario: The joint's own screen runs

- **WHEN** a bracket is bolted to a plate and the combination declares the load
- **THEN** the bolted-connection screen runs on the mated geometry and its entries appear
  on the combination's card

### Requirement: Common combinations are short documents

The library SHALL ship worked combinations an agent can adapt, each as a document over
catalog parts: a bracket bolted to a plate; a flange pair with bolts; a shaft carrying a
key, gear, bearings and collar; a lifting lug welded to a base plate; and a frame of
structural members. A weld SHALL be a declared joint between two faces carrying its type
and size, shown by a symbol, and MUST NOT be modelled as bead geometry.

#### Scenario: An agent adapts a worked combination

- **WHEN** an agent is asked for a motor bracket with its fasteners
- **THEN** it can start from the bolted-bracket combination and change parameters, rather
  than compose placement from nothing

### Requirement: A combination exports as one assembly and a parts list

A combination SHALL export as a STEP AP242 assembly in which each part is a named
component with its transform, importing as a structured assembly in the supported CAD
tools, and SHALL produce a bill of materials listing each part or hardware item with its
quantity, designation or pattern, material and mass where known. Export SHALL be gated on
the combination's card as a single part's export is gated on its own.

#### Scenario: The assembly opens as an assembly

- **WHEN** a bracket, plate and four bolt stacks are exported
- **THEN** the STEP file imports with named components that can be selected and hidden
  individually, not as one fused body

#### Scenario: The parts list counts hardware

- **WHEN** the same combination's bill of materials is read
- **THEN** it lists one bracket, one plate, four bolts, eight washers and four nuts with
  their designations
