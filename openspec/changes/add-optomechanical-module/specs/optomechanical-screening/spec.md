# Opto-Mechanical Screening Specification (delta)

## ADDED Requirements

### Requirement: Scope is screening, and the boundary is stated

The opto-mechanical module SHALL screen the mechanical behavior of optical assemblies — 
thermal, dynamic, retention, sealing, and clearance — and SHALL NOT perform ray tracing,
diffraction propagation, or optical design optimization. Where a screen requires a
prescription or surface quantity the module does not compute — marginal ray height, field
angle, surface figure, a Zernike description of a deformed surface — that quantity SHALL
be a typed input supplied by the user with provenance or imported from an external tool
whose identity and version are recorded. The module MUST NOT estimate such a quantity
internally, and a screen lacking one SHALL report "not evaluated" naming the missing input
and the accepted sources.

#### Scenario: Missing prescription input is named, not guessed

- **WHEN** an obscuration screen runs without the beam envelope's defining angles supplied
- **THEN** the screen reports "not evaluated" naming the missing quantities and the
  accepted sources, rather than assuming a cone

#### Scenario: Imported optical data carries its tool

- **WHEN** surface deformation data produced by an external optical or finite-element tool
  is imported
- **THEN** the tool's identity and version are recorded in the result provenance and in
  the evidence bundle

#### Scenario: The module says what it is

- **WHEN** an opto-mechanical report is rendered
- **THEN** it states that the results are analytical screening, that optical performance
  prediction remains with the optical design tool, and that sign-off remains with the
  engineer of record

### Requirement: Environments are declared physically, never by application

Shock, vibration, and thermal environments SHALL be declared as physical quantities —
acceleration magnitude, pulse shape, duration, axis, cycle count, power spectral density,
temperature range, soak duration, rate of change — with an optional citation to the
severity's source, such as a published environmental test method. The module MUST NOT
carry application-specific environment presets, and every screen SHALL behave identically
regardless of what produced the environment.

#### Scenario: One arithmetic, many sources

- **WHEN** two specs declare the same half-sine pulse magnitude, duration, and axis
- **THEN** both produce identical screening results, and no result depends on what the
  user said the source was

#### Scenario: Severity cites its source when the user gives one

- **WHEN** a user declares an environment citing a published test method and severity
  level
- **THEN** the citation travels into the scorecard entry and the evidence bundle

#### Scenario: Undeclared environment is not assumed

- **WHEN** a thermal or dynamic screen is requested without a declared environment
- **THEN** the screen reports "not evaluated" naming the environment it requires, rather
  than applying a default severity

### Requirement: Athermal focus screening against depth of focus

The module SHALL screen focus stability over a declared temperature range by composing the
differential axial expansion of the housing, cell, and spacer materials with the
element's index change over temperature, and comparing the resulting focus shift against
the system's depth of focus computed from the declared f-number and wavelength or against
a user-declared allowance. The contributing terms SHALL be reported separately, and every
material property used SHALL be reported with the temperature range over which it was
declared valid.

#### Scenario: Focus shift is itemized

- **WHEN** an aluminum housing holding a glass element is screened over a declared range
- **THEN** the result reports the housing expansion term, the element terms, the index
  term, their combination, the depth of focus, and the verdict

#### Scenario: Property used outside its declared range is refused

- **WHEN** a screen runs at a temperature outside the range over which a material property
  was declared valid
- **THEN** the screen reports "not evaluated" naming the property and its declared range,
  rather than extrapolating

#### Scenario: Athermal candidate is reported as an inverse

- **WHEN** a focus screen fails
- **THEN** the result reports the housing coefficient of thermal expansion that would
  bring the shift within the depth of focus, holding the other declared terms fixed, or
  states that no value of it can — never a repair direction the declared geometry cannot
  reach

### Requirement: Line-of-sight stability under declared dynamic environments

