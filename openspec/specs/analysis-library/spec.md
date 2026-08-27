# analysis-library Specification

## Purpose
The closed-form screening checks themselves: the T1 analytical layer every discipline pack draws on. Its rules are about evidence rather than physics — every public symbol names the handbook or clause it comes from, every argument and return is a dimension-checked quantity, every module carries a runnable example, and a check with a design inverse ships the inverse beside it so a failing verdict can say what would fix it. The worked-example anchors are the regression floor: numbers taken from a published source and pinned, so a refactor that changes an answer fails rather than quietly moving a margin.

## Requirements
### Requirement: Every check cites its source

Every analysis function that produces an engineering verdict or sized quantity SHALL carry a citation — handbook (author, title, edition, section) or standard (designation, edition, clause) — and that citation SHALL travel with the result into scorecards, evidence, and reports; a function without a citation MUST NOT ship in the public API.

#### Scenario: Citation travels to the scorecard

- **WHEN** a sheave-bending screen contributes to a scorecard
- **THEN** the entry carries the citation the function declares, without the caller re-supplying it

#### Scenario: Uncited function rejected

- **WHEN** a new public analysis function is submitted without a citation
- **THEN** CI rejects it naming the function

### Requirement: Unit-typed API surface

Public analysis functions SHALL accept and return unit-carrying quantities only; raw floats for physical quantities are prohibited in the public API, and dimensional mismatches SHALL be rejected at call time naming the parameter and expected dimension.

#### Scenario: Wrong dimension rejected at the boundary

- **WHEN** a caller passes a force where a stress is expected
- **THEN** the call fails immediately naming the parameter, received dimension, and expected dimension

### Requirement: Worked-example regression anchoring

Every analysis function SHALL be tested against at least one published worked example (Roark/Shigley/AISC/ASME-class) reproducing the source's result within a stated tolerance, with the source identified in the test; refactors that drift a worked-example result SHALL fail CI.

#### Scenario: Textbook anchor holds

- **WHEN** the test suite runs
- **THEN** each function reproduces its cited worked example within tolerance, and a numerical drift fails the build naming the function and source

### Requirement: Design inverses pair with forward checks

Where the library provides a design inverse (solve for the dimension, count, or rating that satisfies a check), the inverse SHALL be paired with its forward check and round-trip tested: the inverse's output, fed to the forward check, satisfies the required margin at the declared tolerance; inverses SHALL be discoverable from their forward checks for repair-hint binding.

#### Scenario: Round trip closes

- **WHEN** the bearing-rating inverse computes the dynamic rating for a target life
- **THEN** the forward life check at that rating meets the target within the declared tolerance, verified in CI

### Requirement: Runnable example per module

Every analysis module SHALL ship at least one runnable example that demonstrates an engineering decision (not just an API call) — a governing check identified, a trade-off surfaced, or a failure caught — executed in CI so examples cannot rot.

#### Scenario: Example teaches a decision

- **WHEN** a new analysis module merges
- **THEN** it includes a CI-executed example whose output shows a scorecard verdict a practicing engineer would act on

### Requirement: Public API stability

The public analysis surface SHALL follow semantic versioning: breaking changes only at major versions, deprecations announced with a documented replacement and retained for at least one minor release with a warning; the public surface SHALL be explicitly enumerated so additions are deliberate.

#### Scenario: Deprecation is survivable

- **WHEN** a public function is renamed
- **THEN** the old name keeps working with a deprecation warning naming the replacement for at least one minor release before removal

### Requirement: User-supplied allowables doctrine

Where a check's governing values come from copyrighted compilations (code allowable-stress tables, reference design values, proprietary coefficients), the library SHALL accept them as user-supplied inputs carrying user provenance, cite the clause that consumes them, and MUST NOT bundle the copyrighted values; results SHALL state that the allowable was user-supplied.

#### Scenario: Copyrighted table never bundled

- **WHEN** a check requires an allowable stress published only in a copyrighted table
- **THEN** the function takes the allowable as a parameter, the result records user provenance for it, and no bundled data ships the table's values

#### Scenario: Provenance in the report

