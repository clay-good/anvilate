# Local FEA Specification

## Purpose

The T3 tier, built: a part or a product meshed and solved on the user's machine with an
open mesher and an open solver run as separate processes. Results are read back into the
scorecard under the same convergence, assumption and no-silent-green rules as every
other check.

## ADDED Requirements

### Requirement: The pipeline runs locally from tags to verdicts

The system SHALL run the T3 tier end to end with no human step: export the built solid
with its semantic tags; mesh it with Gmsh, mapping every tag a load case or support names
to a physical group; write a CalculiX input deck; run the solver as a subprocess; and read
displacements, stresses, temperatures and reactions from its result files into typed
check entries. The mesher and solver SHALL run as separate processes with file
interchange only, inside the sandbox (no network, scratch directory only, CPU, memory and
time caps). Tags SHALL be carried to the mesh by geometric signature (each tagged face's
area, centroid and normal recorded at build time and matched after import), never by
entity name alone, and the match SHALL be verified: a tag that resolves to no face, to a
face whose area differs from the recorded one, or to more faces than were tagged SHALL
abort the run as a setup failure naming the tag.

#### Scenario: A bracket from spec to verdict

- **WHEN** an agent asks for the FEA tier on a bracket with a fixed base and a tip load
- **THEN** the run meshes, solves and returns a von Mises stress entry and a displacement
  entry, each locating its peak by tag, with no file touched by the user

#### Scenario: A support on a tag the mesh lost

- **WHEN** a load case fixes a tagged face that maps to an empty physical group after meshing
- **THEN** the run is aborted as a setup failure naming the tag, and every FEA entry is not
  evaluated

### Requirement: The solver is found, pinned and reported, never fetched silently

The system SHALL locate the CalculiX and Gmsh executables from an explicit setting, the
active environment, or the path, in that order, and SHALL run each only when its reported
version lies in the release's pinned range. The version, the executable's digest and the
solver options SHALL be recorded in the evidence bundle of every run. When the solver or
mesher is absent, every FEA entry SHALL be not evaluated, naming the capability and the
command that installs it on the user's platform; no executable SHALL be downloaded
without the user's consent for that executable.

#### Scenario: No solver installed

- **WHEN** the FEA tier is demanded on a machine with no CalculiX executable
- **THEN** each FEA entry is not evaluated with the install command for the platform, and
  the card does not pass

#### Scenario: A solver outside the pinned range

- **WHEN** the found CalculiX reports a version outside the pinned range
- **THEN** the run is refused naming the found and the supported versions

### Requirement: Steady-state thermal and thermal stress

The FEA tier SHALL support steady-state heat transfer with declared temperatures,
heat fluxes, internal heat generation and convection (film coefficient and sink
temperature) on tagged faces, reporting peak temperature and the temperature at each
tagged region against declared limits. When a load case declares a thermal state and a
structural load together, the temperature field SHALL be applied to the structural
analysis and the reported stress SHALL include the thermal strain. Each thermal input
SHALL carry its source, and a material without the thermal properties the analysis needs
(conductivity, expansion coefficient) SHALL make the affected entries not evaluated
naming the property.

#### Scenario: A housing's thermal stress

- **WHEN** a gearbox housing declares a 90 °C oil-wetted interior, convection to 25 °C air
  on its outer faces, and its bearing loads
- **THEN** the card reports the peak housing temperature and the combined thermal and
  mechanical stress, each with the load case named

#### Scenario: Missing expansion coefficient

- **WHEN** a thermal-stress case runs on a material with no expansion coefficient
- **THEN** the stress entries are not evaluated naming the property, and the temperature
  entries still report

### Requirement: Products are solved with bonded connections

A product, or a named sub-tree of one, SHALL be solvable as one model in which each
declared connection between items is a bonded (tied) contact between the mated faces.
Loads and supports SHALL be addressed by item path and tag. Every product FEA result
SHALL state that its connections were idealized as bonded. A connection whose real
behavior bonding cannot represent (a bolted joint that may separate, a bearing that
rotates) SHALL be named in the result as idealized, and the joint's own hand screen SHALL
remain the check for that joint.

#### Scenario: A housing and its covers

- **WHEN** a reducer housing and its two covers are solved with their bolted flanges tied
- **THEN** the result reports stress across all three items by path, states that the flanges
  were bonded, and the flange bolts are still screened by the bolted-joint check

#### Scenario: A tie that did not connect

- **WHEN** the solver reports slave nodes on a tied connection that found no master face
- **THEN** the run is not evaluated, naming the connection and the count of unconnected
  nodes, never reported with part of the interface left free

### Requirement: Stress singularities are named, not reported as stress

A governing stress SHALL be reported as a singularity when it grows without converging
under refinement at a re-entrant corner, a point load or a point support: reported at
its location, never as a converged stress and never as a pass. The system SHALL offer
the reading that the method supports instead: stress at a declared distance from the
feature, or the linearized membrane and bending stress through a declared section, each
labeled with how it was read.

#### Scenario: A sharp inside corner

- **WHEN** peak stress at a sharp inside corner rises 18% then 21% across two refinements
- **THEN** the entry reports a singularity at the corner's tag and does not pass, and names
  the fillet radius or the read-off distance that would make it a stress

### Requirement: FEA and hand checks are compared where both apply

The card SHALL report both values and their ratio where a T1 check and a T3 result screen
the same quantity at the same location (a cantilever's root stress, a plate's
net-section stress, a thick cylinder's bore stress). A disagreement beyond a stated band SHALL be
a warning naming both values, so that an idealization error in either is visible.

#### Scenario: Beam theory and the mesh disagree

- **WHEN** a cantilever's T1 root stress is 120 MPa and its converged T3 stress at the root
  tag is 205 MPa
- **THEN** the card carries a warning naming both values and the ratio

### Requirement: The pipeline is verified against published benchmarks

The FEA tier SHALL be regression-tested on every solver or mesher version change against
benchmarks whose target values are re-derived from public reproductions, never
redistributed: at least one plane-stress concentration benchmark, one 3D solid
benchmark, one steady-state thermal benchmark and one thermal-stress benchmark, plus
closed-form cases the T1 library already holds (cantilever, thick cylinder, plate with a
hole). A result outside its stated tolerance SHALL block the version change.

#### Scenario: A solver bump that moves a result

- **WHEN** a new CalculiX version is proposed and the elliptic-membrane benchmark (target
  92.7 MPa) moves outside its tolerance
- **THEN** the version change is blocked, naming the benchmark, the target and the value

### Requirement: FEA results are pictures and files, and runs are tasks

An FEA run SHALL produce a rendered contour picture of the governing field with the peak
located and labeled, written to the output folder and returned to the agent as an image;
the deck, mesh and result files SHALL be written beside it and named in the result. A run
that can exceed the synchronous tool budget SHALL execute as a cancellable task reporting
mesh, solve and convergence progress. Results SHALL be cached by the content digest of the
model, load cases and toolchain versions, and a cached result SHALL be reported as such.

#### Scenario: The agent sees where it fails

- **WHEN** a housing's FEA fails on stress
- **THEN** the agent receives a contour picture with the peak marked at its tag, and the
  engineer finds the same picture and the result file in the output folder

#### Scenario: A repeated run costs nothing

- **WHEN** the same product and load cases are solved again with the same versions
- **THEN** the cached result is returned and labeled cached, with no solver process started
