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

The bundle's rendered form SHALL name **each check individually**, with its detail and the clause it cites, rather than a count of how many ran. A roll-up over layers is a legitimate document — the attestation predicate carries one — but it is not the document handed to a reviewer, and a surface that emits it under the name "evidence bundle" is emitting a verdict rather than evidence.

The bundle SHALL carry the **spec its verdicts were computed from**, in a form the tool's own front door reads back: a reviewer holding the bundle and nothing else SHALL be able to recover the document, screen it, and obtain the same scorecard. A bundle carrying no spec SHALL say so in the document rather than omit the section, because a bundle that cannot be re-run and one whose author left the spec out must not read the same.

Where a surface receives a reference to a screening result rather than the documents themselves, that reference SHALL name the spec and the scorecard together. An arrangement under which the spec is supplied separately and optionally is non-conforming: it makes reproducibility a property of how a client was written rather than of the bundle.

#### Scenario: Reproducibility from the bundle

- **WHEN** a senior engineer receives only the evidence bundle and the Anvilate release named in it
- **THEN** they can re-run the identical analysis and obtain the same scorecard

#### Scenario: Screening label on the bundle

- **WHEN** any evidence bundle is generated
- **THEN** it carries the non-dismissable screening-analysis disclaimer and the list of modeling assumptions

#### Scenario: Every check is named, not counted

- **WHEN** a bundle is rendered for a card on which one check failed
- **THEN** the document names that check, its detail and its citation, so a reviewer can see which one failed and against what — rather than only that one of several did

#### Scenario: The rendered spec is readable by the tool that wrote it

- **WHEN** the spec is taken out of a rendered evidence bundle and given back to the tool
- **THEN** it parses, screens, and produces the scorecard the bundle reports — so the bundle does not describe the inputs, it is them

#### Scenario: A bundle with no spec says so

- **WHEN** a bundle is rendered for a screening result whose spec was not supplied
- **THEN** the document states that it carries no spec and cannot be reproduced from alone, rather than omitting the section

### Requirement: QIF results export

The export layer SHALL export a validated part's scorecard and evidence as a QIF Results document (ISO 23952): each check maps to a characteristic with its requirement (threshold and units), evaluated actual, pass/fail status, and traceability to the spec revision and toolchain versions; the export SHALL validate against the QIF schemas, and checks that were not evaluated SHALL be represented as unevaluated characteristics, never omitted.

#### Scenario: Quality software reads the verdicts

- **WHEN** a validated part's evidence is exported as QIF Results
- **THEN** standard QIF-conformant quality software can enumerate every check as a characteristic with its requirement, actual, and status, and the document validates against the published schemas

#### Scenario: Not-evaluated survives the mapping

- **WHEN** a scorecard containing not-evaluated checks is exported
- **THEN** those checks appear as unevaluated characteristics with their reason, preserving the no-silent-green property in the interchange format