- **WHEN** a scorecard entry used a user-supplied allowable
- **THEN** the rendered report marks that value as user-supplied alongside the clause citation

### Requirement: Weld fatigue screening from a declared detail category

The analysis library SHALL provide nominal-stress weld fatigue screening in which the
detail category is a typed user-supplied input carrying the standard, edition, and
detail description it came from; the library MUST NOT infer a detail category from
geometry, and a check without a declared category SHALL report "not evaluated." From the
declared category the library SHALL construct the standardized S-N curve using cited
slope, constant-amplitude limit, and cutoff conventions, apply thickness/size and
mean-stress corrections only when their inputs are declared, and report every applied
correction with its factor and citation. Cumulative damage over a declared stress-range
spectrum SHALL compose the existing linear-damage summation, and an allowable-cycles (or
allowable stress range for a target life) design inverse SHALL pair with the forward
check per the library contract.

#### Scenario: Category drives a cited curve

- **WHEN** a user declares a detail category with its source and a constant-amplitude
  stress range and cycle count
- **THEN** the check reports the damage fraction, the constructed curve's slopes and knee
  points with citations, and the declared category's source in provenance

#### Scenario: No category, no verdict

- **WHEN** a welded joint is checked without a declared detail category
- **THEN** the check reports "not evaluated" naming the missing category — the library
  never selects one from the joint geometry

#### Scenario: Corrections are visible

- **WHEN** plate thickness exceeds the reference thickness and a thickness correction
  applies
- **THEN** the result states the correction factor, its citation, and the corrected
  category value alongside the declared one

#### Scenario: Spectrum damage and inverse agree

- **WHEN** a variable-amplitude spectrum yields a damage fraction below 1.0 and the
  allowable-cycles inverse is queried for the same detail and stress range
- **THEN** the forward and inverse results are mutually consistent under the library's
  round-trip requirement

### Requirement: Member-force ingestion from external analysis

The library SHALL accept typed member-force records — axial force, shears, moments, and torsion at member stations, with units — produced by external structural-analysis tools (Pynite-class), and feed them to the existing cited member checks; results SHALL carry provenance identifying the external tool, its version, and the load case or combination the forces came from.

#### Scenario: Pynite forces through AISC checks

- **WHEN** a user supplies member end forces computed by an external frame analysis for a declared section and length
- **THEN** the existing beam, column, and beam-column screens run with those demands and each scorecard entry cites its clause and records the external-analysis provenance

#### Scenario: Verdict states its demand source

- **WHEN** a check consuming external forces is rendered in a report
- **THEN** the report states that demands came from the named external analysis, not from Anvilate's own load derivation

### Requirement: Section-property ingestion

The library SHALL accept externally computed cross-section constants (area, second moments, torsion constant, section moduli, warping constant where relevant) as typed CrossSection inputs with source provenance, including an optional-dependency adapter for sectionproperties-class engines; ingested constants SHALL be dimensionally validated before use.

#### Scenario: Arbitrary section screened

- **WHEN** a user computes constants for a custom welded section with an external section engine and supplies them
- **THEN** beam and torsion checks accept the section with the engine and version recorded as the property source

#### Scenario: Adapter is optional

- **WHEN** the optional section-engine dependency is absent
- **THEN** manual typed entry of constants works identically, and nothing else in the library degrades

### Requirement: No silent conventions on imported analysis data

Ingestion of external forces and section properties SHALL require explicit declaration of the source's axis convention and unit system; the mapping to Anvilate's conventions SHALL be validated, and a record whose convention is undeclared or inconsistent MUST be rejected rather than assumed.

#### Scenario: Undeclared axes rejected

- **WHEN** a member-force record arrives without an axis-convention declaration
- **THEN** ingestion fails naming the missing declaration, and no check runs on assumed axes

#### Scenario: Strong/weak axis mix-up caught

- **WHEN** a declared convention maps the section's transverse moment to the bending axis inconsistently with the record's own labels
- **THEN** ingestion fails with the conflict described, rather than screening about the wrong axis

### Requirement: Fracture screening set — SIF solutions, reference stress, FAD placement

