# Artifact Export Specification

## Purpose

The export layer turns a validated part into the artifacts engineers actually consume: STEP AP242 with embedded validation properties and semantic PMI, dimensioned 2D drawings, STL/3MF for printing, URDF for robotics, the generating source code, and the evidence bundle. Export is gated on validation; nothing unvalidated leaves the tool unmarked.

## Requirements

### Requirement: Validation-gated export

Export of CAD artifacts SHALL be enabled only when the part's acceptance checks pass; the user MAY explicitly export an unvalidated part, in which case the exported file metadata and evidence bundle MUST be watermarked as unvalidated.

#### Scenario: Green part exports

- **WHEN** all acceptance-tier checks pass
- **THEN** the export menu is enabled for all formats

#### Scenario: Override is watermarked

- **WHEN** the user invokes "export unvalidated"
- **THEN** the STEP header metadata, drawing title block, and evidence bundle each carry an explicit unvalidated watermark

### Requirement: STEP AP242 with validation properties

The primary CAD export SHALL be STEP AP242 (with an AP214 fallback flag) and MUST embed geometric validation properties — volume, surface area, centroid — so receiving CAD systems can verify import integrity; property write-out SHALL follow the published CAx/MBx interoperability recommended practices.

#### Scenario: Receiving CAD verifies integrity

- **WHEN** an exported STEP is imported into a target CAD system
- **THEN** the embedded volume, area, and centroid match the received geometry within the recommended-practice tolerances

#### Scenario: AP242 is the default schema

- **WHEN** a STEP file is written with default settings
- **THEN** the file declares the AP242 schema, and PMI/validation-property content is not silently dropped by a legacy schema default

### Requirement: Semantic PMI export

Where the spec defines toleranced features (thread callouts, critical dimensions, datum-bearing interfaces), the STEP export SHALL carry them as semantic PMI (machine-readable representation), and exported PMI SHALL be conformance-checked in CI with an independent STEP analyzer against the PMI recommended practices.

#### Scenario: Thread callout survives round-trip

- **WHEN** a part with an M5 threaded interface is exported and re-imported through the CI conformance checker
- **THEN** the thread specification is present as semantic PMI, not only as drawing text

### Requirement: Clean import across the CAD matrix

Exported STEP files MUST import without repair dialogs into the supported CAD matrix (CATIA V5/3DEXPERIENCE, SolidWorks, NX, Fusion, FreeCAD, Onshape); an automated import-regression matrix SHALL run in CI against the freely automatable tiers, with the proprietary tier verified on a documented recurring cadence.

#### Scenario: Regression on a kernel upgrade

- **WHEN** the geometry kernel version is bumped
- **THEN** the CI import matrix runs and any new import warning in any target blocks the release

### Requirement: Print and robotics exports

The export layer SHALL produce STL and 3MF with a printability re-check under the relevant additive DFM profile at export time, and URDF with mass and inertia tensors computed from the actual geometry and material density.

#### Scenario: URDF inertia from geometry

- **WHEN** a part is exported as URDF
- **THEN** the mass and inertia tensor are computed from the B-Rep and material density, not defaulted

#### Scenario: Print export re-checks printability

- **WHEN** a CNC-validated part is exported as STL for FDM
- **THEN** the additive DFM profile runs and any overhang/min-feature violations are surfaced before the file is written

### Requirement: Source and spec always exportable

The generating source code and the Design Spec SHALL always be exportable regardless of validation state, since they are the editable model, not a claimed-valid artifact.

#### Scenario: Source export while red

- **WHEN** a part has failing checks
- **THEN** the user can still save the spec and source files for offline editing

### Requirement: Evidence bundle

Every validated export SHALL include an evidence bundle (HTML, optionally PDF) containing: the spec, the scorecard with thresholds and measured values, FEA assumptions and stress-field imagery, mesh statistics and convergence history, material and standards data provenance, solver and kernel versions, the exact solver input decks, and the iteration history — sufficient for an independent engineer to reproduce the run.

#### Scenario: Reproducibility from the bundle

- **WHEN** a senior engineer receives only the evidence bundle and the Anvilate release named in it
- **THEN** they can re-run the identical analysis and obtain the same scorecard

#### Scenario: Screening label on the bundle

- **WHEN** any evidence bundle is generated
- **THEN** it carries the non-dismissable screening-analysis disclaimer and the list of modeling assumptions