The module SHALL screen angular line-of-sight stability by converting a declared dynamic
environment into an equivalent static acceleration, applying it to the declared element
mass at its declared mount compliance, and converting the resulting tilt and decenter into
an angular line-of-sight shift compared against a declared angular limit. For a classical
pulse the amplification basis SHALL be stated; for a random environment the narrow-band
equivalent SHALL state its basis and the sigma level used. The damping or quality factor
SHALL be a declared input — the module MUST NOT default it, because the result scales
directly with it.

#### Scenario: Amplification basis is never implicit

- **WHEN** a shock screen converts a half-sine pulse into an equivalent static load
- **THEN** the result states the amplification factor applied, the basis for it, and the
  ratio of pulse duration to the mount's fundamental period that justifies it

#### Scenario: Undeclared damping refuses the screen

- **WHEN** a dynamic screen is requested without a declared damping or quality factor
- **THEN** the screen reports "not evaluated" naming the missing input

#### Scenario: Angular result is angular

- **WHEN** a line-of-sight result is rendered
- **THEN** it is expressed in the reader's declared angular unit with the unit shown, and
  the tilt and decenter contributions are reported separately

### Requirement: Element retention preload and glass contact stress

The module SHALL screen the axial preload required to retain an optical element against a
declared acceleration, the contact stress that preload produces at the declared retention
interface geometry, and the change in preload across the declared temperature range. The
contact-stress screen SHALL compare against a user-supplied allowable tensile stress for
the element material with the statistical nature of glass strength stated in the result;
the module MUST NOT supply a glass strength value of its own. Loss of contact at the hot
or cold extreme SHALL fail, not warn.

#### Scenario: Preload window is two-sided

- **WHEN** a retention screen runs over a declared temperature range
- **THEN** the result reports the preload at ambient and at both extremes, fails on loss
  of contact at one extreme and on overstress at the other, and names which bound governs

#### Scenario: Glass allowable is user-supplied

- **WHEN** a contact-stress screen runs without a declared allowable tensile stress for
  the element material
- **THEN** it reports "not evaluated" naming the missing allowable

#### Scenario: Strength statistics are stated, not buried

- **WHEN** a glass contact-stress result is rendered
- **THEN** it states that glass strength is statistical and surface-condition dependent,
  and that the comparison is a screening one

### Requirement: Elastomeric and bonded mounts screen their athermal thickness

The module SHALL screen elastomeric and adhesive annular mounts for the bond thickness at
which radial expansion of the element, the elastomer, and the housing offset one another,
reporting the athermal thickness, the declared thickness, and the radial stress at the
declared temperature extremes. The elastomer's modulus and Poisson's ratio SHALL be
declared inputs with provenance; a screen missing either SHALL report "not evaluated"
naming it, because the athermal result depends strongly on the Poisson term.

#### Scenario: Athermal thickness reported beside the declared one

- **WHEN** a bonded mount is screened
- **THEN** the result reports the athermal thickness, the declared thickness, and the
  radial stress at both extremes

#### Scenario: Missing elastomer properties refuse the screen

- **WHEN** an elastomer's Poisson's ratio is not declared
- **THEN** the screen reports "not evaluated" naming it, rather than assuming an
  incompressible value

### Requirement: Beam envelope is a keepout and obscuration is screened against it

A declared optical beam envelope SHALL be emitted as a keepout envelope with its own
semantic tag and reason, so that mechanical intrusion into the optical path is caught by
the standard T0 intrusion check. In addition, the module SHALL screen the mechanical clear
aperture at each declared station against the beam footprint at that station, reporting
the obscuration as a fraction of the footprint with the station named.

#### Scenario: A rib in the beam path fails at T0

- **WHEN** a stiffening feature crosses the declared beam envelope
- **THEN** the standard intrusion check fails naming the feature and the envelope, with no
  optical computation required

#### Scenario: Aperture shortfall is quantified

- **WHEN** a mechanical aperture is smaller than the beam footprint at its station
- **THEN** the screen fails reporting the obscuration fraction and naming the station

