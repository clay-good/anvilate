# Input Ingestion Specification (delta)

## ADDED Requirements

### Requirement: A folder of context can be inventoried

Given a folder inside a declared context root, the system SHALL list its engineering files
with, for each: its format, its size, whether Anvilate reads it deterministically (STEP,
DXF, STL, 3MF, calibration certificates, text requirement sheets), whether it is the
agent's to read (images, PDFs, prose), or whether it is unsupported with the conversion
that would make it readable. The listing SHALL read no file contents beyond what
identifies the format, and SHALL be bounded in count and depth with the remainder stated.

#### Scenario: An agent learns what is in the folder

- **WHEN** an agent inventories a project folder holding STEP, DXF, PNG, PDF and DWG files
- **THEN** it is told which files to pass to Anvilate's readers, which to read itself, and
  that the DWG files need exporting to DXF first

### Requirement: A STEP part is read as measured facts

The system SHALL read a STEP file and report, without model involvement: the unit the
file was written in and the unit values are reported in; each solid with its name, overall
dimensions, volume and, where a material is supplied, mass; planar faces with area and
normal; cylindrical faces grouped into holes and bosses with diameter, depth and axis;
hole patterns with count, pitch and bolt-circle fit; and, for an assembly, the component
tree with names and placements. A hole built from several faces SHALL be recognised as one
hole. Anything the reader cannot classify SHALL be counted and reported as unclassified,
never dropped, and a file with no solid SHALL be refused with what it contains instead.

#### Scenario: An inch file is not silently millimetres

- **WHEN** a STEP file written in inches is read
- **THEN** the result states that the file's unit is the inch and that the reported values
  are in millimetres

#### Scenario: A split hole is one hole

- **WHEN** a through hole is modelled as two half-cylinders
- **THEN** it is reported once, with its full diameter

#### Scenario: An assembly keeps its parts

- **WHEN** an assembly STEP is read
- **THEN** each component is reported under its own name with its placement, not merged
  into one body

### Requirement: Meshes are read as meshes

The system SHALL read STL and 3MF files as triangle meshes and report overall dimensions,
volume where the mesh is closed, and triangle count, stating the unit as declared by the
file or as not stated. A mesh result SHALL be labelled as a mesh and MUST NOT be offered as
faces, holes or design intent.

#### Scenario: A scan gives a size, not a design

- **WHEN** an STL of an existing part is read
- **THEN** its bounding size and volume are reported with the note that a mesh carries no
  features, and no hole or face is claimed

### Requirement: Unsupported formats are refused with the step that fixes them

DWG, IGES, Parasolid and native CAD files SHALL be refused by name, with the instruction
to export STEP (for 3D) or DXF (for 2D) from the originating tool. The system MUST NOT
bundle or invoke a converter, and MUST NOT attempt a partial read.

#### Scenario: A DWG is not guessed at

- **WHEN** a DWG file is offered
- **THEN** the refusal says to export DXF from the CAD tool, and nothing is read

### Requirement: A read file can seed a catalog part

A measured closed DXF profile or STEP part SHALL be offerable as starting parameters for a
matching catalog pattern (a rectangular profile with holes as a mounting plate, a cylinder
with a bore as a spacer). Each seeded parameter SHALL carry the file as its source, and a
shape no pattern matches SHALL be reported as such with its measurements rather than
forced into one.

#### Scenario: A plate like this drawing

- **WHEN** an agent asks for a mounting plate matching a DXF outline with four holes
- **THEN** it receives the pattern's parameters filled from the measured profile, each
  citing the DXF, ready to change

## MODIFIED Requirements

### Requirement: DXF dimension reading

The system SHALL read an imported DXF drawing and report: the drawing unit, taken from the
caller's statement or the file's declared unit and never assumed when neither is present;
its layers; its closed profiles, assembled from connected lines, arcs and splines within a
stated tolerance as well as from closed polylines, each with its overall size, area and
contained holes; block insertions with their scale applied; and its dimension entities,
including their measured values and text overrides, offered as typed dimension inputs,
flagging any dimension whose text override disagrees with its measured geometry.

#### Scenario: Mounting plate DXF

- **WHEN** the user drops a DXF of a mounting plate with dimensioned hole spacing
- **THEN** the hole-spacing dimensions are extracted with values and offered as interface data

#### Scenario: Override disagreement flagged

- **WHEN** a DXF dimension's text override differs from the geometry it measures
- **THEN** the conflict is surfaced to the user for resolution rather than either value being silently trusted

#### Scenario: A unitless drawing is not assumed to be millimetres

- **WHEN** a DXF declares no unit and the caller states none
- **THEN** the read is refused, asking for the drawing's unit

#### Scenario: A profile drawn as separate lines is still a profile

- **WHEN** a plate outline is drawn as four lines and four arcs that meet end to end
- **THEN** it is reported as one closed profile with its size

### Requirement: Vision-based drawing extraction is confirmation-gated and provenance-tagged

Anvilate SHALL NOT read dimensions from raster images, scans, photographs or PDF figures;
that reading is done by the user's agent. A value an agent reads from such a source SHALL
enter a spec only as an agent-read value naming the source file and where in it the value
appears, SHALL remain a draft until a person confirms it, and MUST NOT be presented as
measured or as user-stated. Where the same dimension is available from a file Anvilate
reads deterministically, the measured value SHALL be offered in preference and a
disagreement between the two SHALL be reported.

#### Scenario: Scanned drawing ingestion

- **WHEN** an agent reads an 80 mm width from a scanned drawing and writes it into a spec
- **THEN** the value is recorded as agent-read from that file and marked unconfirmed

#### Scenario: A measurement outranks a reading

- **WHEN** the agent read 80 mm from a picture and the STEP file of the same part measures 82 mm
- **THEN** both are reported with their sources and the difference is flagged for the person to settle