The analysis library SHALL provide a fracture screening set under the library contract:
(a) named handbook stress intensity factor solutions (at minimum through-wall,
semi-elliptical surface, and embedded flaw geometries in plates and cylinders) each
citing its open-literature source and enforcing its stated geometric validity ranges —
out-of-range inputs report "not evaluated," never extrapolated; (b) reference-stress
plastic-collapse solutions for the same geometries; (c) failure assessment diagram
placement computing the assessment point (Kr, Lr) against the cited open-literature
Level-2-class FAD curve, with the verdict expressed as margin along the load line and
the cutoff Lr,max derived from the supplied material properties. Fracture toughness
SHALL be user-supplied with provenance; a Charpy-correlated toughness estimate MAY be
offered only with the correlation cited and the result labeled an estimate, consistent
with the derived-fatigue-parameter doctrine. Results SHALL carry the screening label and
a statement that flaw assessment dispositions require a qualified assessor; the library
MUST NOT reproduce API 579 Level-1 screening figures or exemption curves.

#### Scenario: Assessment point placed with margin

- **WHEN** a semi-elliptical surface flaw in a cylinder is assessed with user-supplied
  toughness and yield/tensile properties under a declared membrane stress
- **THEN** the result reports Kr, Lr, the FAD curve citation, the margin along the load
  line to the curve, and which failure mode (fracture-dominated, collapse-dominated, or
  interactive) the point sits in

#### Scenario: Validity range enforced

- **WHEN** a flaw's depth-to-thickness ratio falls outside the cited SIF solution's
  stated range
- **THEN** the check reports "not evaluated" naming the violated range — never an
  extrapolated K

#### Scenario: Estimated toughness is labeled

- **WHEN** toughness is derived from user-supplied Charpy energy via a cited correlation
- **THEN** the result carries the correlation citation and an estimate label, and the
  evidence bundle distinguishes it from directly supplied toughness

#### Scenario: Screening framing is non-negotiable

- **WHEN** any fracture screening result is rendered in a scorecard or report
- **THEN** it states the screening label and the qualified-assessor requirement, and no
  output phrase asserts fitness for continued service

### Requirement: Thermal screening set

The library SHALL provide cited closed-form thermal screening: series/parallel thermal resistance networks (conduction, contact, convection, spreading), fin efficiency and fin-array heatsink sizing, natural- and forced-convection correlations with their validity ranges declared and enforced, and junction- or surface-temperature margin checks against user-declared limits; every correlation SHALL cite its source (Incropera-class heat transfer references or handbook data), and an input outside a correlation's declared validity range SHALL report not evaluated with the violated range named — never a silently extrapolated coefficient.

#### Scenario: Heatsink margin screened

- **WHEN** a user declares a heat source, an ambient temperature, a finned heatsink geometry, and a junction-temperature limit
- **THEN** the screen composes the resistance network, reports the predicted junction temperature against the limit with the margin, and cites each correlation used

#### Scenario: Out-of-range correlation refuses

- **WHEN** a natural-convection correlation receives a Rayleigh number outside its cited validity range
- **THEN** the check reports not evaluated naming the correlation, its range, and the computed value, rather than extrapolating

### Requirement: Vibration isolation and shock screening set

The library SHALL provide cited closed-form isolation and shock screening: transmissibility as a function of frequency ratio and damping with an isolation-effectiveness margin check, isolator selection screening composing the existing static-deflection inverse, and base-excitation half-sine shock response screening (peak response versus pulse duration and system frequency) against user-declared fragility limits; each check SHALL cite its source and follow the two-sided reporting pattern where amplification regions are flagged, not just insufficient isolation.

#### Scenario: Isolator actually isolates

- **WHEN** a user declares a machine mass, excitation frequency, and target transmissibility, and selects an isolator stiffness
- **THEN** the screen reports the frequency ratio, transmissibility, and margin against the target, citing the source, and fails isolators operating in the amplification region with that condition named

#### Scenario: Shock screening against fragility

- **WHEN** a half-sine shock input (peak, duration) and an equipment fragility limit are declared
- **THEN** the screen reports the predicted peak response against the fragility limit with the governing regime (impulsive, quasi-static, or resonant amplification) identified and cited