#### Scenario: Zero obscuration is a measured result, not an absence

- **WHEN** a design is reported as unobstructed
- **THEN** the result states the stations screened and the smallest clearance found, so
  that "no obscuration" is distinguishable from "nothing was checked"

### Requirement: Wavefront error is an allocated budget, never an invented number

Where a spec declares a wavefront-error requirement, the module SHALL evaluate it as a
performance budget whose contributors are supplied or imported — surface figure,
mount-induced deformation, thermal gradient, assembly error — each with its source. The
module MUST NOT compute a wavefront error from mechanical quantities alone. The threshold
SHALL be declared; where the user declares a diffraction-limited criterion, the criterion
and its citation SHALL appear in the result.

#### Scenario: Budget refuses to run on missing contributors

- **WHEN** a wavefront budget is declared and a contributor's source produced no value
- **THEN** the budget reports "not evaluated" naming that contributor

#### Scenario: Criterion is cited

- **WHEN** a declared diffraction-limited threshold is applied
- **THEN** the result states the criterion, its numeric value, and its citation

### Requirement: Stress birefringence screened from stress and the stress-optic coefficient

The module SHALL screen stress-induced birefringence by combining a declared or computed
stress in an optical element with the element material's stress-optic coefficient,
reporting the optical path difference per unit thickness and the total retardance against
a declared tolerance. The result SHALL cite the tolerance convention the declared limit
belongs to.

#### Scenario: Retardance compared against a declared class

- **WHEN** a mounted window's stress is screened with a declared birefringence tolerance
- **THEN** the result reports the retardance, the declared limit, the verdict, and the
  convention the limit is expressed in

#### Scenario: Missing stress-optic coefficient is named

- **WHEN** the element material record carries no stress-optic coefficient
- **THEN** the screen reports "not evaluated" naming the property

### Requirement: Sealing and internal condensation screened at the environment extremes

The module SHALL screen sealed optical housings by composing the existing gland screens at
the declared temperature extremes rather than at ambient only, and SHALL screen internal
condensation by comparing the declared internal dew point against the coldest internal
surface temperature at the declared cold soak. A sealed volume with no declared internal
dew point or fill condition SHALL report "not evaluated" naming it — an unstated purge is
not a dry one.

#### Scenario: Gland screened cold and hot

- **WHEN** a sealed housing is screened over a declared temperature range
- **THEN** squeeze, gland fill, and stretch are each reported at both extremes with the
  governing extreme named

#### Scenario: Fogging is screened, not assumed away

- **WHEN** an internal dew point is declared above the coldest internal surface
  temperature at cold soak
- **THEN** the screen fails naming the margin, because the optic will fog

#### Scenario: Unstated fill condition is not a dry purge

- **WHEN** a sealed volume is declared with no fill condition or internal dew point
- **THEN** the condensation screen reports "not evaluated" naming the missing declaration

### Requirement: The module composes existing screens rather than reimplementing them

This module SHALL compose, from the existing library symbol under its own citations and
factors, every thermal, contact, impact, fastener, gland, and paraxial-optics quantity it
needs that the analysis library already provides. The module MUST NOT ship a second
implementation of an existing relation, and CI SHALL reject one naming the symbol that
should have been composed.

#### Scenario: Existing thermal relation is reused

- **WHEN** the athermal focus screen computes a differential expansion
- **THEN** it calls the library's existing expansion relation rather than restating it

#### Scenario: Duplicate implementation is rejected

- **WHEN** a submitted screen restates a relation the analysis library already exports
- **THEN** CI fails naming both symbols

### Requirement: The exclusion is on what the module ships, not on what a user types

