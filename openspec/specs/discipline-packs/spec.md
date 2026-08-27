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

### Requirement: Timber pack

The timber pack SHALL provide, when shipped: the NDS adjustment-factor chain computed as a typed, itemized product (load duration, wet service, temperature, beam stability, size, flat use, incising, repetitive member, and column stability factors as applicable), and member screens for bending, shear, compression with column stability, bearing, and combined bending plus axial loading — each check citing its NDS section and edition; reference design values SHALL be user-supplied with provenance (the NDS Supplement's values are never bundled), and every applied adjustment factor SHALL be individually visible in the result with its governing condition stated.

#### Scenario: Factor chain is itemized, never a lump

- **WHEN** a bending screen runs on a member with wet service and a snow-governed load duration declared
- **THEN** the result lists each applied factor with its value and triggering condition, the adjusted design value, and the demand comparison, with sections cited

#### Scenario: Reference values are user-supplied

- **WHEN** a user declares a sawn-lumber member without supplying reference design values
- **THEN** the screen reports not evaluated naming the missing values, and accepts them as user-provenance inputs when supplied

#### Scenario: Column stability computed, not assumed

- **WHEN** a compression member is screened with slenderness requiring the column stability factor
- **THEN** the factor is computed per the cited section from the member's declared geometry and modulus, and the screen fails members exceeding the slenderness limit rather than extrapolating

### Requirement: Process piping pack

The process piping pack SHALL provide, when shipped: pressure-design wall-thickness screening for straight pipe (ASME B31.3 §304.1.2 including mill tolerance and corrosion allowance), branch-connection reinforcement area screening, miter-bend pressure screening, and displacement-stress-range screening against the computed allowable range — each check citing its B31.3 paragraph and edition; allowable stresses SHALL be user-supplied with provenance (the code's stress tables are never bundled), while standard pipe dimensions (B36.10M/B36.19M schedules) resolve from the bundled standards database with citations.

#### Scenario: Wall thickness with user-supplied allowable

- **WHEN** a user requests a wall-thickness screen for NPS 4 Schedule 40 pipe at a stated design pressure and temperature, supplying the allowable stress for their material at that temperature
- **THEN** the pack resolves the schedule dimensions from the standards database, computes required thickness per the cited paragraph including mill tolerance and corrosion allowance, and reports pass/fail with the allowable marked user-supplied

#### Scenario: Missing allowable never guessed

- **WHEN** a piping check runs without an allowable stress supplied
- **THEN** the check reports not evaluated with the required input named, rather than substituting a remembered or estimated value

#### Scenario: Branch reinforcement screened

- **WHEN** a branch connection is declared with run and branch sizes, thicknesses, and the user-supplied allowables
- **THEN** the reinforcement-area check reports required versus available area with each term traceable and the paragraph cited

### Requirement: Cold-formed steel pack

The cold-formed steel pack SHALL provide, when shipped: Direct Strength Method member screens for compression and flexure covering local, distortional, and global limit states per the cited AISI S100 sections and edition; elastic buckling loads and moments SHALL be typed inputs with declared provenance — user-supplied or computed by an external finite-strip tool whose identity and version are recorded — and the pack MUST NOT estimate buckling values internally; the governing limit state SHALL be identified in every result.

#### Scenario: DSM column screened from finite-strip inputs

- **WHEN** a lipped-channel column is screened with elastic buckling values computed by an external finite-strip tool and supplied with tool provenance
- **THEN** the compression screens report local, distortional, and global strengths per the cited sections, identify the governing limit state, and record the buckling-value provenance

#### Scenario: Buckling values never invented

- **WHEN** a DSM screen runs without elastic buckling inputs
- **THEN** the check reports not evaluated naming the missing inputs and the accepted sources (user-supplied or a supported external tool), rather than approximating

#### Scenario: Prequalification boundary stated

- **WHEN** a screened section falls outside the method's prequalified geometric limits declared to the check
- **THEN** the result carries a warning naming the exceeded limit, and the report states the applicable resistance-factor consequence per the cited section

### Requirement: Below-the-hook lifting device pack

The system SHALL provide, when shipped, an optional below-the-hook lifting device pack
that designs and checks BTH-1-class lifters as typed devices: Design Category (A or B)
and Service Class (0–4) SHALL be typed spec inputs that resolve the nominal design factor
and fatigue-evaluation obligation with the governing clause cited; member checks
(tension, compression, bending, combined stress, and stability) SHALL be evaluated in
BTH-1 allowable-stress form; pin-connected plate checks SHALL compose the existing lug
limit states under BTH-1 design factors rather than duplicating them; and every check
SHALL cite its BTH-1 clause. Rated load, Design Category, and Service Class SHALL appear
in the evidence bundle and any generated drawing title block, because BTH-1 lifters must
be marked with them.

#### Scenario: Design category resolves the design factor

- **WHEN** a spreader beam is specified as Design Category B, Service Class 2
- **THEN** all strength checks apply the Category B design factor with the clause cited,
  and the scorecard states the category, class, and factor used

#### Scenario: Lug checks reuse the existing limit states

- **WHEN** the lifter's pin-connected plates are checked
- **THEN** the pack evaluates the already-specified lug limit states (net-section
  tension, shear-out, bearing, pin shear, weld) with BTH-1 design factors and citations,
  and does not report a second, conflicting set of lug results

#### Scenario: Service class gates fatigue

- **WHEN** the device's Service Class requires fatigue evaluation
- **THEN** a fatigue screen runs against the declared load cycles, and if the stress
  category or cycle data needed is not declared, the fatigue check reports "not
  evaluated" naming the missing input — never a silent pass

#### Scenario: Rated load travels to artifacts

- **WHEN** a validated lifter is exported
- **THEN** the rated load, Design Category, and Service Class appear in the evidence
  bundle and in the drawing title block fields designated for them

### Requirement: Pressure equipment pack

The pressure equipment pack SHALL provide, when shipped: required-thickness and MAWP screening for ellipsoidal and torispherical formed heads and conical sections, nozzle-opening reinforcement area screening per the UG-37 area-replacement method, and bolted-flange screening per Appendix 2 (bolt loads, gasket seating and operating conditions, flange stresses) composing the existing gasket m/y factors — each check citing its ASME VIII Division 1 paragraph and edition, with allowable stresses user-supplied with provenance and never bundled.

#### Scenario: Head thickness screened

- **WHEN** a 2:1 ellipsoidal head is declared with design pressure, diameter, joint efficiency, and a user-supplied allowable stress
- **THEN** the required thickness and MAWP are reported per the cited paragraph, with pass/fail against the declared nominal thickness

#### Scenario: Nozzle opening reinforced

- **WHEN** a nozzle is declared on a shell with sizes, thicknesses, and allowables supplied
- **THEN** the UG-37 check reports required versus available reinforcement area, itemizing shell surplus, nozzle-wall contribution, and any reinforcing pad, each term traceable

#### Scenario: Flange screened to Appendix 2

- **WHEN** a bolted flange is declared with gasket factors from the existing gasket module and user-supplied allowables
- **THEN** seating and operating bolt loads and the flange stress checks report pass/fail with the Appendix 2 clause cited

### Requirement: Aluminum structural pack

The system SHALL provide, when shipped, an optional aluminum structural design pack with
ADM 2020 member screens — tensile yielding and rupture, local buckling resolved by
width-to-thickness slenderness class, member buckling, lateral-torsional buckling, and
combined loading interaction — each citing its ADM clause. Buckling constants SHALL be
computed from the ADM's cited formulas as functions of the alloy-temper properties, never
looked up from bundled reproductions of the standard's tables. Weld-affected-zone
reductions SHALL be first-class: when any part of a checked member is declared
weld-affected, the check SHALL evaluate with the reduced properties, state both the
parent and weld-affected values used, and identify which governed; a member with declared
welds whose weld-affected properties are not supplied SHALL report "not evaluated" naming
the missing values. Alloy-temper mechanical properties follow the user-supplied
allowables doctrine with provenance recorded.

#### Scenario: Governing limit state named

- **WHEN** a 6061-T6 rectangular-tube beam is screened under bending
- **THEN** yielding, local buckling, and lateral-torsional buckling are each evaluated
  with clauses cited, and the scorecard names the governing limit state and its margin

#### Scenario: Welded member uses reduced properties

- **WHEN** a member is declared welded within the checked region and weld-affected
  properties are supplied
- **THEN** the check evaluates with the weld-affected values, reports both property sets,
  and flags that the weld-affected zone governed if it did

#### Scenario: Missing weld-affected data is honest

- **WHEN** a member is declared welded but only parent-metal properties are supplied
- **THEN** affected checks report "not evaluated" naming the weld-affected properties
  required — never a check computed silently on parent-metal strength

#### Scenario: Buckling constants are computed, not recalled

- **WHEN** any buckling check runs
- **THEN** its buckling constants derive from the cited ADM formulas evaluated on the
  supplied properties, and the formula citation appears in the check provenance

