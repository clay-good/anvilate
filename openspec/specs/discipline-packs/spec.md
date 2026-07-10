# Discipline Packs Specification

## Purpose

Discipline packs extend Anvilate beyond mechanical parts to the adjacent engineers who share the same unmet need — structural/civil and industrial/manufacturing engineers — without complicating the core product. A pack bundles part archetypes, standards data, code-based checks, and docs behind the existing pipeline contracts; enabling one adds a discipline, disabling one leaves zero trace in the UI. The wedge: artifacts that are small, parametric, prescribed by codes, repeated constantly, and served today by expensive black-box tools or fragile spreadsheets.
## Requirements
### Requirement: Discipline pack contract

A discipline pack SHALL bundle: pattern archetypes meeting the pattern-library contribution contract, standards-database records with provenance, discipline check sets returning standard scorecard records, process/DFM profiles, a default unit system, sample specs, and user documentation; packs MUST plug into the existing tiers and gates and MUST NOT bypass validation, export gating, or sandboxing.

#### Scenario: Pack parts flow through the same gauntlet

- **WHEN** a part from an enabled discipline pack is built
- **THEN** it runs the same T0–T3 tiers, produces a standard scorecard, and is export-gated exactly like a core mechanical part

#### Scenario: Incomplete pack rejected

- **WHEN** a pack is submitted missing check citations, golden-file tests, or documentation
- **THEN** CI rejects it with the missing contract items enumerated

### Requirement: Code checks cite their source clause

Every discipline code check SHALL cite the governing standard, edition, and clause (e.g., "AISC 360-22 §J8") in its scorecard record and documentation page, and results SHALL carry the screening label with engineering sign-off remaining with the engineer of record.

#### Scenario: Traceable base-plate check

- **WHEN** a concrete bearing check runs on a base plate
- **THEN** the scorecard entry names the standard edition and clause the check implements, and the rendered report carries the screening disclaimer

#### Scenario: Edition is pinned

- **WHEN** a code check's underlying standard has multiple editions
- **THEN** the check declares which edition it implements, and the evidence bundle records it

### Requirement: Structural steel pack

The structural pack SHALL provide, when shipped: column base plate with anchor-rod layout, gusset plate, shear/connection plate, and lifting lug archetypes, with check sets implementing the governing US code provisions (AISC 360 limit states; ACI 318 anchoring provisions for concrete breakout/pullout; ASME BTH-1 lug limit states — net-section tension, shear-out, bearing, pin shear, weld); Eurocode (EN 1993-1-8) check sets SHALL follow the same contract when shipped.

#### Scenario: Lifting lug in minutes, not hours

- **WHEN** a user requests "lifting lug for a 5 ton vertical pick, A36 plate, 1 inch pin"
- **THEN** the pack generates the lug, runs the BTH-1-class limit-state checks with each result cited, and offers DXF, STEP, and a dimensioned drawing on pass

#### Scenario: Base plate to fabrication drawing

- **WHEN** a user requests a base plate for a stated column, axial load, and concrete strength
- **THEN** the compiled spec resolves the column section from the section library, checks bearing and plate bending per the cited provisions, checks anchorage per the cited concrete provisions, and exports a dimensioned drawing with the anchor layout

### Requirement: License-clean steel section library

The section library SHALL store public dimensional geometry only and compute section properties from geometry at build time; license-restricted compilations (e.g., the AISC shapes database) MUST be fetched to the user's machine on first use with consent and checksum verification, cached locally, and never redistributed in Anvilate releases.

#### Scenario: W-shape resolves offline after first fetch

- **WHEN** a spec references "W12x26" after the user has accepted the one-time section-data fetch
- **THEN** the section resolves with zero network calls, its properties computed from stored geometry, with fetch provenance recorded

#### Scenario: No fetch, no guess

- **WHEN** a referenced section's dataset has not been fetched and the machine is air-gapped
- **THEN** the system asks for the governing dimensions or a local data file instead of estimating, and records user provenance

### Requirement: Industrial fixtures pack

The industrial pack SHALL provide, when shipped: fixture/subplate archetypes with dowel-and-tap hole grids using standard fits, machine-guard panel archetypes parameterized by the safety-distance and guard-construction standards (ISO 13857 reach tables, ISO 14120), and robot end-effector adapter plates on standard flange patterns (ISO 9409-1), each check citing its table or clause.

#### Scenario: Guard opening from the standard's table

- **WHEN** a user requests "guard panel, hazard 200 mm behind it"
- **THEN** the maximum permissible mesh opening is resolved from the encoded ISO 13857 table with its citation, and a larger requested opening fails validation with the table row cited

#### Scenario: Fixture plate grid

- **WHEN** a user requests a fixture subplate with a 25 mm dowel-and-tap grid
- **THEN** the pattern generates the grid with dowel holes at the standard press-fit tolerance and tapped holes called out per the standards database

### Requirement: Packs are optional, lazily loaded, and invisible when disabled

Discipline packs SHALL be individually enable-able, add nothing to install size requirements of the core beyond their own data, and contribute no UI vocabulary, patterns, samples, or checks while disabled; the core mechanical experience MUST remain unchanged when no pack is enabled.

#### Scenario: Mechanical user never sees structural jargon

- **WHEN** a user with no packs enabled uses the workbench
- **THEN** no structural or industrial pack terms, samples, or check categories appear anywhere in the UI

#### Scenario: Enabling a pack is one action

- **WHEN** a user enables the structural pack
- **THEN** its samples appear in the gallery, its archetypes become available to compilation, and its unit default (US customary) is offered for new specs

### Requirement: Column screens use the least radius of gyration

Structural-pack buckling screens (columns and the axial term of beam-columns) SHALL compute slenderness from the least radius of gyration the declared cross-section carries, falling back to the bending-axis value only when the section records no transverse second moment; the flexural term of a beam-column SHALL continue to use the declared bending axis.

#### Scenario: Strong-axis declaration cannot inflate buckling capacity

- **WHEN** a column member is declared with a section whose bending axis is
  its strong axis (both second moments present)
- **THEN** the buckling screen computes slenderness from the weak-axis radius
  of gyration, and the scorecard reflects the weaker — governing — axis

#### Scenario: Hand-built sections keep the explicit contract

- **WHEN** a column member declares a `CrossSection` that carries no
  transverse second moment
- **THEN** the screen uses the bending-axis radius of gyration, as today, and
  the member documentation states the caller owns the weak-axis choice