The module SHALL exclude application-specific functionality from its own surface: it ships
no ballistic trajectory model, no aiming or fire-control solution, no lead or drop
computation, and no target-engagement content, and its manifest declares none. Conformance
SHALL be checked against the module's published symbols and declared coverage in CI, not
by inspecting the words a user writes in a spec. The module MUST NOT attempt to infer a
user's application from declared text and refuse on that basis, because such a gate matches
a vocabulary rather than a capability: it turns away legitimate work that happens to share
a word and lets the same request through under a different one.

#### Scenario: The exclusion is enforced where it is checkable

- **WHEN** CI validates the module
- **THEN** it asserts against the module's published symbols and declared coverage that no
  excluded capability is shipped, and fails naming any that is

#### Scenario: A physically declared environment always screens

- **WHEN** a user declares a shock environment by magnitude, pulse shape, duration, and
  axis
- **THEN** every applicable screen runs on the declared physics, and no screen is withheld
  on the basis of what the user says the application is

#### Scenario: The boundary is documented, not policed by keyword

- **WHEN** a user asks whether the module computes an aiming solution
- **THEN** the scope documentation states that it does not and names what it screens
  instead, and no text-matching refusal mechanism exists to be worked around

### Requirement: Orientation and the static gravity load are declared

A screen whose result depends on orientation SHALL require the declared orientation of the
assembly relative to gravity, and SHALL report the static deflection and its angular
consequence for each declared orientation rather than for one assumed attitude. Where an
assembly is declared to operate in more than one orientation, the screen SHALL envelope
them and name the governing orientation; where no orientation is declared, an
orientation-dependent screen SHALL report "not evaluated" naming it.

#### Scenario: Governing orientation is named

- **WHEN** an assembly is declared to operate horizontally and vertically
- **THEN** the static screens report both and name the governing orientation

#### Scenario: Unstated orientation refuses the screen

- **WHEN** an orientation-dependent screen runs with no declared orientation
- **THEN** it reports "not evaluated" naming the missing declaration rather than assuming
  an axis

### Requirement: As-built alignment is an input, and its absence is visible

The module SHALL treat as-built alignment error — assembly eccentricity, wedge, tilt at
build, and adjustment resolution — as declared or measured inputs it does not compute, and
a line-of-sight or wavefront budget SHALL name any as-built contributor that has not been
supplied. A budget assembled from environmental contributors alone SHALL state that it
excludes as-built error, so that a result covering only what the analysis can reach is
never read as covering the whole error.

#### Scenario: The budget says what it does not contain

- **WHEN** a line-of-sight budget contains only thermal and dynamic contributors
- **THEN** the result states that as-built alignment error is not included and names it as
  an unsupplied contributor

#### Scenario: Adjustment resolution is a contributor

- **WHEN** an adjustment mechanism's resolution is declared
- **THEN** it enters the budget as a contributor with its basis, rather than being treated
  as exact

### Requirement: Every screen names the physical test that would confirm it

Each screen SHALL map to a verification test archetype naming the environmental test
method and the severity parameters that would confirm its result physically, so that a
screening verdict carries the test it is a stand-in for. A screen with no mappable test
SHALL say so, and the verification matrix SHALL count it as analysis-only coverage rather
than leaving it unattributed.

#### Scenario: The verdict names its confirming test

- **WHEN** a thermal focus screen passes over a declared range
- **THEN** the verification matrix names the thermal test method and the severity that
  would confirm it

#### Scenario: Analysis-only coverage is counted honestly

- **WHEN** a screen maps to no physical test
- **THEN** the matrix records it as analysis-only rather than as verified

### Requirement: Boresight is the difference between two paths, not the drift of one

A boresight or overlay screen SHALL evaluate the angular difference between two declared
optical paths — a direct-view path and an injected or reflected path, two channels of a
multi-band instrument, or an instrument and its reference datum — rather than the absolute
drift of one path. Contributors common to both paths SHALL be identified as common-mode
and SHALL NOT inflate the differential result, and contributors acting on only one path
SHALL be reported as differential. A screen supplied with one path SHALL report "not
evaluated" naming the missing second path, because the drift of a single path is not a
boresight error.

