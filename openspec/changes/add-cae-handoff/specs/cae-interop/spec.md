# CAE Interop Specification

## Purpose

Analysis-ready input for the user's own FE solver, and the solver's interface loads read
back into Anvilate's cited hand methods.

## ADDED Requirements

### Requirement: A part or product exports as an analysis-ready deck

A built part or product SHALL export as a keyword-format deck (`.inp`) or a bulk-data deck
(`.bdf`). The deck SHALL hold the mesh with its element type and size, materials with
their sources as comments, and the declared supports and loads applied to tagged faces,
with one step or subcase per load case. Every load SHALL be traceable to its spec entry
by a comment.

#### Scenario: A bracket deck with two load cases

- **WHEN** a bracket with a fixed base and two declared tip load cases is exported as a
  bulk-data deck
- **THEN** the deck has two subcases, each load applied to the tagged tip face, and each
  load commented with its spec entry

### Requirement: Units are stated, never implied

Every deck SHALL state its consistent unit system in a header comment and in a sidecar
file. A deck SHALL be refused if any value cannot be expressed in the chosen system.
Imported results SHALL declare their unit system, and an import without one SHALL be
refused naming the file.

#### Scenario: A results file with no stated units

- **WHEN** an agent imports a result file and declares no unit system
- **THEN** the import is refused, naming the file and the systems it may declare

### Requirement: A deck is input, not evidence

An exported deck SHALL be marked in its header and in the evidence bundle as unsolved
input. No check SHALL report a result from the user's solver unless that result was read
back through an import that records the file hash, the solver and its version as
declared, and the load case.

#### Scenario: A solver run nobody imported

- **WHEN** an agent says a deck "passed" in the user's solver without importing results
- **THEN** no card entry changes, and the deck remains listed as unsolved input

### Requirement: Interface loads are read from result files per load case

The system SHALL read grid-point or free-body forces at a named interface from a result
file. Each import records the file hash, the load-case identity, the coordinate system,
and the summed force and moment at the interface. The read loads SHALL become load cases
on that connection. Results whose free body does not balance within a stated tolerance
SHALL be reported with the residual.

#### Scenario: Fitting loads for 400 cases

- **WHEN** an analyst imports interface forces at a wing fitting for 400 load cases
- **THEN** the fitting's connection holds 400 load cases, each traceable to its case
  identity and the file hash

#### Scenario: A free body that does not balance

- **WHEN** the forces cut at a bracket do not sum to equilibrium within tolerance
- **THEN** the import reports the residual force and moment, and the cases affected

### Requirement: Region results are cited inputs, not replacements

A peak stress, strain or displacement in a tagged region SHALL be importable as a cited
input to a check: the check reports its own verdict on that value, naming the file, case
and region. An imported value SHALL NOT replace a closed-form check that also runs, and
both SHALL be reported where they disagree by more than a stated tolerance.

#### Scenario: A solver and a hand calc disagree

- **WHEN** an imported peak bending stress is 40% above the closed-form estimate for the
  same section
- **THEN** both entries are reported, and the disagreement is named as a finding
