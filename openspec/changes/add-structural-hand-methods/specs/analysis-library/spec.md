# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Preloaded joints are screened with preload scatter and loss

A preloaded-joint screen SHALL compute maximum and minimum preload from the nominal
preload, the tightening method's scatter, short-term relaxation, and declared creep and
thermal losses. It SHALL check separation, slip, and bolt yield and ultimate under the
bound fitting factor, citing NASA-STD-5020B. A default scatter from the standard SHALL be
labeled as such.

#### Scenario: Torque-controlled, unlubricated

- **WHEN** a joint declares torque control on dry threads and no measured scatter
- **THEN** the screen uses the standard's default scatter, labels it a default, and
  checks separation at minimum preload

#### Scenario: Separation before rupture

- **WHEN** a joint's separation load exceeds the bolt's ultimate load
- **THEN** the screen reports that the bolt fails before the joint separates, naming both
  loads

### Requirement: Lugs are screened for axial, transverse and oblique load

A lug screen SHALL compute net-section, shear-bearing and transverse capacity, combine an
oblique load by the interaction rule, and check bushing bearing where a bushing is
declared. Its design curves SHALL be taken only from public-domain sources, each cited.
A lug geometry outside a curve's published range SHALL be not evaluated.

#### Scenario: An oblique load at 45 degrees

- **WHEN** a lug carries a load 45 degrees from its axis
- **THEN** the screen reports axial and transverse ratios and their interaction, citing
  the method

#### Scenario: Outside the curves

- **WHEN** a lug's edge-distance ratio lies outside the published curve range
- **THEN** the screen is not evaluated, naming the ratio and the range

### Requirement: Crippling and buckling include plasticity

The library SHALL screen formed and extruded sections for crippling by element, and SHALL
correct column and plate buckling for plasticity with the tangent or secant modulus from
the material's stress-strain description. A thin-walled cylinder SHALL use the knockdown
factor of its cited source. Where no stress-strain description exists, the plastic
correction SHALL be not evaluated.

#### Scenario: A short stiffener

- **WHEN** a short Z-stiffener's elastic buckling stress exceeds its proportional limit
- **THEN** the screen reports the plasticity-corrected stress and the crippling stress,
  and the governing one

### Requirement: Fastener groups distribute load by stiffness and check interaction

A fastener-group screen SHALL distribute shear by fastener and sheet stiffness where they
differ. It SHALL check each fastener's combined shear and tension by a cited interaction
rule, and check sheet pull-through against a declared head or nut bearing.

#### Scenario: Mixed fastener sizes

- **WHEN** a splice uses two larger and two smaller fasteners
- **THEN** the larger fasteners carry the larger share in proportion to stiffness, and
  each fastener's interaction ratio is reported

### Requirement: Laminates are screened by lamination theory

A laminate screen SHALL build the ABD matrix from declared plies and lamina records,
compute ply stresses and strains under declared running loads, and report first-ply
failure by maximum stress, maximum strain and Tsai-Wu, naming the governing ply and
criterion. The strength basis SHALL be stated on every entry.

#### Scenario: A quasi-isotropic plate in tension

- **WHEN** a [0/45/-45/90]s laminate carries a running load
- **THEN** the screen reports each ply's stresses, the first ply to fail and the
  criterion that governs

### Requirement: Sandwich panels are screened for their local modes

A sandwich screen SHALL check face wrinkling, intracell dimpling, core shear, and insert
pull-out against a declared insert allowable, each with its cited formula. A mode whose
input the panel does not declare SHALL be not evaluated.

#### Scenario: Thin faces on a coarse core

- **WHEN** a panel's face is thin relative to its core cell size
- **THEN** intracell dimpling is reported as the governing mode

### Requirement: Random vibration is screened from a declared input

A random-vibration screen SHALL integrate a declared input PSD to Grms, estimate response
by Miles' equation at a declared natural frequency and Q, and report a 3σ peak. It SHALL
combine the peak with quasi-static load factors by the declared rule, and state that
Miles' equation assumes a single-degree-of-freedom response.

#### Scenario: A box on a launch profile

- **WHEN** a 100 Hz box with Q of 10 is screened on a declared input PSD
- **THEN** the screen reports the input Grms, the response Grms, the 3σ load, and the
  single-degree-of-freedom assumption

### Requirement: Fracture-control classification is a candidate, never a ruling

A fracture-control helper SHALL check a part against the conditions a public
fracture-control standard gives for non-fracture-critical classification, each condition
cited. It SHALL report the result as a candidate classification. An engineer's
acceptance, with name and date, SHALL be required before any surface shows it as a
classification.

#### Scenario: A candidate awaiting acceptance

- **WHEN** a bracket meets every listed condition
- **THEN** it is shown as a candidate for non-fracture-critical classification until an
  engineer records acceptance