#### Scenario: Common-mode motion does not count twice

- **WHEN** a housing expansion tilts both the direct path and the injected display path
  equally
- **THEN** the differential boresight result excludes the common-mode term and names it as
  common-mode, rather than reporting the full housing motion as overlay error

#### Scenario: A one-sided contributor is differential

- **WHEN** a beam-combiner mount tilts, affecting only the injected path
- **THEN** the contribution enters the differential budget in full and is named as acting
  on that path

#### Scenario: One path is not a boresight

- **WHEN** an overlay screen is requested with only one declared path
- **THEN** it reports "not evaluated" naming the missing path

### Requirement: Internal heat sources raise the volume the optics sit in

The thermal screens SHALL consume, through the declared-consumption mechanism, a computed
internal temperature rise contributed by every dissipating source declared inside an
enclosure — a display, an emitter, a detector, drive electronics — rather than treating
such a source as thermally inert. The rise SHALL be computed from the declared dissipation and
the enclosure's declared heat path, and an enclosure with a declared source and no
declared heat path SHALL report "not evaluated" naming the missing path — a sealed volume
does not shed heat by assumption.

#### Scenario: Self-heating reaches the focus screen

- **WHEN** a display dissipating a declared power is enclosed in a sealed housing
- **THEN** the internal rise is computed and the athermal focus screen evaluates at the
  raised internal temperature, naming the source in its chain

#### Scenario: No heat path, no number

- **WHEN** a dissipating source is declared with no conduction, convection, or radiation
  path out of the enclosure
- **THEN** the rise reports "not evaluated" naming the missing path rather than assuming
  ambient

#### Scenario: Self-heating moves the condensation verdict too

- **WHEN** an internal rise is computed
- **THEN** the sealing and condensation screens evaluate against the raised internal
  condition, not against ambient

### Requirement: The thermal condition declares its kind, and the wrong screen refuses

A declared thermal condition SHALL state its kind — uniform soak, spatial gradient, or
transient — and each thermal screen SHALL declare which kinds it is valid for. A uniform-
soak screen SHALL report "not evaluated" when the declared condition is a gradient, naming
the mismatch, because a soak screen applied to a gradient misses the surface deformation
and wedge that the gradient actually causes. A transient condition SHALL be compared
against the assembly's thermal time constant, and a dwell shorter than the time needed to
approach equilibrium SHALL make any equilibrium screen report that it is optimistic,
naming both durations.

#### Scenario: A gradient is not a soak

- **WHEN** a radial gradient across an element is declared and a uniform-soak focus screen
  is requested
- **THEN** the screen reports "not evaluated" naming the condition kind it requires

#### Scenario: A short dwell is called optimistic

- **WHEN** a transient condition's dwell is shorter than the assembly's time constant
- **THEN** equilibrium screens state that the declared dwell does not reach equilibrium and
  report both durations

#### Scenario: Kind is required, never defaulted

- **WHEN** a thermal condition is declared without a kind
- **THEN** the spec is rejected naming the condition, rather than assuming a soak

### Requirement: Dynamic clearance is screened against the shock displacement

A declared internal gap SHALL be screened against the relative displacement the declared
dynamic environment produces across it, so that an element free to move under shock is
caught before it strikes its housing, its neighbor, or a keepout boundary. The screen SHALL
report the computed displacement, the declared gap, and the margin, and a gap closed under
the declared environment SHALL fail regardless of the nominal-geometry intrusion verdict,
which is computed at rest.

#### Scenario: A nominal clearance closes under load

- **WHEN** a lens cell with a declared radial gap is screened against a declared shock
  environment whose displacement exceeds that gap
- **THEN** the dynamic clearance screen fails naming the gap, the displacement, and the
  contacting features, even though the static intrusion check passed

#### Scenario: Undeclared gaps are named, not assumed generous

- **WHEN** an assembly declares a dynamic environment and no internal gaps
- **THEN** the screen reports "not evaluated" naming the gaps it would need declared

### Requirement: Adjustment mechanisms are screened and are always budget contributors

A declared adjustment mechanism SHALL be screened for its resolution, its backlash or
hysteresis, its range against the correction it must cover, and whether it holds position
under the declared environment without a separate locking feature. Every adjustment
mechanism SHALL appear as a contributor in any alignment budget it bears on, because an
adjustment that can be set can also move; a mechanism declared with no resolution SHALL
report "not evaluated" naming it.

#### Scenario: Range is checked against the correction it must cover

- **WHEN** an adjustment's declared range is smaller than the misalignment the other
  screens predict it must remove
- **THEN** the screen fails reporting both, rather than reporting a mechanism that cannot
  reach as merely present

#### Scenario: Holding is screened, not assumed

- **WHEN** an adjustment mechanism is declared without a locking feature
- **THEN** the screen evaluates whether it holds under the declared environment and
  reports "not evaluated" if the properties that decide it are missing

#### Scenario: Every adjustment is in the budget

- **WHEN** an alignment budget is assembled on an assembly carrying two adjustments
- **THEN** both appear as contributors with their resolution and hysteresis, and the
  report notes that added adjustment freedom is itself a stability contributor

### Requirement: Tilted transmissive elements displace the image they pass

A screen SHALL report the axial and lateral image displacement introduced by a
plane-parallel element declared at a tilt in a converging or diverging beam, computed from
its thickness, index, and tilt, and that displacement SHALL enter the focus and
boresight budgets as a contributor. A beam combiner, window, or filter declared in a path
with no thickness or index SHALL report "not evaluated" naming the missing property,
because an element declared as if it had no optical effect is an unchecked claim.

#### Scenario: A window is not optically free

- **WHEN** a sealing window is declared in a converging beam
- **THEN** its axial image displacement is computed and enters the focus budget

#### Scenario: Combiner tilt reaches the boresight budget

- **WHEN** a beam combiner is declared at a tilt in one path
- **THEN** its lateral displacement enters the differential boresight budget as a
  one-sided contributor

### Requirement: Harnesses and flexible attachments load the mount they cross

A screen SHALL report the parasitic force and moment applied by every cable, ribbon,
harness, or other flexible attachment declared as crossing a mount interface, computed
from its declared routing and stiffness, and the resulting alignment shift SHALL enter the
alignment budget.
A declared crossing attachment with no declared stiffness SHALL report "not evaluated"
naming it, because a harness assumed to be free is one of the most common unmodelled
sources of alignment drift in a compact assembly.

#### Scenario: A ribbon cable shifts the element it serves

- **WHEN** a display ribbon is declared crossing from the housing to an adjustable mount
- **THEN** the parasitic load and its alignment consequence are reported and enter the
  budget

#### Scenario: A crossing with no stiffness is named

- **WHEN** a harness is declared crossing a mount with no stiffness or routing declared
- **THEN** the screen reports "not evaluated" naming what it needs

### Requirement: Retention after cycling is verification-only and says so

Alignment retention after repeated thermal or mechanical cycling SHALL be reported as not
screenable by analysis, naming the physical test that establishes it, rather than being
approximated or omitted. The module MUST NOT report a retention verdict computed from
single-excursion screens, because bolted joints, adhesives, and preloaded interfaces do
not return to their starting state and no closed-form screen in this module models that
path dependence.

#### Scenario: Cycling retention is named, not inferred

- **WHEN** a spec declares a retention requirement after a number of thermal cycles
- **THEN** the scorecard carries a not-evaluated entry naming the requirement and the test
  method that would establish it, and the card does not pass on the single-excursion
  screens alone

#### Scenario: Single-excursion results do not stand in for cycling

- **WHEN** the thermal screens pass over the declared range
- **THEN** no retention-after-cycling verdict is derived from them

### Requirement: Each named workflow ships as an end-to-end example

The module SHALL ship a runnable example for each workflow it claims to serve — an
injected-display housing with a beam combiner, a ruggedized assembly under a declared
shock environment, and an assembly through a declared thermal range — each carrying a
spec, the full scorecard, and the budgets, with at least one screen failing so the example
demonstrates a real verdict rather than a curated pass. A claimed workflow with no
end-to-end example SHALL fail CI, because a feature whose consumers are each tested alone
has never been shown to work as a flow.

#### Scenario: The workflow runs as one flow

- **WHEN** the injected-display example is run
- **THEN** it compiles a spec, generates the beam-path keepout, runs the thermal, dynamic,
  retention, sealing, and clearance screens, assembles the differential boresight budget,
  and prints a card whose verdict follows from them

#### Scenario: An example that cannot fail is not an example

- **WHEN** a workflow example passes every screen
- **THEN** CI fails requiring a variant that exercises a real failure and its repair hint

#### Scenario: A claimed workflow without a flow fails CI

- **WHEN** the module's documentation claims a workflow with no corresponding end-to-end
  example
- **THEN** CI fails naming the workflow

### Requirement: Every non-metallic in a sealed optical volume is censused for outgassing

The module SHALL census every non-metallic material declared inside a sealed optical
volume — adhesives, elastomers, potting, conformal coatings, cable jackets, labels,
lubricants — against declared outgassing limits, reporting each material's total mass loss
and collected volatile condensable material with the test method and source cited. The
condensable figure SHALL be reported as the optics-governing one, because it is the
fraction that deposits on cold and optical surfaces. A declared non-metallic with no
outgassing data SHALL report "not evaluated" naming the material, and the census SHALL
report the population it examined so a clean result is distinguishable from an empty one.

#### Scenario: The census names its population

- **WHEN** a sealed assembly declaring nine non-metallics passes the outgassing screen
- **THEN** the result states that nine materials were examined, lists each with its
  figures and source, and names the limits applied

#### Scenario: An undeclared-data material is not assumed clean

- **WHEN** an adhesive is declared with no outgassing data
- **THEN** the screen reports "not evaluated" naming the adhesive, rather than passing the
  assembly on the materials that did have data

#### Scenario: The condensable figure governs near optics

- **WHEN** a material passes the mass-loss limit and exceeds the condensable limit
- **THEN** the screen fails naming the condensable figure and stating that it is the
  optics-governing criterion

### Requirement: A sealed volume that cycles is screened for breathing and ingress

A screen SHALL evaluate the pressure differential a declared thermal cycle drives across a
sealed volume's boundary, and SHALL report whether the design admits that differential
through a declared pressure-equalization path or resists it through the seal. Where the
differential is resisted and the environment declares repeated cycles, the screen SHALL
report cumulative moisture ingress as a verification-only concern naming the test, because
a seal that breathes ingests ambient air on every cycle and accumulates water over many —
the mechanism behind most fogged instruments. A volume declared sealed against a cycling
environment with neither an equalization path nor a declared desiccant or purge SHALL be
reported as a finding, not a pass.

#### Scenario: Breathing is computed, not assumed away

- **WHEN** a sealed volume is declared against a thermal cycling environment
- **THEN** the screen reports the driven pressure differential per cycle and whether an
  equalization path is declared

#### Scenario: No path, no desiccant, no purge is a finding

- **WHEN** a cycling sealed volume declares none of an equalization membrane, a desiccant,
  or a purge fill
- **THEN** the screen reports a finding naming the mechanism, rather than a clean seal
  verdict

#### Scenario: Accumulation is verification-only and says so

- **WHEN** cumulative ingress over a declared cycle count is at issue
- **THEN** the result names the test method that establishes it and does not report an
  analytical verdict

### Requirement: Windows and closures are screened under the declared pressure differential

A screen SHALL report the stress and deflection of every declared window, closure, or
sealing element under the pressure differential implied by the declared altitude, depth,
or internal fill condition, and the resulting optical effect — surface deformation and its
focus consequence — SHALL enter the focus and wavefront budgets. The screen SHALL evaluate
the worst declared differential in both directions, since a volume sealed at one pressure
sees an outward differential at altitude and an inward one under immersion or at low
temperature.

#### Scenario: Both directions are screened

- **WHEN** an assembly declares both a high-altitude and an immersion condition
- **THEN** the window screen reports stress and deflection under both differentials and
  names the governing one

#### Scenario: Window bow reaches the focus budget

- **WHEN** a window deflects under a declared differential
- **THEN** the induced optical effect enters the focus and wavefront budgets as a
  contributor attributed to that condition

#### Scenario: Undeclared fill condition refuses the screen

- **WHEN** a sealed volume declares no fill pressure
- **THEN** the differential screen reports "not evaluated" naming it, rather than assuming
  sea-level fill

### Requirement: Coatings and cements carry their own environmental limits

Every declared optical coating and cemented joint SHALL carry its declared environmental
limits — temperature range, humidity exposure, and radiation or irradiance where relevant
— and a screen SHALL compare the declared environment against them, failing when the
environment exceeds a limit and naming both. A coated or cemented surface declared with no
limits SHALL report "not evaluated" naming the surface, because a cement softening or a
coating delaminating at a temperature the housing survives is a failure the mechanical
screens cannot see.

#### Scenario: The cement, not the housing, governs

- **WHEN** a declared thermal range exceeds a cemented doublet's declared limit while the
  housing screens pass
- **THEN** the card fails naming the cement, its limit, and the declared range

#### Scenario: A coated surface with no limits is named

- **WHEN** a coating is declared with no environmental limits
- **THEN** the screen reports "not evaluated" naming the surface and the limits it needs

### Requirement: Cleanliness is a declared requirement with assembly consequences

A declared surface cleanliness or particulate level SHALL be reported together with the
assembly environment it implies and the declared assembly environment, failing when the
declared environment cannot achieve the declared level. Where a cleanliness level is
required by a spec and no assembly environment is declared, the screen SHALL report "not
evaluated" naming it, because a cleanliness requirement nobody costed into the build
environment is a requirement that will be discovered at assembly.

#### Scenario: The requirement reaches the build environment

- **WHEN** a spec declares a surface cleanliness level and an assembly environment that
  cannot achieve it
- **THEN** the screen fails naming both, with the cited basis for the implication

#### Scenario: An uncosted cleanliness requirement is named

- **WHEN** a cleanliness level is declared with no assembly environment
- **THEN** the screen reports "not evaluated" naming the missing declaration

### Requirement: The module ships environment profiles so a first screen is minutes, not a day

The module SHALL ship cited, versioned environment profiles covering its common operating
classes — benchtop, handheld, vehicle-mounted, airborne, and sealed-and-purged — each
supplying a coherent set of the declarations its screens require, with an applicability
statement and every supplied value attributed to the profile. A user SHALL be able to bind
one profile and reach a real scorecard, then override individual values as their design
becomes specific, because a module that requires twenty declarations before it says
anything will be abandoned before it says anything.

#### Scenario: One binding reaches a real verdict

- **WHEN** a user declares a lens cell and binds the handheld profile
- **THEN** the thermal, dynamic, sealing, and clearance screens run on profile-supplied
  declarations, and every profile-sourced value is marked as such on the card

#### Scenario: The profile is a starting point, not an answer

- **WHEN** a profile-supplied value governs a verdict
- **THEN** the result names the profile as the source and states that the value is a
  class default the user should confirm

#### Scenario: Profiles do not paper over a real gap

- **WHEN** a screen needs a design-specific value no profile can supply, such as an
  element's allowable stress or a mount's measured compliance
- **THEN** it still reports "not evaluated" naming that value — a profile supplies
  environments, never the design's own properties
